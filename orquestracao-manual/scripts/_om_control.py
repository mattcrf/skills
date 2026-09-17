"""Operation preparation, immutable task publication, and bridge dispatch."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import sys
import tomllib
from pathlib import Path


OP_FORMAT = "om-operation/1"
STATUS_FORMAT = "om-status/1"
EVENT_TYPE = "task-published"
TARGET_TASK_BYTES = 2_000
TARGET_TASK_WORDS = 250
OPS_ROOT_ENV = "ORQUESTRACAO_MANUAL_OPS_ROOT"
ID_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
EFFECTS = {"read-only", "mutating"}
KINDS = {"scout", "writer", "verifier"}
OP_KEYS = {"format", "id", "project_root", "current_context", "profiles"}
PROFILE_KEYS = {"effects"}
TASK_KEYS = {"id", "kind", "effect", "profile", "context", "depends"}
EVENT_KEYS = {
    "seq",
    "prev",
    "type",
    "task_id",
    "task_sha256",
    "effect",
    "profile",
    "context",
    "event_hash",
}


class ControlError(Exception):
    pass


def _error(message: str) -> "NoReturn":  # type: ignore[name-defined]
    raise ControlError(message)


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        _error("unreadable %s: %s" % (label, path))


def _decode(raw: bytes, label: str) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        _error("invalid utf-8 in %s" % label)


def _load_toml(path: Path, label: str) -> dict:
    try:
        value = tomllib.loads(_decode(_read_bytes(path, label), label))
    except tomllib.TOMLDecodeError as exc:
        _error("invalid TOML in %s: %s" % (label, exc))
    if not isinstance(value, dict):
        _error("invalid %s" % label)
    return value


def _validate_id(value: object, label: str) -> str:
    if not isinstance(value, str):
        _error("invalid %s" % label)
    if ID_RE.fullmatch(value) is None:
        _error("invalid %s" % label)
    return value


def _load_operation(root: Path) -> dict:
    if not root.is_dir():
        _error("operation directory does not exist: %s" % root)
    path = root / "operation.toml"
    doc = _load_toml(path, "operation.toml")
    if set(doc) != OP_KEYS or doc.get("format") != OP_FORMAT:
        _error("invalid operation.toml schema")
    op_id = _validate_id(doc.get("id"), "operation id")
    project_raw = doc.get("project_root")
    if not isinstance(project_raw, str) or not project_raw:
        _error("invalid project_root")
    project = Path(project_raw)
    if not project.is_absolute() or not project.is_dir():
        _error("project_root must be an existing absolute directory")
    context = doc.get("current_context")
    if isinstance(context, bool) or not isinstance(context, int) or context <= 0:
        _error("current_context must be a positive integer")
    profiles = doc.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        _error("profiles must be a non-empty table")
    clean_profiles: dict[str, dict] = {}
    for name, profile in profiles.items():
        _validate_id(name, "profile id")
        if not isinstance(profile, dict) or set(profile) != PROFILE_KEYS:
            _error("invalid profile schema: %s" % name)
        effects = profile.get("effects")
        if (
            not isinstance(effects, list)
            or not effects
            or any(not isinstance(item, str) or item not in EFFECTS for item in effects)
            or len(effects) != len(set(effects))
        ):
            _error("invalid effects for profile: %s" % name)
        clean_profiles[name] = {"effects": list(effects)}
    return {
        "id": op_id,
        "project_root": str(project),
        "current_context": context,
        "profiles": clean_profiles,
    }


def _parse_task(path: Path, operation: dict) -> tuple[dict, bytes]:
    raw = _read_bytes(path, "task")
    text = _decode(raw, "task")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "+++":
        _error("task must start with TOML front matter")
    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "+++"), None)
    if closing is None:
        _error("task front matter is not closed")
    try:
        front = tomllib.loads("".join(lines[1:closing]))
    except tomllib.TOMLDecodeError as exc:
        _error("invalid task front matter: %s" % exc)
    if not isinstance(front, dict) or set(front) != TASK_KEYS:
        _error("invalid task front matter schema")
    task_id = _validate_id(front.get("id"), "task id")
    if path.stem != task_id:
        _error("task id differs from filename")
    kind = front.get("kind")
    if not isinstance(kind, str) or kind not in KINDS:
        _error("invalid task kind")
    effect = front.get("effect")
    if not isinstance(effect, str) or effect not in EFFECTS:
        _error("invalid task effect")
    profile = front.get("profile")
    if not isinstance(profile, str) or profile not in operation["profiles"]:
        _error("unknown task profile")
    if effect not in operation["profiles"][profile]["effects"]:
        _error("task effect is not granted by profile")
    context = front.get("context")
    if (
        isinstance(context, bool)
        or not isinstance(context, int)
        or context <= 0
        or context > operation["current_context"]
    ):
        _error("invalid task context")
    depends = front.get("depends")
    if (
        not isinstance(depends, list)
        or any(not isinstance(item, str) or ID_RE.fullmatch(item) is None for item in depends)
        or len(depends) != len(set(depends))
        or task_id in depends
    ):
        _error("invalid task dependencies")
    body = "".join(lines[closing + 1 :])
    if not body.strip():
        _error("task body is empty")
    if "TODO:" in body:
        _error("task still contains TODO markers")
    return {
        "id": task_id,
        "kind": kind,
        "effect": effect,
        "profile": profile,
        "context": context,
        "depends": list(depends),
    }, raw


def _canonical_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _event_hash(event_without_hash: dict) -> str:
    return hashlib.sha256(_canonical_json(event_without_hash).encode("utf-8")).hexdigest()


def _task_sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _word_count(raw: bytes) -> int:
    return len(re.findall(r"\S+", _decode(raw, "task")))


def _toml_string(value: str) -> str:
    # JSON basic strings are valid TOML basic strings for these values.
    return json.dumps(value, ensure_ascii=False)


def _atomic_write(path: Path, data: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        _error("cannot write: %s" % path)
    temporary = path.with_name(".%s.tmp-%d" % (path.name, os.getpid()))
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        _error("cannot write: %s" % path)


def _lock_handle(handle) -> None:
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_handle(handle) -> None:
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    finally:
        handle.close()


@contextlib.contextmanager
def _exclusive_lock(root: Path):
    path = root / ".cache" / "control.lock"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        _error("cannot open lock file: %s" % path)
    try:
        handle = path.open("a+b")
    except OSError:
        _error("cannot open lock file: %s" % path)
    try:
        _lock_handle(handle)
    except OSError:
        handle.close()
        _error("cannot acquire lock: %s" % path)
    try:
        yield
    finally:
        _unlock_handle(handle)


def _load_events(root: Path, operation: dict) -> list[dict]:
    path = root / "events.jsonl"
    if not path.exists():
        return []
    text = _decode(_read_bytes(path, "events.jsonl"), "events.jsonl")
    events: list[dict] = []
    task_ids: set[str] = set()
    previous = None
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line:
            _error("blank event at line %d" % line_number)
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            _error("invalid event JSON at line %d" % line_number)
        if not isinstance(event, dict) or set(event) != EVENT_KEYS:
            _error("invalid event schema at line %d" % line_number)
        if event["seq"] != line_number or event["prev"] != previous:
            _error("broken event chain at line %d" % line_number)
        supplied_hash = event["event_hash"]
        bare = {key: value for key, value in event.items() if key != "event_hash"}
        if supplied_hash != _event_hash(bare):
            _error("invalid event hash at line %d" % line_number)
        if event["type"] != EVENT_TYPE:
            _error("unknown event type at line %d" % line_number)
        task_id = _validate_id(event["task_id"], "event task id")
        if task_id in task_ids:
            _error("duplicate published task: %s" % task_id)
        task_ids.add(task_id)
        task_path = root / "tasks" / (task_id + ".md")
        task, raw = _parse_task(task_path, operation)
        if _task_sha(raw) != event["task_sha256"]:
            _error("published task changed: %s" % task_id)
        for key in ("effect", "profile", "context"):
            if task[key] != event[key]:
                _error("task metadata differs from event: %s" % task_id)
        events.append(event)
        previous = supplied_hash
    disk_ids = {path.stem for path in (root / "tasks").glob("*.md")} if (root / "tasks").is_dir() else set()
    if disk_ids != task_ids:
        _error("task files differ from published event set")
    task_docs = {event["task_id"]: _parse_task(root / "tasks" / (event["task_id"] + ".md"), operation)[0] for event in events}
    for task in task_docs.values():
        missing = sorted(set(task["depends"]) - set(task_docs))
        if missing:
            _error("missing dependencies for %s: %s" % (task["id"], ", ".join(missing)))
    _reject_dependency_cycles(task_docs)
    return events


def _reject_dependency_cycles(tasks: dict[str, dict]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            _error("dependency cycle at task: %s" % task_id)
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in tasks[task_id]["depends"]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in sorted(tasks):
        visit(task_id)


def _state(root: Path, operation: dict) -> tuple[list[dict], list[dict]]:
    events = _load_events(root, operation)
    tasks = []
    for event in events:
        task, _raw = _parse_task(root / "tasks" / (event["task_id"] + ".md"), operation)
        state = "blocked" if task["depends"] else "ready"
        tasks.append({**task, "state": state, "sha256": event["task_sha256"]})
    return events, tasks


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            continue


def _guard(action, args) -> int:
    _configure_stdio()
    try:
        return int(action(args))
    except ControlError as exc:
        sys.stderr.write("om: %s\n" % exc)
        return 1


def _publish(args) -> int:
    root = Path(args.operation)
    operation = _load_operation(root)
    source = Path(args.task)
    with _exclusive_lock(root):
        events, tasks = _state(root, operation)
        task, raw = _parse_task(source, operation)
        if any(item["id"] == task["id"] for item in tasks):
            _error("task already published: %s" % task["id"])
        missing = sorted(set(task["depends"]) - {item["id"] for item in tasks})
        if missing:
            _error("missing dependencies: %s" % ", ".join(missing))
        target = root / "tasks" / (task["id"] + ".md")
        if target.exists():
            _error("task file already exists: %s" % target)
        bare_event = {
            "seq": len(events) + 1,
            "prev": events[-1]["event_hash"] if events else None,
            "type": EVENT_TYPE,
            "task_id": task["id"],
            "task_sha256": _task_sha(raw),
            "effect": task["effect"],
            "profile": task["profile"],
            "context": task["context"],
        }
        event = {**bare_event, "event_hash": _event_hash(bare_event)}
        existing = b"" if not events else _read_bytes(root / "events.jsonl", "events.jsonl")
        event_bytes = (_canonical_json(event) + "\n").encode("utf-8")
        _atomic_write(target, raw)
        try:
            _atomic_write(root / "events.jsonl", existing + event_bytes)
        except ControlError:
            try:
                target.unlink()
            except OSError:
                pass
            raise
    state = "blocked" if task["depends"] else "ready"
    words = _word_count(raw)
    budget = (
        "within"
        if len(raw) <= TARGET_TASK_BYTES and words <= TARGET_TASK_WORDS
        else "over"
    )
    sys.stdout.write(
        "published %s state=%s event=%d bytes=%d words=%d budget=%s sha256=%s\n"
        % (
            task["id"],
            state,
            event["seq"],
            len(raw),
            words,
            budget,
            event["task_sha256"],
        )
    )
    return 0


def run_task_publish(args) -> int:
    return _guard(_publish, args)


def _default_operations_root() -> Path:
    configured = os.environ.get(OPS_ROOT_ENV)
    if configured:
        root = Path(configured).expanduser()
        if not root.is_absolute():
            _error("%s must be an absolute directory" % OPS_ROOT_ENV)
        return root.resolve()
    return (Path.home() / "Documents" / "skills" / "temp" / "ops").resolve()


def _op_init(args) -> int:
    project = Path(args.project_root).resolve()
    if not project.is_dir():
        _error("project_root must be an existing directory: %s" % project)
    if args.operation is None:
        if args.id is None:
            _error("--id is required when --operation is omitted")
        op_id = _validate_id(args.id, "operation id")
        root = (_default_operations_root() / op_id).resolve()
    else:
        root = Path(args.operation).resolve()
        op_id = _validate_id(args.id or root.name, "operation id")
    context = args.context
    if isinstance(context, bool) or not isinstance(context, int) or context <= 0:
        _error("context must be a positive integer")
    if root.exists() and any(root.iterdir()):
        _error("operation directory is not empty: %s" % root)
    try:
        root.mkdir(parents=True, exist_ok=True)
        for name in ("tasks", "results", ".scratch", ".cache"):
            (root / name).mkdir()
    except OSError:
        _error("cannot initialize operation: %s" % root)
    document = """\
format = "om-operation/1"
id = {op_id}
project_root = {project}
current_context = {context}

[profiles.scout]
effects = ["read-only"]

[profiles.implementer]
effects = ["mutating"]

[profiles.independent-reviewer]
effects = ["read-only"]
""".format(
        op_id=_toml_string(op_id),
        project=_toml_string(project.as_posix()),
        context=context,
    )
    _atomic_write(root / "operation.toml", document.encode("utf-8"))
    _atomic_write(root / ".gitignore", b"/.cache/\n/.scratch/\n")
    sys.stdout.write("initialized %s operation=%s project=%s\n" % (op_id, root, project))
    return 0


def run_op_init(args) -> int:
    return _guard(_op_init, args)


def _task_defaults(kind: str) -> tuple[str, str]:
    if kind == "writer":
        return "mutating", "implementer"
    if kind == "verifier":
        return "read-only", "independent-reviewer"
    return "read-only", "scout"


def _task_new(args) -> int:
    root = Path(args.operation)
    operation = _load_operation(root)
    task_id = _validate_id(args.id, "task id")
    kind = args.kind
    default_effect, default_profile = _task_defaults(kind)
    effect = args.effect or default_effect
    profile = args.profile or default_profile
    if effect not in EFFECTS:
        _error("invalid task effect")
    if profile not in operation["profiles"]:
        _error("unknown task profile")
    if effect not in operation["profiles"][profile]["effects"]:
        _error("task effect is not granted by profile")
    depends = list(args.depends or [])
    if len(depends) != len(set(depends)):
        _error("duplicate task dependency")
    for dependency in depends:
        _validate_id(dependency, "task dependency")
    if task_id in depends:
        _error("task cannot depend on itself")
    context = operation["current_context"] if args.context is None else args.context
    if context <= 0 or context > operation["current_context"]:
        _error("invalid task context")
    result = (root / "results" / (task_id + ".md")).resolve()
    title = args.title or task_id
    document = """\
+++
id = {task_id}
kind = {kind}
effect = {effect}
profile = {profile}
context = {context}
depends = {depends}
+++

# {title}

Operação compartilhada: `{operation}`.

## Objetivo

TODO: descreva a entrega observável.

## Contexto específico

TODO: aponte somente fontes e decisões ainda necessárias.

## Permissão e limites

TODO: delimite escrita, efeitos e exclusões próprias desta tarefa.

## Aceitação

TODO: liste evidências que permitem julgar a entrega.

## Retorno

Grave o resultado em `{result}` conforme o protocolo do trabalhador.
""".format(
        task_id=_toml_string(task_id),
        kind=_toml_string(kind),
        effect=_toml_string(effect),
        profile=_toml_string(profile),
        context=context,
        depends=json.dumps(depends, ensure_ascii=False),
        title=title,
        operation=root.resolve(),
        result=result,
    )
    target = root / ".scratch" / "drafts" / (task_id + ".md")
    if target.exists() or (root / "tasks" / (task_id + ".md")).exists():
        _error("task already exists: %s" % task_id)
    _atomic_write(target, document.encode("utf-8"))
    sys.stdout.write("draft %s\n" % target.resolve())
    return 0


def run_task_new(args) -> int:
    return _guard(_task_new, args)


def _execution_path(root: Path, dispatch_path: Path) -> Path:
    stem = dispatch_path.stem
    suffix = stem[len("dispatch") :] if stem.startswith("dispatch") else "-" + stem
    return root / ("execution%s.md" % suffix)


def _bridge_dispatch(args) -> int:
    root = Path(args.operation).resolve()
    operation = _load_operation(root)
    if args.slots < 1 or args.slots > 3:
        _error("slots must be between 1 and 3")
    with _exclusive_lock(root):
        _events, tasks = _state(root, operation)
    by_id = {task["id"]: task for task in tasks}
    selected_ids = list(args.tasks or [task["id"] for task in tasks])
    if not selected_ids:
        _error("operation has no published tasks")
    if len(selected_ids) != len(set(selected_ids)):
        _error("duplicate task selected for dispatch")
    missing = [task_id for task_id in selected_ids if task_id not in by_id]
    if missing:
        _error("unknown task for dispatch: %s" % ", ".join(missing))
    selected = [by_id[task_id] for task_id in selected_ids]
    out = Path(args.out).resolve() if args.out else root / "dispatch.md"
    if out.exists():
        _error("dispatch already exists: %s" % out)
    execution = _execution_path(root, out)
    skill_root = Path(__file__).resolve().parent.parent
    skill = skill_root / "SKILL.md"
    manager = skill_root / "references" / "gerente.md"
    worker = skill_root / "references" / "trabalhador.md"
    for path in (skill, manager, worker):
        if not path.is_file():
            _error("installed protocol file is missing: %s" % path)
    lines = [
        "# Despacho — %s" % operation["id"],
        "",
        "Papel: gerente",
        "Protocolo: `%s`" % skill,
        "Referência do gerente: `%s`" % manager,
        "Referência do trabalhador: `%s`" % worker,
        "Projeto: `%s`" % operation["project_root"],
        "Operação: `%s`" % root,
        "Índice de execução: `%s`" % execution.resolve(),
        "Vagas concedidas: %d" % args.slots,
        "Escrita: no máximo uma tarefa mutante por vez.",
        "",
        "| ID | Pedido publicado | Efeito | Depende de | Retorno |",
        "| --- | --- | --- | --- | --- |",
    ]
    for task in selected:
        dependencies = ", ".join(task["depends"]) or "nenhuma"
        lines.append(
            "| {id} | `{task}` | {effect} | {depends} | `{result}` |".format(
                id=task["id"],
                task=(root / "tasks" / (task["id"] + ".md")).resolve(),
                effect=task["effect"],
                depends=dependencies,
                result=(root / "results" / (task["id"] + ".md")).resolve(),
            )
        )
    rendered = "\n".join(lines) + "\n"
    _atomic_write(out, rendered.encode("utf-8"))
    sys.stdout.write("dispatch %s\n" % out)
    sys.stdout.write('manager: Leia "%s" e execute as instruções.\n' % out)
    return 0


def run_bridge_dispatch(args) -> int:
    return _guard(_bridge_dispatch, args)


def _render_brief(operation: dict, events: list[dict], tasks: list[dict]) -> str:
    lines = [
        "operation=%s context=%d events=%d tasks=%d"
        % (
            operation["id"],
            operation["current_context"],
            len(events),
            len(tasks),
        )
    ]
    for task in tasks:
        line = "%s %s" % (task["id"], task["state"])
        if task["depends"]:
            line += " depends=%s" % ",".join(task["depends"])
        lines.append(line)
    return "\n".join(lines) + "\n"


def _status(args) -> int:
    root = Path(args.operation)
    operation = _load_operation(root)
    with _exclusive_lock(root):
        events, tasks = _state(root, operation)
    if getattr(args, "brief", False):
        sys.stdout.write(_render_brief(operation, events, tasks))
        return 0
    document = {
        "format": STATUS_FORMAT,
        "operation": operation["id"],
        "context": operation["current_context"],
        "event_head": None if not events else {"seq": events[-1]["seq"], "hash": events[-1]["event_hash"]},
        "tasks": [
            {
                "id": task["id"],
                "kind": task["kind"],
                "effect": task["effect"],
                "profile": task["profile"],
                "state": task["state"],
                "depends": task["depends"],
            }
            for task in tasks
        ],
    }
    sys.stdout.write(json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n")
    return 0


def run_status(args) -> int:
    return _guard(_status, args)


def _doctor(args) -> int:
    root = Path(args.operation)
    operation = _load_operation(root)
    with _exclusive_lock(root):
        events, tasks = _state(root, operation)
    sys.stdout.write(
        "OK operation=%s tasks=%d events=%d head=%s\n"
        % (
            operation["id"],
            len(tasks),
            len(events),
            "none" if not events else events[-1]["event_hash"],
        )
    )
    return 0


def run_doctor(args) -> int:
    return _guard(_doctor, args)


def _resume(args) -> int:
    root = Path(args.operation)
    operation = _load_operation(root)
    with _exclusive_lock(root):
        events, tasks = _state(root, operation)
    ready = [task for task in tasks if task["state"] == "ready"]
    blocked = [task for task in tasks if task["state"] == "blocked"]
    lines = [
        "# Resume - %s" % args.role,
        "",
        "Operation: `%s`" % operation["id"],
        "Project: `%s`" % operation["project_root"],
        "Context: `%s`" % operation["current_context"],
        "Event head: `%s`" % ("none" if not events else events[-1]["event_hash"]),
        "",
        "## Ready",
        "",
    ]
    lines.extend(
        ["- `%s` - %s, profile `%s`" % (task["id"], task["effect"], task["profile"]) for task in ready]
        or ["- Nothing"]
    )
    lines.extend(["", "## Blocked", ""])
    lines.extend(
        ["- `%s` - depends on %s" % (task["id"], ", ".join("`%s`" % dep for dep in task["depends"])) for task in blocked]
        or ["- Nothing"]
    )
    lines.extend(["", "## Next decision", ""])
    lines.append("- Dispatch `%s`." % ready[0]["id"] if ready else "- No task is ready.")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


def run_resume(args) -> int:
    return _guard(_resume, args)


def register_cli(sub) -> None:
    op = sub.add_parser("op", help="operation lifecycle commands")
    op_sub = op.add_subparsers(dest="op_command", required=True)
    init = op_sub.add_parser("init", help="create a local operation")
    init.add_argument(
        "--operation",
        required=False,
        default=None,
        help="new operation directory; defaults to the standard operations root plus --id",
    )
    init.add_argument("--project-root", required=True, help="existing project root")
    init.add_argument(
        "--id",
        required=False,
        default=None,
        help="operation id; required for the standard root, otherwise defaults to directory name",
    )
    init.add_argument("--context", required=False, type=int, default=1)
    init.set_defaults(func=run_op_init)
    task = sub.add_parser("task", help="local task lifecycle commands")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    new = task_sub.add_parser("new", help="create an editable task draft")
    new.add_argument("--operation", required=True, help="operation directory")
    new.add_argument("--id", required=True, help="task id")
    new.add_argument("--kind", required=True, choices=tuple(sorted(KINDS)))
    new.add_argument("--effect", required=False, choices=tuple(sorted(EFFECTS)), default=None)
    new.add_argument("--profile", required=False, default=None)
    new.add_argument("--context", required=False, type=int, default=None)
    new.add_argument("--depends", nargs="*", default=[])
    new.add_argument("--title", required=False, default=None)
    new.set_defaults(func=run_task_new)
    publish = task_sub.add_parser("publish", help="validate and seal a task")
    publish.add_argument("--operation", required=True, help="operation directory")
    publish.add_argument("--task", required=True, help="draft task markdown")
    publish.set_defaults(func=run_task_publish)
    status = sub.add_parser("status", help="derive operation status from events")
    status.add_argument("--operation", required=True, help="operation directory")
    status.add_argument(
        "--brief", action="store_true", help="print a compact human-readable summary"
    )
    status.set_defaults(func=run_status)
    resume = sub.add_parser("resume", help="render a role resume capsule")
    resume.add_argument("--operation", required=True, help="operation directory")
    resume.add_argument("--role", required=True, choices=("captain",))
    resume.set_defaults(func=run_resume)
    doctor = sub.add_parser("doctor", help="validate operation invariants")
    doctor.add_argument("--operation", required=True, help="operation directory")
    doctor.set_defaults(func=run_doctor)
    bridge = sub.add_parser("bridge", help="generate bridge transport artifacts")
    bridge_sub = bridge.add_subparsers(dest="bridge_command", required=True)
    dispatch = bridge_sub.add_parser(
        "dispatch", help="generate a minimal operational manager dispatch"
    )
    dispatch.add_argument("--operation", required=True, help="operation directory")
    dispatch.add_argument("--slots", required=False, type=int, default=2)
    dispatch.add_argument("--tasks", nargs="*", default=None, help="published task ids; defaults to all")
    dispatch.add_argument("--out", required=False, default=None, help="immutable dispatch path")
    dispatch.set_defaults(func=run_bridge_dispatch)

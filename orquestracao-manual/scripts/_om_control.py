"""Minimal local control plane for the Phase B vertical slice."""

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
MAX_TASK_BYTES = 2_000
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
    if len(raw) > MAX_TASK_BYTES:
        _error("task exceeds %d bytes" % MAX_TASK_BYTES)
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
    if not "".join(lines[closing + 1 :]).strip():
        _error("task body is empty")
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
    sys.stdout.write(
        "published %s state=%s event=%d sha256=%s\n"
        % (task["id"], state, event["seq"], event["task_sha256"])
    )
    return 0


def run_task_publish(args) -> int:
    return _guard(_publish, args)


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
    task = sub.add_parser("task", help="local task lifecycle commands")
    task_sub = task.add_subparsers(dest="task_command", required=True)
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

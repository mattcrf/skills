"""Private replay benchmark (convert and measure the selected Phase B slices).

The spec carries the sealed sources, the stable required-item identifiers and
their mapping into the generated v2 task fields. Tasks are rendered in memory,
validated through the local control schema and never committed.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import re
import sys
import tempfile
from pathlib import Path

SPEC_FORMAT = "om-benchmark-replay-spec/1"
REPORT_FORMAT = "om-benchmark-replay/1"
OPERATION_FORMAT = "om-operation/1"

ALGORITHM = {
    "bytes": (
        "raw utf-8 byte length of the rendered task, including the TOML front "
        "matter and the trailing newline"
    ),
    "note": (
        "tasks are rendered from the spec in memory; the very same text is "
        "published into a throwaway operation and re-read by the local "
        "control schema before any measurement is reported"
    ),
    "words": (
        "count of non-overlapping matches of the regular expression \\S+ "
        "over the task text decoded as utf-8-sig"
    ),
}

PROVENANCE_NOTE = (
    "Source hashes, words and bytes are sealed in the spec and cross-check "
    "the frozen Phase A legacy fixture; generated task copies are never "
    "committed."
)

_ITEM_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]*\.[0-9]+")
_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
_CASE_RE = re.compile(r"[a-z][a-z0-9_-]*")
_FIELD_RE = re.compile(r"[a-z][a-z0-9_]*")
_HEX64_RE = re.compile(r"[0-9a-fA-F]{64}")
_WORD_RE = re.compile(r"\S+")

_KINDS = {"scout", "writer", "verifier"}
_EFFECTS = {"read-only", "mutating"}
_RELATIONS = {"correction_dependency", "parallel_independence"}
_SPEC_KEYS = {"format", "operation", "limits", "sources", "cases"}
_OPERATION_KEYS = {"current_context", "profiles"}
_LIMIT_KEYS = {"task_bytes_max", "task_words_max"}
_SOURCE_KEYS = {"id", "bytes", "words", "sha256"}
_CASE_KEYS = {"id", "shape", "original_source_ids", "required_items", "tasks"}
_TASK_KEYS = {
    "id",
    "kind",
    "effect",
    "profile",
    "context",
    "depends",
    "sections",
    "items",
}
_SECTION_KEYS = {"field", "heading", "text"}
_REPORT_KEYS = {
    "format",
    "spec_sha256",
    "algorithm",
    "limits",
    "sources",
    "cases",
    "coverage",
    "average_task",
    "validation",
    "provenance",
}


def _input_error(message: str) -> "NoReturn":  # type: ignore[name-defined]
    sys.stderr.write("om: replay error: %s\n" % message)
    raise SystemExit(2)


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        _input_error("unreadable %s: %s" % (label, path))


def _parse_json(raw: bytes, path: Path, label: str) -> dict:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        _input_error("invalid %s format: %s" % (label, path))
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        _input_error("invalid %s format: %s" % (label, path))
    if not isinstance(data, dict):
        _input_error("invalid %s format: %s" % (label, path))
    return data


def _as_nonempty_str(value: object) -> str:
    if not isinstance(value, str) or value == "":
        return ""
    return value


def _as_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, int):
        return None
    if value <= 0:
        return None
    return value


def _as_name(value: object) -> str:
    if not isinstance(value, str) or value == "":
        return ""
    if value != value.strip():
        return ""
    if any(char in value for char in ("/", "\\", ":")):
        return ""
    if value in (".", ".."):
        return ""
    return value


def _as_hex64(value: object) -> str:
    if not isinstance(value, str):
        return ""
    if _HEX64_RE.fullmatch(value) is None:
        return ""
    return value.lower()


def _check_sources(raw, path: Path) -> list[dict]:
    if not isinstance(raw, list) or len(raw) == 0:
        _input_error("invalid spec sources: %s" % path)
    sources: list[dict] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict) or set(entry) != _SOURCE_KEYS:
            _input_error("invalid spec sources: %s" % path)
        sid = _as_name(entry.get("id"))
        n_bytes = _as_positive_int(entry.get("bytes"))
        n_words = _as_positive_int(entry.get("words"))
        digest = _as_hex64(entry.get("sha256"))
        if sid == "" or n_bytes is None or n_words is None or digest == "":
            _input_error("invalid spec sources: %s" % path)
        if sid in seen:
            _input_error("invalid spec sources: %s" % path)
        seen.add(sid)
        sources.append(
            {"id": sid, "bytes": n_bytes, "words": n_words, "sha256": digest}
        )
    return sources


def _check_operation(raw, path: Path) -> dict:
    if not isinstance(raw, dict) or set(raw) != _OPERATION_KEYS:
        _input_error("invalid spec operation: %s" % path)
    context = _as_positive_int(raw.get("current_context"))
    if context is None:
        _input_error("invalid spec operation: %s" % path)
    raw_profiles = raw.get("profiles")
    if not isinstance(raw_profiles, dict) or len(raw_profiles) == 0:
        _input_error("invalid spec operation: %s" % path)
    profiles: dict[str, list[str]] = {}
    for name, effects in raw_profiles.items():
        if _ID_RE.fullmatch(name) is None:
            _input_error("invalid spec profile: %s" % path)
        if (
            not isinstance(effects, list)
            or len(effects) == 0
            or any(effect not in _EFFECTS for effect in effects)
            or len(set(effects)) != len(effects)
        ):
            _input_error("invalid spec profile: %s" % path)
        profiles[name] = list(effects)
    return {"current_context": context, "profiles": profiles}


def _check_limits(raw, path: Path) -> dict:
    if not isinstance(raw, dict) or set(raw) != _LIMIT_KEYS:
        _input_error("invalid spec limits: %s" % path)
    n_bytes = _as_positive_int(raw.get("task_bytes_max"))
    n_words = _as_positive_int(raw.get("task_words_max"))
    if n_bytes is None or n_words is None:
        _input_error("invalid spec limits: %s" % path)
    return {"task_bytes_max": n_bytes, "task_words_max": n_words}


def _check_relation(raw, task_ids: list[str], path: Path):
    if raw is None:
        return None
    if not isinstance(raw, dict):
        _input_error("invalid spec relation: %s" % path)
    kind = raw.get("kind")
    if kind not in _RELATIONS:
        _input_error("invalid spec relation: %s" % path)
    if kind == "correction_dependency":
        if set(raw) != {"kind", "from", "to"}:
            _input_error("invalid spec relation: %s" % path)
        source = raw.get("from")
        target = raw.get("to")
        if (
            source not in task_ids
            or target not in task_ids
            or source == target
        ):
            _input_error("invalid spec relation: %s" % path)
        return {"kind": kind, "from": source, "to": target}
    extra = set(raw) - {"kind", "writer", "items"}
    if extra:
        _input_error("invalid spec relation: %s" % path)
    writer = raw.get("writer")
    if writer not in task_ids:
        _input_error("invalid spec relation: %s" % path)
    raw_items = raw.get("items")
    items: dict[str, str] = {}
    if raw_items is not None:
        if not isinstance(raw_items, dict) or len(raw_items) == 0:
            _input_error("invalid spec relation: %s" % path)
        for item_id, text in raw_items.items():
            if _ITEM_RE.fullmatch(item_id) is None:
                _input_error("invalid spec relation: %s" % path)
            if not isinstance(text, str) or text.strip() == "":
                _input_error("invalid spec relation: %s" % path)
            items[item_id] = text
    return {"kind": kind, "writer": writer, "items": items}


def _check_cases(
    raw,
    sources: dict[str, dict],
    profiles: dict[str, list[str]],
    context: int,
    path: Path,
) -> list[dict]:
    if not isinstance(raw, list) or len(raw) == 0:
        _input_error("invalid spec cases: %s" % path)
    cases: list[dict] = []
    seen_cases: set[str] = set()
    seen_tasks: set[str] = set()
    seen_items: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            _input_error("invalid spec cases: %s" % path)
        if not set(entry).issubset(_CASE_KEYS | {"relation"}) or not _CASE_KEYS.issubset(
            set(entry)
        ):
            _input_error("invalid spec cases: %s" % path)
        case_id = _as_nonempty_str(entry.get("id"))
        if case_id == "" or _CASE_RE.fullmatch(case_id) is None:
            _input_error("invalid spec cases: %s" % path)
        if case_id in seen_cases:
            _input_error("invalid spec cases: %s" % path)
        seen_cases.add(case_id)
        shape = _as_nonempty_str(entry.get("shape"))
        if shape == "":
            _input_error("invalid spec cases: %s" % path)
        raw_originals = entry.get("original_source_ids")
        if not isinstance(raw_originals, list) or len(raw_originals) == 0:
            _input_error("invalid spec cases: %s" % path)
        originals: list[str] = []
        for sid in raw_originals:
            if sid not in sources or sid in originals:
                _input_error("invalid spec cases: %s" % path)
            originals.append(sid)
        raw_required = entry.get("required_items")
        if not isinstance(raw_required, list) or len(raw_required) == 0:
            _input_error("invalid spec cases: %s" % path)
        required: list[str] = []
        for item_id in raw_required:
            if _ITEM_RE.fullmatch(item_id) is None or item_id in required:
                _input_error("invalid spec cases: %s" % path)
            if item_id in seen_items:
                _input_error("invalid spec cases: %s" % path)
            seen_items.add(item_id)
            required.append(item_id)
        raw_tasks = entry.get("tasks")
        if not isinstance(raw_tasks, list) or len(raw_tasks) == 0:
            _input_error("invalid spec cases: %s" % path)
        tasks: list[dict] = []
        for task in raw_tasks:
            if not isinstance(task, dict) or set(task) != _TASK_KEYS:
                _input_error("invalid spec cases: %s" % path)
            task_id = task.get("id")
            if _ID_RE.fullmatch(task_id or "") is None or task_id in seen_tasks:
                _input_error("invalid spec cases: %s" % path)
            seen_tasks.add(task_id)
            kind = task.get("kind")
            effect = task.get("effect")
            profile = task.get("profile")
            if kind not in _KINDS or effect not in _EFFECTS:
                _input_error("invalid spec cases: %s" % path)
            if profile not in profiles or effect not in profiles[profile]:
                _input_error("invalid spec cases: %s" % path)
            task_context = _as_positive_int(task.get("context"))
            if task_context is None or task_context > context:
                _input_error("invalid spec cases: %s" % path)
            depends = task.get("depends")
            if (
                not isinstance(depends, list)
                or any(_ID_RE.fullmatch(dep or "") is None for dep in depends)
                or len(set(depends)) != len(depends)
                or task_id in depends
            ):
                _input_error("invalid spec cases: %s" % path)
            raw_sections = task.get("sections")
            if not isinstance(raw_sections, list) or len(raw_sections) == 0:
                _input_error("invalid spec cases: %s" % path)
            sections: list[dict] = []
            fields: list[str] = []
            for section in raw_sections:
                if not isinstance(section, dict) or set(section) != _SECTION_KEYS:
                    _input_error("invalid spec cases: %s" % path)
                field = section.get("field")
                heading = _as_nonempty_str(section.get("heading"))
                text = _as_nonempty_str(section.get("text"))
                if _FIELD_RE.fullmatch(field or "") is None or field in fields:
                    _input_error("invalid spec cases: %s" % path)
                if heading == "" or text == "":
                    _input_error("invalid spec cases: %s" % path)
                fields.append(field)
                sections.append({"field": field, "heading": heading, "text": text})
            raw_items = task.get("items")
            if not isinstance(raw_items, dict) or len(raw_items) == 0:
                _input_error("invalid spec cases: %s" % path)
            items: dict[str, str] = {}
            for item_id, field in raw_items.items():
                if _ITEM_RE.fullmatch(item_id) is None:
                    _input_error("invalid spec cases: %s" % path)
                if not isinstance(field, str) or field not in fields:
                    _input_error("invalid spec cases: %s" % path)
                items[item_id] = field
            tasks.append(
                {
                    "id": task_id,
                    "kind": kind,
                    "effect": effect,
                    "profile": profile,
                    "context": task_context,
                    "depends": list(depends),
                    "sections": sections,
                    "items": items,
                }
            )
        task_ids = [task["id"] for task in tasks]
        for task in tasks:
            unknown = sorted(set(task["depends"]) - set(task_ids))
            if unknown:
                _input_error("invalid spec cases: %s" % path)
        _reject_cycles(
            {task["id"]: task["depends"] for task in tasks}, path
        )
        relation = _check_relation(entry.get("relation"), task_ids, path)
        if relation is not None:
            by_id = {task["id"]: task for task in tasks}
            if relation["kind"] == "correction_dependency":
                if by_id[relation["from"]]["depends"] != [relation["to"]]:
                    _input_error("invalid spec relation: %s" % path)
            else:
                mutating = [task["id"] for task in tasks if task["effect"] == "mutating"]
                if (
                    mutating != [relation["writer"]]
                    or any(task["depends"] for task in tasks)
                ):
                    _input_error("invalid spec relation: %s" % path)
        matched = dict.fromkeys(required, False)
        for task in tasks:
            for item_id in task["items"]:
                if item_id not in matched:
                    _input_error("invalid spec cases: %s" % path)
                matched[item_id] = True
        relation_items: list[str] = []
        if relation is not None and relation["kind"] == "parallel_independence":
            relation_items = list(relation["items"])
            for item_id in relation_items:
                if item_id not in matched:
                    _input_error("invalid spec cases: %s" % path)
                matched[item_id] = True
        if not all(matched.values()):
            _input_error("invalid spec cases: %s" % path)
        cases.append(
            {
                "id": case_id,
                "shape": shape,
                "original_source_ids": originals,
                "required_items": required,
                "tasks": tasks,
                "relation": relation,
            }
        )
    return cases


def _reject_cycles(graph: dict[str, list[str]], path: Path) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            _input_error("dependency cycle in spec: %s" % path)
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)


def check_spec(data: dict, path: Path) -> dict:
    if data.get("format") != SPEC_FORMAT:
        _input_error("invalid spec format: %s" % path)
    if set(data) != _SPEC_KEYS:
        _input_error("invalid spec format: %s" % path)
    operation = _check_operation(data.get("operation"), path)
    limits = _check_limits(data.get("limits"), path)
    sources = _check_sources(data.get("sources"), path)
    by_id = {source["id"]: source for source in sources}
    cases = _check_cases(
        data.get("cases"), by_id, operation["profiles"], operation["current_context"], path
    )
    return {
        "operation": operation,
        "limits": limits,
        "sources": sources,
        "cases": cases,
    }


def order_tasks(cases: list[dict]) -> list[dict]:
    remaining = [dict(task, case_id=case["id"]) for case in cases for task in case["tasks"]]
    placed: set[str] = set()
    ordered: list[dict] = []
    while remaining:
        for task in list(remaining):
            if all(dependency in placed for dependency in task["depends"]):
                ordered.append(task)
                remaining.remove(task)
                placed.add(task["id"])
                break
        else:  # pragma: no cover - check_spec already rejects cycles
            _input_error("dependency cycle in spec")
    return ordered


def render_task(task: dict) -> bytes:
    lines = [
        "+++",
        'id="%s"' % task["id"],
        'kind="%s"' % task["kind"],
        'effect="%s"' % task["effect"],
        'profile="%s"' % task["profile"],
        "context=%d" % task["context"],
        "depends=[%s]" % ", ".join('"%s"' % dep for dep in task["depends"]),
        "+++",
        "",
    ]
    for section in task["sections"]:
        lines.append("## %s" % section["heading"])
        lines.append("")
        lines.append(section["text"])
        lines.append("")
    return "\n".join(lines).encode("utf-8")


def measure_task(raw: bytes) -> tuple[int, int]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        _input_error("generated task is not valid utf-8")
    return len(raw), len(_WORD_RE.findall(text))


def _load_control():
    try:
        import _om_control

        return _om_control
    except ImportError:
        path = Path(__file__).resolve().parent / "_om_control.py"
        spec = importlib.util.spec_from_file_location("_om_control", path)
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def validate_generated(operation: dict, ordered: list[dict]) -> dict:
    control = _load_control()
    failed: list[str] = []
    with tempfile.TemporaryDirectory(prefix="om-replay-") as tmp:
        root = Path(tmp)
        lines = [
            'format = "%s"' % OPERATION_FORMAT,
            'id = "replay-validation"',
            'project_root = "%s"' % root.as_posix(),
            "current_context = %d" % operation["current_context"],
            "",
        ]
        for name in sorted(operation["profiles"]):
            lines.append("[profiles.%s]" % name)
            lines.append(
                "effects = [%s]"
                % ", ".join('"%s"' % effect for effect in operation["profiles"][name])
            )
            lines.append("")
        try:
            (root / "operation.toml").write_text(
                "\n".join(lines), encoding="utf-8", newline="\n"
            )
            drafts = root / ".drafts"
            drafts.mkdir()
            for task in ordered:
                draft = drafts / ("%s.md" % task["id"])
                draft.write_bytes(render_task(task))
                with contextlib.redirect_stdout(io.StringIO()):
                    code = control.run_task_publish(
                        argparse.Namespace(operation=str(root), task=str(draft))
                    )
                if code != 0:
                    failed.append(task["id"])
            with contextlib.redirect_stdout(io.StringIO()):
                doctor = control.run_doctor(argparse.Namespace(operation=str(root)))
        except OSError:
            _input_error("cannot stage generated tasks for validation")
    return {
        "tasks": len(ordered),
        "ok": len(ordered) - len(failed),
        "failed": sorted(failed),
        "doctor": "ok" if doctor == 0 else "failed",
    }


def _summed(records: list[dict]) -> dict:
    return {
        "files": len(records),
        "bytes": sum(record["bytes"] for record in records),
        "words": sum(record["words"] for record in records),
    }


def _reduction(original: int, generated: int) -> float:
    return (original - generated) / original * 100.0


def build_report(
    spec: dict, spec_sha256: str, ordered: list[dict], validation: dict
) -> dict:
    sources = {source["id"]: source for source in spec["sources"]}
    measured = {task["id"]: measure_task(render_task(task)) for task in ordered}
    failed = set(validation["failed"])
    limits = spec["limits"]
    cases_doc: list[dict] = []
    required_total = 0
    mapped_total = 0
    missing_total: list[str] = []
    bytes_total = 0
    words_total = 0
    task_total = 0
    for case in spec["cases"]:
        originals = [sources[sid] for sid in case["original_source_ids"]]
        original_sum = _summed(originals)
        cases_items: dict[str, dict] = {}
        for task in case["tasks"]:
            for item_id, field in task["items"].items():
                cases_items[item_id] = {"task": task["id"], "field": field}
        relation = case["relation"]
        if relation is not None and relation["kind"] == "parallel_independence":
            for item_id in relation["items"]:
                cases_items[item_id] = {"relation": relation["kind"]}
        missing = [item for item in case["required_items"] if item not in cases_items]
        mapped = [item for item in case["required_items"] if item in cases_items]
        required_total += len(case["required_items"])
        mapped_total += len(mapped)
        missing_total.extend(missing)
        tasks_doc: list[dict] = []
        for task in case["tasks"]:
            n_bytes, n_words = measured[task["id"]]
            bytes_total += n_bytes
            words_total += n_words
            task_total += 1
            tasks_doc.append(
                {
                    "id": task["id"],
                    "kind": task["kind"],
                    "effect": task["effect"],
                    "profile": task["profile"],
                    "context": task["context"],
                    "depends": list(task["depends"]),
                    "bytes": n_bytes,
                    "words": n_words,
                    "within_limits": n_bytes <= limits["task_bytes_max"]
                    and n_words <= limits["task_words_max"],
                    "validation": "failed" if task["id"] in failed else "ok",
                    "mapped_items": [
                        item
                        for item in mapped
                        if cases_items[item].get("task") == task["id"]
                    ],
                    "missing_items": list(missing),
                }
            )
        generated_sum = {
            "files": len(case["tasks"]),
            "bytes": sum(measured[task["id"]][0] for task in case["tasks"]),
            "words": sum(measured[task["id"]][1] for task in case["tasks"]),
        }
        relation_doc = None
        if relation is not None:
            if relation["kind"] == "correction_dependency":
                relation_doc = {
                    "kind": relation["kind"],
                    "verified": True,
                    "items": [],
                    "from": relation["from"],
                    "to": relation["to"],
                }
            else:
                relation_doc = {
                    "kind": relation["kind"],
                    "verified": True,
                    "items": sorted(relation["items"]),
                    "writer": relation["writer"],
                    "independent": all(
                        not task["depends"] for task in case["tasks"]
                    ),
                    "read_only": [
                        task["id"]
                        for task in case["tasks"]
                        if task["effect"] == "read-only"
                    ],
                    "details": [
                        {"id": item, "text": relation["items"][item]}
                        for item in sorted(relation["items"])
                    ],
                }
        cases_doc.append(
            {
                "id": case["id"],
                "shape": case["shape"],
                "original_sources": list(case["original_source_ids"]),
                "original": original_sum,
                "generated": generated_sum,
                "reduction_percent": {
                    "bytes": _reduction(original_sum["bytes"], generated_sum["bytes"]),
                    "words": _reduction(original_sum["words"], generated_sum["words"]),
                },
                "tasks": tasks_doc,
                "relation": relation_doc,
            }
        )
    average_bytes = bytes_total / task_total if task_total else 0.0
    average_words = words_total / task_total if task_total else 0.0
    return {
        "format": REPORT_FORMAT,
        "spec_sha256": spec_sha256,
        "algorithm": dict(ALGORITHM),
        "limits": dict(limits),
        "sources": [sources[source["id"]] for source in spec["sources"]],
        "cases": cases_doc,
        "coverage": {
            "required": required_total,
            "mapped": mapped_total,
            "missing": sorted(missing_total),
            "percent": (
                100.0 * mapped_total / required_total if required_total else 0.0
            ),
        },
        "average_task": {
            "bytes": average_bytes,
            "words": average_words,
            "within_limits": average_bytes <= limits["task_bytes_max"]
            and average_words <= limits["task_words_max"],
        },
        "validation": dict(validation),
        "provenance": {
            "note": PROVENANCE_NOTE,
            "spec_sha256": spec_sha256,
        },
    }


def _check_report(data: dict, path: Path) -> dict:
    if set(data) != _REPORT_KEYS or data.get("format") != REPORT_FORMAT:
        _input_error("invalid baseline format: %s" % path)
    if _as_hex64(data.get("spec_sha256")) == "":
        _input_error("invalid baseline format: %s" % path)
    for key in ("algorithm", "limits", "coverage", "average_task", "validation", "provenance"):
        if not isinstance(data.get(key), dict):
            _input_error("invalid baseline format: %s" % path)
    for key in ("sources", "cases"):
        if not isinstance(data.get(key), list) or len(data[key]) == 0:
            _input_error("invalid baseline format: %s" % path)
    return data


def run_benchmark_replay(args) -> int:
    spec_path = Path(str(args.spec))
    baseline_path = Path(str(args.baseline))
    spec_raw = _read_bytes(spec_path, "spec")
    spec_sha256 = hashlib.sha256(spec_raw).hexdigest().lower()
    spec = check_spec(_parse_json(spec_raw, spec_path, "spec"), spec_path)
    baseline = _check_report(
        _parse_json(_read_bytes(baseline_path, "baseline"), baseline_path, "baseline"),
        baseline_path,
    )
    if baseline["spec_sha256"].lower() != spec_sha256:
        _input_error("spec seal mismatch")
    ordered = order_tasks(spec["cases"])
    validation = validate_generated(spec["operation"], ordered)
    document = build_report(spec, spec_sha256, ordered, validation)
    sys.stdout.write(
        json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    )
    if validation["failed"] or validation["doctor"] != "ok":
        sys.stderr.write("om: replay validation failed\n")
        return 1
    over = [task["id"] for case in document["cases"] for task in case["tasks"] if not task["within_limits"]]
    if over or not document["average_task"]["within_limits"]:
        sys.stderr.write(
            "om: replay exceeds task limits: %s\n" % ", ".join(sorted(over) or ["average"])
        )
        return 1
    for key in (
        "format",
        "spec_sha256",
        "algorithm",
        "limits",
        "sources",
        "cases",
        "coverage",
        "average_task",
        "validation",
        "provenance",
    ):
        if baseline.get(key) != document[key]:
            sys.stderr.write("om: mismatch: %s differs\n" % key)
            return 1
    return 0

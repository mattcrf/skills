"""Private report library (deterministic Phase A cost baseline)."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPORT_FORMAT_ID = "om-report/1"
SPEC_FORMAT_ID = "om-report-spec/1"
LEGACY_FORMAT_ID = "om-benchmark-legacy/1"
QUALITY_FORMAT_ID = "om-benchmark-quality/1"

_HEX64_RE = re.compile(r"[0-9a-fA-F]{64}")


def _report_error(message: str) -> "NoReturn":  # type: ignore[name-defined]
    sys.stderr.write("om: report error: %s\n" % message)
    raise SystemExit(2)


def _read_raw(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        _report_error("unreadable %s: %s" % (label, path))


def _parse_json(raw: bytes, path: Path, label: str) -> dict:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        _report_error("invalid %s format: %s" % (label, path))
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        _report_error("invalid %s format: %s" % (label, path))
    if not isinstance(data, dict):
        _report_error("invalid %s format: %s" % (label, path))
    return data


def _is_relative_id(value: object) -> bool:
    if not isinstance(value, str) or value == "":
        return False
    if value.startswith("/") or value.startswith("\\"):
        return False
    if ":" in value or "\\" in value:
        return False
    parts = value.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        return False
    if any(p == "" for p in parts):
        return False
    return True


def _require_hex64(value: object) -> str:
    if not isinstance(value, str):
        return ""
    if not _HEX64_RE.fullmatch(value):
        return ""
    return value.lower()


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


def _validate_spec(data: dict, path: Path) -> dict:
    if data.get("format") != SPEC_FORMAT_ID:
        _report_error("invalid spec format: %s" % path)
    legacy_id = data.get("legacy_id")
    quality_id = data.get("quality_id")
    legacy_sha = data.get("legacy_sha256")
    quality_sha = data.get("quality_sha256")
    if not _is_relative_id(legacy_id):
        _report_error("invalid spec legacy id: %s" % path)
    if not _is_relative_id(quality_id):
        _report_error("invalid spec quality id: %s" % path)
    legacy_hex = _require_hex64(legacy_sha)
    quality_hex = _require_hex64(quality_sha)
    if not legacy_hex:
        _report_error("invalid spec legacy seal: %s" % path)
    if not quality_hex:
        _report_error("invalid spec quality seal: %s" % path)

    technical = data.get("technical")
    overhead = data.get("overhead")
    if not isinstance(technical, dict) or not isinstance(overhead, dict):
        _report_error("invalid spec format: %s" % path)
    authored_cat = _as_nonempty_str(technical.get("authored_requests_category"))
    received_cat = _as_nonempty_str(technical.get("received_returns_category"))
    dispatch_cat = _as_nonempty_str(overhead.get("dispatch_category"))
    execution_cat = _as_nonempty_str(overhead.get("execution_category"))
    handoff_cat = _as_nonempty_str(overhead.get("handoff_category"))
    cats = [authored_cat, received_cat, dispatch_cat, execution_cat, handoff_cat]
    if any(c == "" for c in cats):
        _report_error("invalid spec format: %s" % path)
    if len(set(cats)) != len(cats):
        _report_error("incoherent spec categories: %s" % path)
    for c in cats:
        if not _is_relative_id(c) and "/" in c:
            _report_error("invalid spec category: %s" % path)

    replay = data.get("replay_slice")
    if not isinstance(replay, dict):
        _report_error("invalid spec format: %s" % path)
    slice_id = _as_nonempty_str(replay.get("id"))
    req_paths = replay.get("request_paths")
    ret_paths = replay.get("return_paths")
    if slice_id == "":
        _report_error("invalid spec format: %s" % path)
    if not isinstance(req_paths, list) or not isinstance(ret_paths, list):
        _report_error("invalid spec format: %s" % path)
    if len(req_paths) == 0 or len(ret_paths) == 0:
        _report_error("incoherent spec slice: %s" % path)
    for lst in (req_paths, ret_paths):
        for item in lst:
            if not _is_relative_id(item):
                _report_error("invalid spec slice path: %s" % path)
    all_slice = list(req_paths) + list(ret_paths)
    if len(set(all_slice)) != len(all_slice):
        _report_error("incoherent spec slice: %s" % path)

    budgets = data.get("budgets")
    if not isinstance(budgets, dict):
        _report_error("invalid spec format: %s" % path)
    b_authored = _as_positive_int(budgets.get("authored_requests_words_max"))
    b_received = _as_positive_int(budgets.get("received_returns_words_max"))
    b_combined = _as_positive_int(budgets.get("combined_words_max"))
    b_packet = _as_positive_int(budgets.get("decision_packet_words_avg_max"))
    b_capsule = _as_positive_int(budgets.get("resume_capsule_words_max"))
    b_context = _as_positive_int(budgets.get("captain_fixed_context_words_max"))
    if (
        b_authored is None
        or b_received is None
        or b_combined is None
        or b_packet is None
        or b_capsule is None
        or b_context is None
    ):
        _report_error("incoherent spec budget: %s" % path)
    assert b_authored is not None and b_received is not None and b_combined is not None
    if b_combined != b_authored + b_received:
        _report_error("incoherent spec budget: %s" % path)

    raw_unrec = data.get("unrecoverable")
    if not isinstance(raw_unrec, list) or len(raw_unrec) == 0:
        _report_error("invalid spec format: %s" % path)
    seen: set[str] = set()
    unrec: list[dict] = []
    for entry in raw_unrec:
        if not isinstance(entry, dict):
            _report_error("invalid spec format: %s" % path)
        uid = _as_nonempty_str(entry.get("id"))
        reason = _as_nonempty_str(entry.get("reason"))
        if uid == "" or reason == "":
            _report_error("invalid spec format: %s" % path)
        if uid in seen:
            _report_error("invalid spec format: %s" % path)
        seen.add(uid)
        for forbidden in ("words", "bytes", "value", "count"):
            if forbidden in entry:
                _report_error("invalid spec unrecoverable: %s" % path)
        unrec.append({"id": uid, "reason": reason})
    unrec.sort(key=lambda r: r["id"])

    return {
        "legacy_id": legacy_id,
        "quality_id": quality_id,
        "legacy_sha256": legacy_hex,
        "quality_sha256": quality_hex,
        "authored_category": authored_cat,
        "received_category": received_cat,
        "dispatch_category": dispatch_cat,
        "execution_category": execution_cat,
        "handoff_category": handoff_cat,
        "slice_id": slice_id,
        "slice_requests": list(req_paths),
        "slice_returns": list(ret_paths),
        "budgets": {
            "authored_requests_words_max": b_authored,
            "received_returns_words_max": b_received,
            "combined_words_max": b_combined,
            "decision_packet_words_avg_max": b_packet,
            "resume_capsule_words_max": b_capsule,
            "captain_fixed_context_words_max": b_context,
        },
        "unrecoverable": unrec,
    }


def _validate_legacy(data: dict, path: Path) -> dict:
    if data.get("format") != LEGACY_FORMAT_ID:
        _report_error("invalid legacy format: %s" % path)
    aggregates = data.get("aggregates")
    files = data.get("files")
    manifest = data.get("manifest")
    algorithm = data.get("manifest_algorithm")
    if not isinstance(aggregates, dict):
        _report_error("invalid legacy format: %s" % path)
    if not isinstance(files, list):
        _report_error("invalid legacy format: %s" % path)
    if not isinstance(manifest, str) or manifest == "":
        _report_error("invalid legacy format: %s" % path)
    if not isinstance(algorithm, str) or algorithm == "":
        _report_error("invalid legacy format: %s" % path)
    by_path: dict[str, dict] = {}
    by_category: dict[str, list[dict]] = {}
    for entry in files:
        if not isinstance(entry, dict):
            _report_error("invalid legacy format: %s" % path)
        rel = entry.get("path")
        category = entry.get("category")
        flow = entry.get("flow")
        n_bytes = entry.get("bytes")
        n_words = entry.get("words")
        n_lines = entry.get("lines")
        digest = entry.get("sha256")
        if not _is_relative_id(rel):
            _report_error("invalid legacy format: %s" % path)
        if not isinstance(category, str) or category == "":
            _report_error("invalid legacy format: %s" % path)
        if not isinstance(flow, str) or flow == "":
            _report_error("invalid legacy format: %s" % path)
        for num in (n_bytes, n_words, n_lines):
            if isinstance(num, bool) or not isinstance(num, int) or num < 0:
                _report_error("invalid legacy format: %s" % path)
        if not _require_hex64(digest):
            _report_error("invalid legacy format: %s" % path)
        assert isinstance(rel, str)
        if rel in by_path:
            _report_error("invalid legacy format: %s" % path)
        record = {
            "path": rel,
            "category": category,
            "flow": flow,
            "bytes": n_bytes,
            "words": n_words,
            "lines": n_lines,
            "sha256": str(digest).lower(),
        }
        by_path[rel] = record
        by_category.setdefault(str(category), []).append(record)
    return {
        "aggregates": aggregates,
        "by_path": by_path,
        "by_category": by_category,
        "manifest": manifest,
        "manifest_algorithm": algorithm,
        "format": data.get("format"),
    }


def _validate_quality(data: dict, path: Path) -> dict:
    if data.get("format") != QUALITY_FORMAT_ID:
        _report_error("invalid quality format: %s" % path)
    raw_cases = data.get("cases")
    raw_oracles = data.get("oracles")
    if not isinstance(raw_cases, list) or not isinstance(raw_oracles, list):
        _report_error("invalid quality format: %s" % path)
    cases: dict[str, dict] = {}
    for entry in raw_cases:
        if not isinstance(entry, dict):
            _report_error("invalid quality format: %s" % path)
        case_id = entry.get("case_id")
        req_ids = entry.get("required_oracle_ids")
        if not isinstance(case_id, str) or case_id == "":
            _report_error("invalid quality format: %s" % path)
        if case_id in cases:
            _report_error("invalid quality format: %s" % path)
        if not isinstance(req_ids, list):
            _report_error("invalid quality format: %s" % path)
        ids: list[str] = []
        for item in req_ids:
            if not isinstance(item, str) or item == "":
                _report_error("invalid quality format: %s" % path)
            ids.append(item)
        if len(set(ids)) != len(ids):
            _report_error("invalid quality format: %s" % path)
        cases[case_id] = {"required_oracle_ids": sorted(ids)}
    oracles: dict[str, dict] = {}
    for entry in raw_oracles:
        if not isinstance(entry, dict):
            _report_error("invalid quality format: %s" % path)
        oid = entry.get("id")
        case_id = entry.get("case_id")
        severity = entry.get("severity")
        claim = entry.get("claim")
        if (
            not isinstance(oid, str)
            or oid == ""
            or not isinstance(case_id, str)
            or case_id == ""
            or not isinstance(severity, str)
            or severity == ""
            or not isinstance(claim, str)
            or claim == ""
        ):
            _report_error("invalid quality format: %s" % path)
        assert isinstance(oid, str) and isinstance(case_id, str)
        if oid in oracles:
            _report_error("invalid quality format: %s" % path)
        if case_id not in cases:
            _report_error("invalid quality format: %s" % path)
        oracles[oid] = {"case_id": case_id, "severity": severity}
    for case_id, record in cases.items():
        for req_id in record["required_oracle_ids"]:
            target = oracles.get(req_id)
            if target is None:
                _report_error("invalid quality format: %s" % path)
            assert target is not None
            if target["case_id"] != case_id:
                _report_error("invalid quality format: %s" % path)
    return {"cases": cases, "oracles": oracles, "format": data.get("format")}


def _sum_records(records: list[dict]) -> dict:
    return {
        "files": len(records),
        "words": sum(int(r["words"]) for r in records),
        "bytes": sum(int(r["bytes"]) for r in records),
    }


def build_report(
    legacy: dict, quality: dict, spec: dict, seals: dict
) -> dict:
    by_category = legacy["by_category"]
    by_path = legacy["by_path"]

    for key in (
        "authored_category",
        "received_category",
        "dispatch_category",
        "execution_category",
        "handoff_category",
    ):
        category = spec[key]
        if category not in by_category:
            _report_error("missing category in legacy: %s" % category)

    authored_records = by_category[spec["authored_category"]]
    received_records = by_category[spec["received_category"]]
    dispatch_records = by_category[spec["dispatch_category"]]
    execution_records = by_category[spec["execution_category"]]
    handoff_records = by_category[spec["handoff_category"]]

    authored_sum = _sum_records(authored_records)
    received_sum = _sum_records(received_records)
    dispatch_sum = _sum_records(dispatch_records)
    execution_sum = _sum_records(execution_records)
    handoff_sum = _sum_records(handoff_records)

    combined_words = authored_sum["words"] + received_sum["words"]
    combined_bytes = authored_sum["bytes"] + received_sum["bytes"]
    known_words = (
        authored_sum["words"]
        + received_sum["words"]
        + dispatch_sum["words"]
        + execution_sum["words"]
        + handoff_sum["words"]
    )
    known_bytes = (
        authored_sum["bytes"]
        + received_sum["bytes"]
        + dispatch_sum["bytes"]
        + execution_sum["bytes"]
        + handoff_sum["bytes"]
    )

    slice_req_records: list[dict] = []
    for rel in spec["slice_requests"]:
        record = by_path.get(rel)
        if record is None:
            _report_error("missing slice path in legacy: %s" % rel)
        assert record is not None
        if record["category"] != spec["authored_category"]:
            _report_error("incoherent slice path: %s" % rel)
        slice_req_records.append(record)
    slice_ret_records: list[dict] = []
    for rel in spec["slice_returns"]:
        record = by_path.get(rel)
        if record is None:
            _report_error("missing slice path in legacy: %s" % rel)
        assert record is not None
        if record["category"] != spec["received_category"]:
            _report_error("incoherent slice path: %s" % rel)
        slice_ret_records.append(record)
    slice_req_sum = _sum_records(slice_req_records)
    slice_ret_sum = _sum_records(slice_ret_records)
    slice_combined_words = slice_req_sum["words"] + slice_ret_sum["words"]
    slice_combined_bytes = slice_req_sum["bytes"] + slice_ret_sum["bytes"]

    required_ids = sorted(
        {
            oid
            for record in quality["cases"].values()
            for oid in record["required_oracle_ids"]
        }
    )
    control_ids = sorted(
        [
            case_id
            for case_id, record in quality["cases"].items()
            if len(record["required_oracle_ids"]) == 0
        ]
    )

    budgets = spec["budgets"]
    if authored_sum["words"] <= 0 or received_sum["words"] <= 0:
        _report_error("incoherent legacy baseline")
    if combined_words <= 0:
        _report_error("incoherent legacy baseline")

    def _reduction(baseline: int, target: int) -> float:
        return (baseline - target) / baseline * 100.0

    reductions = {
        "authored_requests": _reduction(
            authored_sum["words"], budgets["authored_requests_words_max"]
        ),
        "received_returns": _reduction(
            received_sum["words"], budgets["received_returns_words_max"]
        ),
        "combined": _reduction(combined_words, budgets["combined_words_max"]),
    }

    unrecoverable = [
        {"id": item["id"], "status": "unrecoverable", "reason": item["reason"]}
        for item in spec["unrecoverable"]
    ]

    document = {
        "format": REPORT_FORMAT_ID,
        "inputs": {
            "legacy_format": legacy["format"],
            "legacy_id": spec["legacy_id"],
            "legacy_manifest": legacy["manifest"],
            "legacy_manifest_algorithm": legacy["manifest_algorithm"],
            "legacy_sha256": seals["legacy_sha256"],
            "quality_format": quality["format"],
            "quality_id": spec["quality_id"],
            "quality_sha256": seals["quality_sha256"],
            "spec_format": SPEC_FORMAT_ID,
            "spec_sha256": seals["spec_sha256"],
        },
        "full_operation_lower_bound": {
            "note": (
                "Known technical lower bound from authored requests and "
                "received returns. Word counts use whitespace separation. "
                "They exclude re-reads, diffs, logs and chat."
            ),
            "authored_requests": {
                "category": spec["authored_category"],
                "files": authored_sum["files"],
                "words": authored_sum["words"],
                "bytes": authored_sum["bytes"],
            },
            "received_returns": {
                "category": spec["received_category"],
                "files": received_sum["files"],
                "words": received_sum["words"],
                "bytes": received_sum["bytes"],
            },
            "combined": {"words": combined_words, "bytes": combined_bytes},
        },
        "textual_overhead": {
            "note": (
                "Operational and handoff words kept separate from the "
                "technical lower bound; never merged silently."
            ),
            "dispatch": {
                "category": spec["dispatch_category"],
                "files": dispatch_sum["files"],
                "words": dispatch_sum["words"],
                "bytes": dispatch_sum["bytes"],
            },
            "execution": {
                "category": spec["execution_category"],
                "files": execution_sum["files"],
                "words": execution_sum["words"],
                "bytes": execution_sum["bytes"],
            },
            "handoff": {
                "category": spec["handoff_category"],
                "files": handoff_sum["files"],
                "words": handoff_sum["words"],
                "bytes": handoff_sum["bytes"],
            },
            "known_textual_total": {"words": known_words, "bytes": known_bytes},
        },
        "replay_slice": {
            "id": spec["slice_id"],
            "note": (
                "Denominator of the historical replay only; not the global "
                "target and not proof of the full operation."
            ),
            "requests": {
                "paths": sorted(spec["slice_requests"]),
                "files": slice_req_sum["files"],
                "words": slice_req_sum["words"],
                "bytes": slice_req_sum["bytes"],
            },
            "returns": {
                "paths": sorted(spec["slice_returns"]),
                "files": slice_ret_sum["files"],
                "words": slice_ret_sum["words"],
                "bytes": slice_ret_sum["bytes"],
            },
            "combined": {
                "words": slice_combined_words,
                "bytes": slice_combined_bytes,
            },
        },
        "frozen_quality": {
            "note": "Identifiers only; claims are omitted.",
            "required_blocking_ids": required_ids,
            "required_blocking_count": len(required_ids),
            "control_case_ids": control_ids,
            "control_count": len(control_ids),
        },
        "unrecoverable": unrecoverable,
        "budgets": {
            "authored_requests_words_max": budgets["authored_requests_words_max"],
            "received_returns_words_max": budgets["received_returns_words_max"],
            "combined_words_max": budgets["combined_words_max"],
            "decision_packet_words_avg_max": budgets[
                "decision_packet_words_avg_max"
            ],
            "resume_capsule_words_max": budgets["resume_capsule_words_max"],
            "captain_fixed_context_words_max": budgets[
                "captain_fixed_context_words_max"
            ],
            "note": "Version-two budgets for the full operation, taken from the specification.",
        },
        "reductions_percent": {
            "note": (
                "Computed as (baseline minus budget) divided by baseline "
                "times one hundred; never fixed text."
            ),
            "authored_requests": reductions["authored_requests"],
            "received_returns": reductions["received_returns"],
            "combined": reductions["combined"],
        },
        "provenance": {
            "note": (
                "Combined words are a known lower bound from surviving "
                "coordination files. They are not a subword-unit count and "
                "not the total captain work, which also involved code, "
                "diffs, logs, chat and re-reads."
            ),
            "legacy_manifest": legacy["manifest"],
            "legacy_sha256": seals["legacy_sha256"],
            "quality_sha256": seals["quality_sha256"],
            "spec_sha256": seals["spec_sha256"],
        },
    }
    return document


def run_benchmark_report(args) -> int:
    legacy_path = Path(str(args.legacy))
    quality_path = Path(str(args.quality))
    spec_path = Path(str(args.spec))

    legacy_raw = _read_raw(legacy_path, "legacy")
    quality_raw = _read_raw(quality_path, "quality")
    spec_raw = _read_raw(spec_path, "spec")

    legacy_sha = hashlib.sha256(legacy_raw).hexdigest()
    quality_sha = hashlib.sha256(quality_raw).hexdigest()
    spec_sha = hashlib.sha256(spec_raw).hexdigest()

    legacy_data = _parse_json(legacy_raw, legacy_path, "legacy")
    quality_data = _parse_json(quality_raw, quality_path, "quality")
    spec_data = _parse_json(spec_raw, spec_path, "spec")

    spec = _validate_spec(spec_data, spec_path)
    if spec["legacy_sha256"] != legacy_sha.lower():
        _report_error("legacy hash mismatch")
    if spec["quality_sha256"] != quality_sha.lower():
        _report_error("quality hash mismatch")

    legacy = _validate_legacy(legacy_data, legacy_path)
    quality = _validate_quality(quality_data, quality_path)

    seals = {
        "legacy_sha256": legacy_sha.lower(),
        "quality_sha256": quality_sha.lower(),
        "spec_sha256": spec_sha.lower(),
    }
    document = build_report(legacy, quality, spec, seals)
    rendered = (
        json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False)
        + "\n"
    )
    sys.stdout.write(rendered)
    return 0

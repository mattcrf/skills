"""Private quality benchmark library (adjudicated scoring only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

QUALITY_FORMAT_ID = "om-benchmark-quality/1"
CANDIDATE_FORMAT_ID = "om-candidate-quality/1"
SCORE_FORMAT_ID = "om-quality-score/1"


def _quality_format_error(message: str) -> "NoReturn":  # type: ignore[name-defined]
    sys.stderr.write("om: format error: %s\n" % message)
    raise SystemExit(2)


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _load_json_document(path: Path, label: str) -> dict:
    try:
        raw = path.read_bytes()
    except OSError:
        _quality_format_error("unreadable %s: %s" % (label, path))
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        _quality_format_error("invalid %s format: %s" % (label, path))
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        _quality_format_error("invalid %s format: %s" % (label, path))
    if not isinstance(data, dict):
        _quality_format_error("invalid %s format: %s" % (label, path))
    return data


def _as_str_list(value: object, label: str, path: Path) -> list[str]:
    if not isinstance(value, list):
        _quality_format_error("invalid %s format: %s" % (label, path))
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            _quality_format_error("invalid %s format: %s" % (label, path))
        out.append(item)
    return out


def _parse_anchor(value: object, label: str, path: Path) -> tuple[int, int]:
    if not isinstance(value, str):
        _quality_format_error("invalid %s format: %s" % (label, path))
    text = value.strip()
    if "-" in text:
        parts = text.split("-", 1)
        if len(parts) != 2:
            _quality_format_error("invalid %s format: %s" % (label, path))
        try:
            start = int(parts[0].strip())
            end = int(parts[1].strip())
        except ValueError:
            _quality_format_error("invalid %s format: %s" % (label, path))
    else:
        try:
            start = int(text)
        except ValueError:
            _quality_format_error("invalid %s format: %s" % (label, path))
        end = start
    if start < 1 or end < 1 or start > end:
        _quality_format_error("invalid %s format: %s" % (label, path))
    return start, end


def _check_evidence_list(evidence: object, label: str, path: Path) -> list[dict]:
    if not isinstance(evidence, list):
        _quality_format_error("invalid %s format: %s" % (label, path))
    checked: list[dict] = []
    for ev in evidence:
        if not isinstance(ev, dict):
            _quality_format_error("invalid %s format: %s" % (label, path))
        rel = ev.get("path")
        digest = ev.get("sha256")
        anchors = ev.get("anchors")
        if not isinstance(rel, str) or rel == "":
            _quality_format_error("invalid %s format: %s" % (label, path))
        if (
            rel.startswith("/")
            or rel.startswith("\\")
            or ".." in rel.replace("\\", "/").split("/")
            or ":" in rel
            or "\\" in rel
        ):
            _quality_format_error("invalid %s format: %s" % (label, path))
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            _quality_format_error("invalid %s format: %s" % (label, path))
        if not isinstance(anchors, list) or len(anchors) == 0:
            _quality_format_error("invalid %s format: %s" % (label, path))
        parsed: list[tuple[int, int]] = []
        for anchor in anchors:
            parsed.append(_parse_anchor(anchor, label, path))
        checked.append(
            {
                "path": rel,
                "sha256": digest.lower(),
                "anchors": sorted(anchors),
                "ranges": sorted(parsed),
            }
        )
    return checked


def _validate_quality_fixture(data: dict, path: Path) -> dict:
    if data.get("format") != QUALITY_FORMAT_ID:
        _quality_format_error("invalid fixture format: %s" % path)
    raw_cases = data.get("cases")
    raw_oracles = data.get("oracles")
    raw_boundary = data.get("information_boundary")
    if not isinstance(raw_cases, list) or not isinstance(raw_oracles, list):
        _quality_format_error("invalid fixture format: %s" % path)
    if not isinstance(raw_boundary, dict):
        _quality_format_error("invalid fixture format: %s" % path)

    cases: dict[str, dict] = {}
    for entry in raw_cases:
        if not isinstance(entry, dict):
            _quality_format_error("invalid fixture format: %s" % path)
        case_id = entry.get("case_id")
        req_ids = entry.get("required_oracle_ids")
        req_reasons = entry.get("required_expanded_review_reasons")
        provenance = entry.get("provenance")
        if not isinstance(case_id, str) or case_id == "":
            _quality_format_error("invalid fixture format: %s" % path)
        if case_id in cases:
            _quality_format_error("duplicate case id in fixture: %s" % case_id)
        ids = _as_str_list(req_ids, "fixture", path)
        reasons = _as_str_list(req_reasons, "fixture", path)
        if len(set(ids)) != len(ids):
            _quality_format_error("duplicate required oracle id in fixture: %s" % case_id)
        if len(set(reasons)) != len(reasons):
            _quality_format_error("duplicate required reason in fixture: %s" % case_id)
        if not isinstance(provenance, dict):
            _quality_format_error("invalid fixture format: %s" % path)
        origin = provenance.get("origin")
        prov_evidence = provenance.get("evidence", [])
        if origin not in ("historical", "synthetic"):
            _quality_format_error("invalid fixture format: %s" % path)
        if origin == "historical":
            checked_prov = _check_evidence_list(prov_evidence, "fixture", path)
            if len(checked_prov) == 0:
                _quality_format_error("invalid fixture format: %s" % path)
        else:
            if not isinstance(prov_evidence, list) or len(prov_evidence) != 0:
                _quality_format_error("invalid fixture format: %s" % path)
            checked_prov = []
        cases[case_id] = {
            "required_oracle_ids": sorted(ids),
            "required_reasons": sorted(reasons),
            "origin": origin,
            "provenance": checked_prov,
        }

    oracles: dict[str, dict] = {}
    for entry in raw_oracles:
        if not isinstance(entry, dict):
            _quality_format_error("invalid fixture format: %s" % path)
        oid = entry.get("id")
        case_id = entry.get("case_id")
        severity = entry.get("severity")
        claim = entry.get("claim")
        evidence = entry.get("evidence")
        if (
            not isinstance(oid, str)
            or oid == ""
            or not isinstance(case_id, str)
            or case_id == ""
            or not isinstance(severity, str)
            or severity == ""
            or not isinstance(claim, str)
            or claim == ""
            or not isinstance(evidence, list)
            or len(evidence) == 0
        ):
            _quality_format_error("invalid fixture format: %s" % path)
        if oid in oracles:
            _quality_format_error("duplicate oracle id in fixture: %s" % oid)
        if case_id not in cases:
            _quality_format_error("unknown case for oracle in fixture: %s" % oid)
        checked_evidence = _check_evidence_list(evidence, "fixture", path)
        if len(checked_evidence) == 0:
            _quality_format_error("invalid fixture format: %s" % path)
        oracles[oid] = {
            "case_id": case_id,
            "severity": severity,
            "claim": claim,
            "evidence": checked_evidence,
        }

    for case_id, record in cases.items():
        for req_id in record["required_oracle_ids"]:
            target = oracles.get(req_id)
            if target is None:
                _quality_format_error(
                    "unknown required oracle in fixture: %s" % req_id
                )
            if target["case_id"] != case_id:
                _quality_format_error(
                    "mismatched required oracle in fixture: %s" % req_id
                )

    exec_inputs = _as_str_list(
        raw_boundary.get("executor_inputs"), "fixture", path
    )
    oracle_only = _as_str_list(
        raw_boundary.get("oracle_only"), "fixture", path
    )
    if len(set(exec_inputs)) != len(exec_inputs):
        _quality_format_error("invalid fixture format: %s" % path)
    if len(set(oracle_only)) != len(oracle_only):
        _quality_format_error("invalid fixture format: %s" % path)
    if set(exec_inputs) & set(oracle_only):
        _quality_format_error("overlapping boundary in fixture: %s" % path)

    return {
        "cases": cases,
        "oracles": oracles,
        "executor_inputs": sorted(exec_inputs),
        "oracle_only": sorted(oracle_only),
    }


def _validate_fixture_evidence(
    fixture: dict, evidence_root: Path, fixture_path: Path
) -> None:
    if not evidence_root.exists() or not evidence_root.is_dir():
        _quality_format_error("missing evidence root: %s" % evidence_root)
    wanted: list[dict] = []
    for oid in sorted(fixture["oracles"].keys()):
        wanted.extend(fixture["oracles"][oid]["evidence"])
    for case_id in sorted(fixture["cases"].keys()):
        wanted.extend(fixture["cases"][case_id]["provenance"])
    checked: set[str] = set()
    for ev in wanted:
        rel = ev["path"]
        target = evidence_root / rel
        try:
            resolved = target.resolve()
            root_resolved = evidence_root.resolve()
        except OSError:
            _quality_format_error("unreadable evidence file: %s" % rel)
        if resolved != root_resolved and not _is_inside(
            resolved, root_resolved
        ):
            _quality_format_error("evidence escapes root: %s" % rel)
        try:
            raw = target.read_bytes()
        except OSError:
            _quality_format_error("unreadable evidence file: %s" % rel)
        digest = hashlib.sha256(raw).hexdigest()
        if digest.lower() != ev["sha256"].lower():
            _quality_format_error("fixture evidence mismatch: %s" % rel)
        checked.add(rel)
    for rel in sorted(checked):
        target = evidence_root / rel
        try:
            text = target.read_bytes().decode("utf-8-sig")
        except (OSError, UnicodeDecodeError):
            _quality_format_error("unreadable evidence file: %s" % rel)
        n_lines = len(text.splitlines())
        for ev in wanted:
            if ev["path"] != rel:
                continue
            for start, end in ev["ranges"]:
                if end > n_lines:
                    _quality_format_error(
                        "unknown anchor in fixture: %s:%d-%d" % (rel, start, end)
                    )


def _validate_candidate(
    data: dict, path: Path, fixture: dict
) -> tuple[list[dict], dict[str, set[str]]]:
    if data.get("format") != CANDIDATE_FORMAT_ID:
        _quality_format_error("invalid candidate format: %s" % path)
    raw_findings = data.get("findings")
    raw_cases = data.get("cases")
    if not isinstance(raw_findings, list) or not isinstance(raw_cases, list):
        _quality_format_error("invalid candidate format: %s" % path)

    seen_ids: set[str] = set()
    findings: list[dict] = []
    for entry in raw_findings:
        if not isinstance(entry, dict):
            _quality_format_error("invalid candidate format: %s" % path)
        fid = entry.get("id")
        case_id = entry.get("case_id")
        status = entry.get("status")
        oracle_ids = entry.get("oracle_ids", [])
        if (
            not isinstance(fid, str)
            or fid == ""
            or not isinstance(case_id, str)
            or case_id == ""
            or not isinstance(status, str)
        ):
            _quality_format_error("invalid candidate format: %s" % path)
        if fid in seen_ids:
            _quality_format_error("duplicate finding id: %s" % fid)
        seen_ids.add(fid)
        if case_id not in fixture["cases"]:
            _quality_format_error("unknown case: %s" % case_id)
        if status not in ("confirmed", "unconfirmed", "rejected"):
            _quality_format_error("invalid status: %s" % status)
        ids = _as_str_list(oracle_ids, "candidate", path)
        if len(set(ids)) != len(ids):
            _quality_format_error("duplicate oracle id in finding: %s" % fid)
        if status == "confirmed":
            if len(ids) == 0:
                _quality_format_error(
                    "confirmed finding without oracle ids: %s" % fid
                )
            for oid in ids:
                target = fixture["oracles"].get(oid)
                if target is None:
                    _quality_format_error("unknown oracle: %s" % oid)
                if target["case_id"] != case_id:
                    _quality_format_error(
                        "mismatched oracle in finding: %s" % fid
                    )
        else:
            if len(ids) != 0:
                _quality_format_error(
                    "non-confirmed finding with oracle ids: %s" % fid
                )
        findings.append(
            {
                "id": fid,
                "case_id": case_id,
                "status": status,
                "oracle_ids": sorted(ids),
            }
        )

    declared: dict[str, set[str]] = {}
    for entry in raw_cases:
        if not isinstance(entry, dict):
            _quality_format_error("invalid candidate format: %s" % path)
        case_id = entry.get("case_id")
        reasons = entry.get("expanded_review_reasons", [])
        if not isinstance(case_id, str) or case_id == "":
            _quality_format_error("invalid candidate format: %s" % path)
        if case_id not in fixture["cases"]:
            _quality_format_error("unknown case: %s" % case_id)
        if case_id in declared:
            _quality_format_error("duplicate case: %s" % case_id)
        items = _as_str_list(reasons, "candidate", path)
        if len(set(items)) != len(items):
            _quality_format_error("duplicate reason in case: %s" % case_id)
        declared[case_id] = set(items)

    for case_id in sorted(fixture["cases"].keys()):
        if case_id not in declared:
            _quality_format_error("missing case: %s" % case_id)
    findings.sort(key=lambda r: r["id"])
    return findings, declared


def _score_quality(
    fixture: dict, findings: list[dict], declared: dict[str, set[str]]
) -> dict:
    required: list[str] = sorted(
        {
            oid
            for record in fixture["cases"].values()
            for oid in record["required_oracle_ids"]
        }
    )
    covered_set: set[str] = set()
    for item in findings:
        if item["status"] == "confirmed":
            covered_set.update(item["oracle_ids"])
    covered_required: list[str] = sorted(oid for oid in covered_set if oid in set(required))
    missing: list[str] = sorted(oid for oid in required if oid not in covered_set)
    if required:
        score = len(covered_required) / len(required)
    else:
        score = 1.0

    rejected = sorted(item["id"] for item in findings if item["status"] == "rejected")
    unconfirmed = sorted(
        item["id"] for item in findings if item["status"] == "unconfirmed"
    )

    confirmed_by_case: dict[str, bool] = {case_id: False for case_id in fixture["cases"]}
    for item in findings:
        if item["status"] == "confirmed":
            confirmed_by_case[item["case_id"]] = True

    missing_triggers: list[dict] = []
    unnecessary: list[dict] = []
    for case_id in sorted(fixture["cases"].keys()):
        required_reasons = set(fixture["cases"][case_id]["required_reasons"])
        given = set(declared.get(case_id, set()))
        for reason in sorted(required_reasons - given):
            missing_triggers.append({"case_id": case_id, "reason": reason})
        if not confirmed_by_case[case_id]:
            for reason in sorted(given - required_reasons):
                unnecessary.append({"case_id": case_id, "reason": reason})

    if unconfirmed:
        verdict = "needs-adjudication"
    elif missing or rejected or missing_triggers or unnecessary:
        verdict = "fail"
    else:
        verdict = "pass"

    return {
        "format": SCORE_FORMAT_ID,
        "recall": {
            "required": required,
            "covered": covered_required,
            "missing": missing,
            "score": score,
        },
        "rejected_findings": rejected,
        "unconfirmed_findings": unconfirmed,
        "unnecessary_expansions": sorted(
            unnecessary, key=lambda r: (r["case_id"], r["reason"])
        ),
        "missing_required_triggers": sorted(
            missing_triggers, key=lambda r: (r["case_id"], r["reason"])
        ),
        "verdict": verdict,
    }


def _resolve_path(value: str) -> Path:
    return Path(value)


def _reject_out_path(
    out_path: Path | None,
    evidence_root: Path,
    fixture_path: Path,
    result_path: Path,
) -> None:
    if out_path is None:
        return
    try:
        out_resolved = out_path.resolve()
        evidence_resolved = evidence_root.resolve()
        fixture_resolved = fixture_path.resolve()
        result_resolved = result_path.resolve()
    except OSError:
        _quality_format_error("unreadable path")
    if out_resolved == evidence_resolved or _is_inside(out_resolved, evidence_resolved):
        _quality_format_error("refusing --out inside --evidence-root")
    if out_resolved == fixture_resolved:
        _quality_format_error("refusing --out equal to --fixture")
    if out_resolved == result_resolved:
        _quality_format_error("refusing --out equal to --result")


def run_benchmark_quality(args: argparse.Namespace) -> int:
    if not getattr(args, "evidence_root", None):
        _quality_format_error("missing --evidence-root")
    fixture_path = _resolve_path(args.fixture)
    result_path = _resolve_path(args.result)
    evidence_root = _resolve_path(args.evidence_root)
    out_path = _resolve_path(args.out) if getattr(args, "out", None) else None

    _reject_out_path(out_path, evidence_root, fixture_path, result_path)

    fixture_data = _load_json_document(fixture_path, "fixture")
    fixture = _validate_quality_fixture(fixture_data, fixture_path)
    _validate_fixture_evidence(fixture, evidence_root, fixture_path)

    candidate_data = _load_json_document(result_path, "candidate")
    findings, declared = _validate_candidate(candidate_data, result_path, fixture)
    scored = _score_quality(fixture, findings, declared)
    rendered = (
        json.dumps(scored, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    )
    if out_path is not None:
        try:
            if out_path.parent != Path(""):
                out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8", newline="\n")
        except OSError:
            _quality_format_error("cannot write --out: %s" % out_path)
    sys.stdout.write(rendered)
    verdict = scored["verdict"]
    if verdict == "pass":
        return 0
    if verdict == "fail":
        return 1
    return 2

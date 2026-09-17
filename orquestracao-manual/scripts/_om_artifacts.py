"""Private artifacts benchmark (portable census, dupes and text repeat)."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

SPEC_FORMAT = "om-benchmark-artifacts-spec/1"
REPORT_FORMAT = "om-benchmark-artifacts/1"
MANIFEST_ALGO = (
    "sha256-hex-of-utf8-joined("
    "'<posix-rel-path><TAB><bytes><TAB><sha256>\\n' "
    "sorted ordinal by posix-rel-path)"
)

_HEX64 = re.compile(r"[0-9a-fA-F]{64}")


def _input_error(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    sys.stderr.write("om: artifacts error: %s\n" % msg)
    raise SystemExit(2)


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        _input_error("unreadable %s: %s" % (label, path))


def _parse_json(data: bytes, path: Path, label: str) -> dict:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        _input_error("invalid %s format: %s" % (label, path))
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        _input_error("invalid %s format: %s" % (label, path))
    if not isinstance(obj, dict):
        _input_error("invalid %s format: %s" % (label, path))
    return obj


def _is_token(val: object) -> bool:
    if not isinstance(val, str) or val == "":
        return False
    if val.startswith("/") or val.startswith("\\"):
        return False
    if ":" in val or "\\" in val:
        return False
    if val.strip() != val:
        return False
    parts = val.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return False
    if any(p != p.strip() for p in parts):
        return False
    return True


def _as_pos_int(val: object) -> int | None:
    if isinstance(val, bool):
        return None
    if not isinstance(val, int):
        return None
    if val <= 0:
        return None
    return val


def _need_hex(val: object) -> str:
    if not isinstance(val, str):
        return ""
    if not _HEX64.fullmatch(val):
        return ""
    return val.lower()


def _compile_pat(pat: object, path: Path, label: str):
    if not isinstance(pat, str) or pat == "":
        _input_error("invalid %s pattern: %s" % (label, path))
    try:
        return re.compile(pat)
    except re.error:
        _input_error("invalid %s pattern: %s" % (label, path))


def _check_spec(obj: dict, path: Path) -> dict:
    if obj.get("format") != SPEC_FORMAT:
        _input_error("invalid spec format: %s" % path)
    raw_rules = obj.get("rules")
    raw_scopes = obj.get("text_scopes")
    raw_thr = obj.get("thresholds")
    raw_top = obj.get("top_n")
    if not isinstance(raw_rules, list) or len(raw_rules) == 0:
        _input_error("invalid spec rules: %s" % path)
    if not isinstance(raw_scopes, list) or len(raw_scopes) == 0:
        _input_error("invalid spec text_scopes: %s" % path)
    if not isinstance(raw_thr, list) or len(raw_thr) == 0:
        _input_error("invalid spec thresholds: %s" % path)
    top_n = _as_pos_int(raw_top)
    if top_n is None:
        _input_error("invalid spec top_n: %s" % path)
    assert top_n is not None
    thr: list[int] = []
    for item in raw_thr:
        num = _as_pos_int(item)
        if num is None:
            _input_error("invalid spec thresholds: %s" % path)
        assert num is not None
        thr.append(num)
    if len(set(thr)) != len(thr):
        _input_error("invalid spec thresholds: %s" % path)
    thr = sorted(thr)
    rules: list[dict] = []
    seen: set[str] = set()
    for entry in raw_rules:
        if not isinstance(entry, dict):
            _input_error("invalid spec rules: %s" % path)
        rid = entry.get("id")
        pat = entry.get("pattern")
        if not _is_token(rid):
            _input_error("invalid spec rule id: %s" % path)
        assert isinstance(rid, str)
        if rid in seen:
            _input_error("invalid spec rules: %s" % path)
        seen.add(rid)
        compiled = _compile_pat(pat, path, "spec rule")
        assert isinstance(pat, str)
        rules.append({"id": rid, "pattern": pat, "compiled": compiled})
    scopes: list[dict] = []
    seen_s: set[str] = set()
    for entry in raw_scopes:
        if not isinstance(entry, dict):
            _input_error("invalid spec text_scopes: %s" % path)
        sid = entry.get("id")
        pat = entry.get("pattern")
        if not _is_token(sid):
            _input_error("invalid spec scope id: %s" % path)
        assert isinstance(sid, str)
        if sid in seen_s:
            _input_error("invalid spec text_scopes: %s" % path)
        seen_s.add(sid)
        compiled = _compile_pat(pat, path, "spec scope")
        assert isinstance(pat, str)
        scopes.append({"id": sid, "pattern": pat, "compiled": compiled})
    overlap = set(seen) & set(seen_s)
    # scope ids may reuse wording but must stay distinct from rule ids
    # to keep physical and textual namespaces separate.
    if overlap:
        _input_error("invalid spec scope id: %s" % path)
    for key in obj.keys():
        if key not in ("format", "rules", "text_scopes", "thresholds", "top_n"):
            _input_error("invalid spec format: %s" % path)
    return {"rules": rules, "scopes": scopes, "thresholds": thr, "top_n": top_n}


def _check_report(obj: dict, path: Path) -> dict:
    if obj.get("format") != REPORT_FORMAT:
        _input_error("invalid report format: %s" % path)
    for key in (
        "format",
        "spec_sha256",
        "manifest",
        "manifest_algorithm",
        "aggregates",
        "totals",
        "duplicates",
        "repetition",
    ):
        if key not in obj:
            _input_error("invalid report format: %s" % path)
    spec_h = _need_hex(obj.get("spec_sha256"))
    mani_h = _need_hex(obj.get("manifest"))
    if not spec_h:
        _input_error("invalid report format: %s" % path)
    if not mani_h:
        _input_error("invalid report format: %s" % path)
    if not isinstance(obj.get("manifest_algorithm"), str):
        _input_error("invalid report format: %s" % path)
    if not isinstance(obj.get("aggregates"), dict):
        _input_error("invalid report format: %s" % path)
    if not isinstance(obj.get("totals"), dict):
        _input_error("invalid report format: %s" % path)
    if not isinstance(obj.get("duplicates"), dict):
        _input_error("invalid report format: %s" % path)
    if not isinstance(obj.get("repetition"), dict):
        _input_error("invalid report format: %s" % path)
    return obj


def _walk_source(root: Path) -> list[tuple[str, int, str]]:
    if not root.exists():
        _input_error("missing source: %s" % root)
    if root.is_symlink():
        _input_error("symlink found under source")
    if not root.is_dir():
        _input_error("source is not a directory: %s" % root)
    try:
        items = list(root.rglob("*"))
    except OSError:
        _input_error("unreadable source: %s" % root)
    out: list[tuple[str, int, str]] = []
    for item in sorted(items, key=lambda p: p.as_posix()):
        try:
            if item.is_symlink():
                _input_error("symlink found under source")
        except OSError:
            _input_error("unreadable source entry")
        try:
            is_f = item.is_file()
        except OSError:
            _input_error("unreadable source entry")
        if not is_f:
            continue
        try:
            rel = item.relative_to(root).as_posix()
        except ValueError:
            _input_error("unreadable source entry")
        if rel == "" or rel.startswith("/") or ".." in rel.split("/"):
            _input_error("unreadable source entry")
        try:
            size = item.stat().st_size
        except OSError:
            _input_error("unreadable file: %s" % rel)
        digest = hashlib.sha256()
        try:
            with item.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
        except OSError:
            _input_error("unreadable file: %s" % rel)
        out.append((rel, size, digest.hexdigest()))
    out.sort(key=lambda t: t[0])
    return out


def _apply_rules(
    entries: list[tuple[str, int, str]], rules: list[dict]
) -> tuple[dict[str, list[tuple[str, int, str]]], dict[str, str]]:
    by_rule: dict[str, list[tuple[str, int, str]]] = {r["id"]: [] for r in rules}
    rel_to_rule: dict[str, str] = {}
    for rel, size, digest in entries:
        hits: list[str] = []
        for rule in rules:
            compiled = rule["compiled"]
            if compiled.fullmatch(rel) is not None:
                hits.append(rule["id"])
        if len(hits) != 1:
            if len(hits) == 0:
                _input_error("file matches no rule: %s" % rel)
            else:
                _input_error("file matches several rules: %s" % rel)
        rid = hits[0]
        by_rule[rid].append((rel, size, digest))
        rel_to_rule[rel] = rid
    return by_rule, rel_to_rule


def _build_manifest(entries: list[tuple[str, int, str]]) -> str:
    blob = "".join("%s\t%d\t%s\n" % (rel, size, digest) for rel, size, digest in entries)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _build_dupes(entries: list[tuple[str, int, str]]) -> dict:
    from collections import defaultdict

    grouped: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for rel, size, digest in entries:
        grouped[digest].append((rel, size))
    multi = {h: v for h, v in grouped.items() if len(v) > 1}
    groups = len(multi)
    files = sum(len(v) for v in multi.values())
    phys = sum(sz for v in multi.values() for _, sz in v)
    uniq = sum(v[0][1] for v in multi.values())
    rep = phys - uniq
    lst = []
    for h in sorted(multi.keys()):
        v = multi[h]
        lst.append({"sha256": h, "files": len(v), "bytes": v[0][1]})
    return {
        "groups": groups,
        "files": files,
        "physical_bytes": phys,
        "unique_bytes": uniq,
        "repeated_bytes": rep,
        "group_list": lst,
    }


def _split_text(data: bytes, rel: str) -> list[str]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        _input_error("invalid text in scope file: %s" % rel)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.split("\n")


def _scope_files(
    entries: list[tuple[str, int, str]],
    rel_to_rule: dict[str, str],
    scopes: list[dict],
    root: Path,
) -> tuple[dict[str, list[str]], str]:
    per_scope: dict[str, list[str]] = {}
    seen: dict[str, str] = {}
    for scope in scopes:
        sid = scope["id"]
        compiled = scope["compiled"]
        matched: list[str] = []
        for rel, _, _ in entries:
            if compiled.fullmatch(rel) is not None:
                matched.append(rel)
        matched.sort()
        if len(matched) == 0:
            _input_error("text scope matches nothing: %s" % sid)
        for rel in matched:
            if rel in seen:
                _input_error("text scopes overlap at: %s" % rel)
            seen[rel] = sid
        per_scope[sid] = matched
    cats: set[str] = set()
    for rel in seen.keys():
        rid = rel_to_rule.get(rel)
        if rid is None:
            _input_error("text scope outside census: %s" % rel)
        assert rid is not None
        cats.add(rid)
    if len(cats) != 1:
        _input_error("text scopes span several rules")
    only = next(iter(cats))
    return per_scope, only


def _totals_for(
    rels: list[str], root: Path
) -> tuple[int, int, int, int, int, dict[str, list[str]]]:
    # returns files, raw_bytes, lines, nonempty, empty, per-file lines
    files = len(rels)
    raw_b = 0
    n_lines = 0
    n_nonempty = 0
    text_b = 0
    per_file: dict[str, list[str]] = {}
    for rel in rels:
        target = root / rel
        try:
            data = target.read_bytes()
        except OSError:
            _input_error("unreadable file: %s" % rel)
        raw_b += len(data)
        parts = _split_text(data, rel)
        per_file[rel] = parts
        n_lines += len(parts)
        for line in parts:
            if line == "":
                continue
            n_nonempty += 1
            text_b += len(line.encode("utf-8"))
        # empty bytes add nothing; text_b already excludes newline/BOM
    n_empty = n_lines - n_nonempty
    return files, raw_b, n_lines, n_nonempty, n_empty, per_file


def _stats_for(
    per_file: dict[str, list[str]],
    scope_of_file: dict[str, str],
    thresholds: list[int],
    total_lines: int,
    text_b: int,
    want_empty: bool,
) -> dict:
    from collections import defaultdict

    to_files: dict[str, set[str]] = defaultdict(set)
    to_occ: dict[str, int] = defaultdict(int)
    to_len: dict[str, int] = {}
    for rel, parts in per_file.items():
        for line in parts:
            if (not want_empty) and line == "":
                continue
            to_files[line].add(rel)
            to_occ[line] += 1
            if line not in to_len:
                to_len[line] = len(line.encode("utf-8"))
    out: dict[str, dict] = {}
    for thr in thresholds:
        keep = [txt for txt, fs in to_files.items() if len(fs) >= thr]
        dist = len(keep)
        occ = sum(to_occ[t] for t in keep)
        red = occ - dist
        cov_b = sum(to_occ[t] * to_len[t] for t in keep)
        if total_lines > 0:
            pct_l = 100.0 * occ / total_lines
        else:
            pct_l = 0.0
        if text_b > 0:
            pct_b = 100.0 * cov_b / text_b
        else:
            pct_b = 0.0
        out[str(thr)] = {
            "distinct": dist,
            "occurrences": occ,
            "redundant": red,
            "pct_lines": pct_l,
            "pct_bytes": pct_b,
            "covered_bytes": cov_b,
        }
    return out


def _build_repetition(
    per_scope_rels: dict[str, list[str]],
    root: Path,
    thresholds: list[int],
    top_n: int,
) -> dict:
    from collections import defaultdict
    import hashlib as _hl

    scope_ids = sorted(per_scope_rels.keys())
    all_rels: list[str] = []
    for sid in scope_ids:
        all_rels.extend(per_scope_rels[sid])
    all_rels.sort()
    f_n, raw_b, n_l, n_ne, n_e, per_file_all = _totals_for(all_rels, root)
    # text_b already computed inside _totals_for (without newline/BOM)
    text_b = 0
    for parts in per_file_all.values():
        for line in parts:
            if line != "":
                text_b += len(line.encode("utf-8"))
    rel_to_scope: dict[str, str] = {}
    for sid, rels in per_scope_rels.items():
        for rel in rels:
            rel_to_scope[rel] = sid
    with_empty = _stats_for(per_file_all, rel_to_scope, thresholds, n_l, text_b, True)
    # for SEM the denominator is nonempty count
    without_empty = _stats_for(per_file_all, rel_to_scope, thresholds, n_ne, text_b, False)
    scopes_doc: dict[str, dict] = {}
    for sid in scope_ids:
        rels = sorted(per_scope_rels[sid])
        s_f, s_raw, s_l, s_ne, s_e, s_per = _totals_for(rels, root)
        s_tb = 0
        for parts in s_per.values():
            for line in parts:
                if line != "":
                    s_tb += len(line.encode("utf-8"))
        s_rel_to: dict[str, str] = {r: sid for r in rels}
        s_with = _stats_for(s_per, s_rel_to, thresholds, s_l, s_tb, True)
        s_without = _stats_for(s_per, s_rel_to, thresholds, s_ne, s_tb, False)
        scopes_doc[sid] = {
            "files": s_f,
            "bytes_raw": s_raw,
            "lines": s_l,
            "lines_nonempty": s_ne,
            "lines_empty": s_e,
            "text_bytes": s_tb,
            "with_empty": s_with,
            "without_empty": s_without,
        }
    # top: non-empty lines in full scope, ordered by files desc, occ desc, hash asc
    to_files: dict[str, set[str]] = defaultdict(set)
    to_occ: dict[str, int] = defaultdict(int)
    to_scopes: dict[str, set[str]] = defaultdict(set)
    to_len: dict[str, int] = {}
    for rel, parts in per_file_all.items():
        sid = rel_to_scope[rel]
        for line in parts:
            if line == "":
                continue
            to_files[line].add(rel)
            to_occ[line] += 1
            to_scopes[line].add(sid)
            if line not in to_len:
                to_len[line] = len(line.encode("utf-8"))
    ranked = []
    for txt, fs in to_files.items():
        h = _hl.sha256(txt.encode("utf-8")).hexdigest()
        ranked.append((txt, len(fs), to_occ[txt], h))
    ranked.sort(key=lambda t: (-t[1], -t[2], t[3]))
    # top holds only lines seen in at least min(thresholds) distinct files;
    # top_n is a maximum, never padded with unique lines.
    min_thr = min(thresholds)
    top = []
    for txt, nf, occ, h in ranked:
        if nf < min_thr:
            continue
        if len(top) >= top_n:
            break
        top.append(
            {
                "kind": "candidate",
                "line_sha256": h,
                "files": nf,
                "occurrences": occ,
                "line_bytes": to_len[txt],
                "covered_bytes": occ * to_len[txt],
                "scopes": sorted(to_scopes[txt]),
            }
        )
    return {
        "kind": "exact_repetition",
        "note": (
            "Exact lexical repetition only (case and space sensitive); "
            "candidate groups may hold semantic false positives; "
            "no claim about protocol, removability or proven reproduction; "
            "historical scratch grouping is descriptive only, not a "
            "deletion approval."
        ),
        "method": (
            "utf-8-sig decode; CRLF/CR to LF; split on LF; spaces kept; "
            "empty when == ''; bytes are utf-8 length without newline/BOM"
        ),
        "thresholds": list(thresholds),
        "top_n": top_n,
        "totals": {
            "files": f_n,
            "bytes_raw": raw_b,
            "lines": n_l,
            "lines_nonempty": n_ne,
            "lines_empty": n_e,
            "text_bytes": text_b,
        },
        "full": {"with_empty": with_empty, "without_empty": without_empty},
        "scopes": scopes_doc,
        "top": top,
    }


def _render(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def run_benchmark_artifacts(args) -> int:
    src = Path(str(args.source))
    spec_path = Path(str(args.spec))
    base_path = Path(str(args.baseline))
    spec_data = _parse_json(_read_bytes(spec_path, "spec"), spec_path, "spec")
    spec = _check_spec(spec_data, spec_path)
    spec_h = hashlib.sha256(_read_bytes(spec_path, "spec")).hexdigest().lower()
    base_data = _parse_json(_read_bytes(base_path, "baseline"), base_path, "baseline")
    base = _check_report(base_data, base_path)
    if base.get("spec_sha256", "").lower() != spec_h:
        _input_error("spec seal mismatch")
    if base.get("manifest_algorithm") != MANIFEST_ALGO:
        _input_error("invalid baseline manifest algorithm")
    entries = _walk_source(src)
    by_rule, rel_to_rule = _apply_rules(entries, spec["rules"])
    manifest = _build_manifest(entries)
    aggregates: dict[str, dict] = {}
    for rule in spec["rules"]:
        rid = rule["id"]
        lst = by_rule[rid]
        aggregates[rid] = {
            "files": len(lst),
            "bytes": sum(sz for _, sz, _ in lst),
        }
    totals = {
        "files": len(entries),
        "bytes": sum(sz for _, sz, _ in entries),
    }
    dupes = _build_dupes(entries)
    per_scope, _only = _scope_files(entries, rel_to_rule, spec["scopes"], src)
    repetition = _build_repetition(per_scope, src, spec["thresholds"], spec["top_n"])
    measured = {
        "format": REPORT_FORMAT,
        "spec_sha256": spec_h,
        "manifest": manifest,
        "manifest_algorithm": MANIFEST_ALGO,
        "aggregates": aggregates,
        "totals": totals,
        "duplicates": dupes,
        "repetition": repetition,
    }
    rendered = _render(measured)
    sys.stdout.write(rendered)
    mismatch = None
    if base.get("manifest") != measured["manifest"]:
        mismatch = "mismatch: manifest differs"
    elif base.get("aggregates") != measured["aggregates"]:
        mismatch = "mismatch: aggregates differ"
    elif base.get("totals") != measured["totals"]:
        mismatch = "mismatch: totals differ"
    elif base.get("duplicates") != measured["duplicates"]:
        mismatch = "mismatch: duplicates differ"
    elif base.get("repetition") != measured["repetition"]:
        mismatch = "mismatch: repetition differs"
    elif base.get("format") != measured["format"]:
        mismatch = "mismatch: format differs"
    if mismatch is not None:
        sys.stderr.write("om: %s\n" % mismatch)
        return 1
    return 0

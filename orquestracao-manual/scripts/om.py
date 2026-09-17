"""Operation control plane (evolutionary entry point).

Phase A: deterministic read-only benchmarks from internal libraries and frozen
fixtures. Phase B: local task lifecycle over a hash-chained event log.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

FORMAT_ID = "om-benchmark-legacy/1"

MANIFEST_ALGORITHM = (
    "sha256-hex-of-utf8-joined('<sha256>:<posix-rel-path>\\n' "
    "sorted by posix-rel-path)"
)

# (glob by file name, category, flow). Category and flow stay separate
# fields in every record; aggregates never merge kinds.
KINDS = (
    ("pedido-*.md", "captain_authored_technical", "authored"),
    ("retorno-*.md", "captain_received_technical", "received"),
    ("despacho-*.md", "captain_authored_operational", "authored"),
    ("execucao-*.md", "captain_received_operational", "received"),
    ("continuacao-*.md", "captain_authored_handoff", "authored"),
)

_WORD_RE = re.compile(r"\S+")


def _fail(message: str) -> "NoReturn":  # type: ignore[name-defined]
    sys.stderr.write("om: %s\n" % message)
    raise SystemExit(1)


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _count_lines(text: str) -> int:
    if text == "":
        return 0
    return text.count("\n") + 1


def _measure_one(raw: bytes) -> tuple[int, int, int, str]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("invalid utf-8")
    n_bytes = len(raw)
    n_words = _count_words(text)
    n_lines = _count_lines(text)
    digest = hashlib.sha256(raw).hexdigest()
    return n_bytes, n_words, n_lines, digest


def _classify(name: str) -> tuple[str, str, str] | None:
    import fnmatch

    for pattern, category, flow in KINDS:
        if fnmatch.fnmatchcase(name, pattern):
            return pattern, category, flow
    return None


def measure_source(source: Path) -> tuple[list[dict], dict, str]:
    if not source.exists():
        _fail("missing source: %s" % source)
    if not source.is_dir():
        _fail("source is not a directory: %s" % source)

    records: list[dict] = []
    # Walk by name so nested layouts stay comparable; historic input is flat.
    candidates = sorted(
        (p for p in source.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(source).as_posix(),
    )
    for path in candidates:
        hit = _classify(path.name)
        if hit is None:
            continue
        pattern, category, flow = hit
        rel = path.relative_to(source).as_posix()
        try:
            raw = path.read_bytes()
        except OSError:
            _fail("unreadable file: %s" % rel)
        try:
            n_bytes, n_words, n_lines, digest = _measure_one(raw)
        except ValueError:
            _fail("unreadable file: %s" % rel)
        records.append(
            {
                "path": rel,
                "category": category,
                "flow": flow,
                "bytes": n_bytes,
                "words": n_words,
                "lines": n_lines,
                "sha256": digest,
            }
        )

    records.sort(key=lambda r: r["path"])

    aggregates: dict[str, dict] = {}
    for pattern, category, flow in KINDS:
        subset = [r for r in records if r["category"] == category]
        aggregates[category] = {
            "glob": pattern,
            "flow": flow,
            "files": len(subset),
            "lines": sum(r["lines"] for r in subset),
            "words": sum(r["words"] for r in subset),
            "bytes": sum(r["bytes"] for r in subset),
        }

    blob = "".join("%s:%s\n" % (r["sha256"], r["path"]) for r in records)
    manifest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return records, aggregates, manifest


def build_document(
    records: list[dict], aggregates: dict, manifest: str
) -> dict:
    return {
        "format": FORMAT_ID,
        "manifest_algorithm": MANIFEST_ALGORITHM,
        "manifest": manifest,
        "aggregates": aggregates,
        "files": records,
    }


def render_document(document: dict) -> str:
    return (
        json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False)
        + "\n"
    )


def load_baseline(path: Path) -> dict:
    try:
        raw = path.read_bytes()
    except OSError:
        _fail("unreadable baseline: %s" % path)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        _fail("invalid baseline format: %s" % path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        _fail("invalid baseline format: %s" % path)
    if not isinstance(data, dict):
        _fail("invalid baseline format: %s" % path)
    for key in ("format", "manifest_algorithm", "manifest", "aggregates", "files"):
        if key not in data:
            _fail("invalid baseline format: %s" % path)
    if (
        not isinstance(data["aggregates"], dict)
        or not isinstance(data["files"], list)
        or not isinstance(data["format"], str)
        or not isinstance(data["manifest"], str)
        or not isinstance(data["manifest_algorithm"], str)
    ):
        _fail("invalid baseline format: %s" % path)
    return data


def compare_documents(measured: dict, baseline: dict) -> str | None:
    if baseline.get("format") != measured["format"]:
        return "mismatch: format differs"
    if baseline.get("manifest_algorithm") != measured["manifest_algorithm"]:
        return "mismatch: manifest algorithm differs"
    if baseline.get("manifest") != measured["manifest"]:
        return "mismatch: manifest differs"
    if baseline.get("aggregates") != measured["aggregates"]:
        return "mismatch: aggregates differ"
    if baseline.get("files") != measured["files"]:
        return "mismatch: files differ"
    return None


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def run_benchmark_legacy(args: argparse.Namespace) -> int:
    source = Path(args.source)
    baseline_path = Path(args.baseline)
    out_path = Path(args.out) if args.out else None

    if not source.exists() or not source.is_dir():
        _fail("missing source: %s" % source)

    if out_path is not None:
        try:
            source_resolved = source.resolve()
            out_resolved = out_path.resolve()
        except OSError:
            _fail("unreadable path")
        if out_resolved == source_resolved or _is_inside(
            out_resolved, source_resolved
        ):
            _fail("refusing --out inside --source")

    records, aggregates, manifest = measure_source(source)
    measured = build_document(records, aggregates, manifest)
    rendered = render_document(measured)

    baseline = load_baseline(baseline_path)

    if out_path is not None:
        try:
            if out_path.parent != Path(""):
                out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8", newline="\n")
        except OSError:
            _fail("cannot write --out: %s" % out_path)

    sys.stdout.write(rendered)

    problem = compare_documents(measured, baseline)
    if problem is not None:
        sys.stderr.write("om: %s\n" % problem)
        return 1
    return 0


def _load_quality_runner():
    try:
        from _om_quality import run_benchmark_quality

        return run_benchmark_quality
    except ImportError:
        import importlib.util

        qp = Path(__file__).resolve().parent / "_om_quality.py"
        spec = importlib.util.spec_from_file_location("_om_quality", qp)
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run_benchmark_quality


def _load_report_runner():
    try:
        from _om_report import run_benchmark_report

        return run_benchmark_report
    except ImportError:
        import importlib.util

        qp = Path(__file__).resolve().parent / "_om_report.py"
        spec = importlib.util.spec_from_file_location("_om_report", qp)
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run_benchmark_report


def _load_artifacts_runner():
    try:
        from _om_artifacts import run_benchmark_artifacts

        return run_benchmark_artifacts
    except ImportError:
        import importlib.util

        qp = Path(__file__).resolve().parent / "_om_artifacts.py"
        spec = importlib.util.spec_from_file_location("_om_artifacts", qp)
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run_benchmark_artifacts


def _load_control_runner(name: str):
    try:
        import _om_control

        return getattr(_om_control, name)
    except ImportError:
        import importlib.util

        path = Path(__file__).resolve().parent / "_om_control.py"
        spec = importlib.util.spec_from_file_location("_om_control", path)
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="om")
    sub = parser.add_subparsers(dest="command", required=True)
    bench = sub.add_parser("benchmark", help="read-only measurement commands")
    bench_sub = bench.add_subparsers(dest="benchmark_command", required=True)
    legacy = bench_sub.add_parser(
        "legacy", help="measure canonical coordination files by name"
    )
    legacy.add_argument("--source", required=True, help="operation directory")
    legacy.add_argument("--baseline", required=True, help="frozen JSON file")
    legacy.add_argument("--out", required=False, default=None)
    legacy.set_defaults(func=run_benchmark_legacy)
    quality = bench_sub.add_parser(
        "quality", help="score adjudicated correspondences"
    )
    quality.add_argument("--fixture", required=True, help="quality fixture file")
    quality.add_argument("--result", required=True, help="candidate result file")
    quality.add_argument(
        "--evidence-root",
        required=True,
        default=None,
        help="required: evidence directory",
    )
    quality.add_argument("--out", required=False, default=None)
    quality.set_defaults(func=_load_quality_runner())
    report = bench_sub.add_parser(
        "report", help="derive measurable Phase A cost baseline"
    )
    report.add_argument("--legacy", required=True, help="legacy fixture file")
    report.add_argument("--quality", required=True, help="quality fixture file")
    report.add_argument("--spec", required=True, help="report spec file")
    report.set_defaults(func=_load_report_runner())
    artifacts = bench_sub.add_parser(
        "artifacts", help="census of physical files with dupes and repeats"
    )
    artifacts.add_argument("--source", required=True, help="operation directory")
    artifacts.add_argument("--spec", required=True, help="artifacts spec file")
    artifacts.add_argument("--baseline", required=True, help="frozen JSON file")
    artifacts.set_defaults(func=_load_artifacts_runner())
    _load_control_runner("register_cli")(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_usage(sys.stderr)
        return 2
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())

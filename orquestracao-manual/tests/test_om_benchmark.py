"""Tests for the read-only legacy benchmark (first Phase A recorte)."""

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
ORQ_DIR = TEST_DIR.parent
OM_PATH = ORQ_DIR / "scripts" / "om.py"
FIXTURE_DIR = TEST_DIR / "fixtures" / "legacy-operation"
FROZEN_BASELINE = ORQ_DIR / "manutencao" / "benchmarks" / "lua-translator-02.json"


def load_om():
    spec = importlib.util.spec_from_file_location("om_under_test", OM_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OM = load_om()


def run_om(source, baseline, out=None):
    cmd = [
        sys.executable,
        "-B",
        str(OM_PATH),
        "benchmark",
        "legacy",
        "--source",
        str(source),
        "--baseline",
        str(baseline),
    ]
    if out is not None:
        cmd += ["--out", str(out)]
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", timeout=60
    )


def snapshot_tree(root):
    data = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            st = path.stat()
            data[rel] = (hashlib.sha256(path.read_bytes()).hexdigest(), st.st_mtime_ns)
    return data


def write_bytes(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def make_minimal_source(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "pedido-01-a.md").write_text("hello world\n", encoding="utf-8", newline="\n")
    (root / "retorno-01-a.md").write_text("reply\n", encoding="utf-8", newline="\n")
    return root


def frozen_baseline_for(source, dest):
    records, aggregates, manifest = OM.measure_source(Path(source))
    doc = OM.build_document(records, aggregates, manifest)
    dest.write_text(OM.render_document(doc), encoding="utf-8", newline="\n")
    return doc


class CountingTest(unittest.TestCase):
    def test_basic_counts_include_trailing_segment(self):
        raw = b"hello world\nsecond line here\n"
        n_bytes, n_words, n_lines, digest = OM._measure_one(raw)
        self.assertEqual(n_bytes, 29)
        self.assertEqual(n_words, 5)
        # 2 newlines + 1 reproduces the published baseline definition.
        self.assertEqual(n_lines, 3)
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())

    def test_no_trailing_newline_is_single_segment(self):
        n_bytes, n_words, n_lines, _ = OM._measure_one(b"a")
        self.assertEqual((n_bytes, n_words, n_lines), (1, 1, 1))

    def test_single_newline_counts_two_segments(self):
        _, _, n_lines, _ = OM._measure_one(b"a\n")
        self.assertEqual(n_lines, 2)

    def test_empty_is_zero(self):
        n_bytes, n_words, n_lines, digest = OM._measure_one(b"")
        self.assertEqual((n_bytes, n_words, n_lines), (0, 0, 0))
        self.assertEqual(digest, hashlib.sha256(b"").hexdigest())

    def test_bom_stripped_for_text_but_kept_in_bytes(self):
        raw = b"\xef\xbb\xbfbom hello\n"
        n_bytes, n_words, n_lines, _ = OM._measure_one(raw)
        self.assertEqual(n_bytes, 13)
        self.assertEqual(n_words, 2)
        self.assertEqual(n_lines, 2)

    def test_invalid_utf8_fails_explicitly(self):
        with self.assertRaises(ValueError):
            OM._measure_one(b"\xff\xfe\x00bad")


class ClassificationTest(unittest.TestCase):
    def test_five_kinds_by_name_with_category_and_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pedido-01-a.md").write_text("a\n", encoding="utf-8", newline="\n")
            (root / "retorno-01-a.md").write_text("b\n", encoding="utf-8", newline="\n")
            (root / "despacho-01.md").write_text("c\n", encoding="utf-8", newline="\n")
            (root / "execucao-01.md").write_text("d\n", encoding="utf-8", newline="\n")
            (root / "continuacao-01.md").write_text("e\n", encoding="utf-8", newline="\n")
            (root / "estado.md").write_text("ignored\n", encoding="utf-8", newline="\n")
            (root / "notes.txt").write_text("ignored\n", encoding="utf-8", newline="\n")
            records, aggregates, _ = OM.measure_source(root)
            by_path = {r["path"]: r for r in records}
            self.assertEqual(
                by_path["pedido-01-a.md"]["category"], "captain_authored_technical"
            )
            self.assertEqual(by_path["pedido-01-a.md"]["flow"], "authored")
            self.assertEqual(
                by_path["retorno-01-a.md"]["category"], "captain_received_technical"
            )
            self.assertEqual(by_path["retorno-01-a.md"]["flow"], "received")
            self.assertEqual(
                by_path["despacho-01.md"]["category"], "captain_authored_operational"
            )
            self.assertEqual(by_path["despacho-01.md"]["flow"], "authored")
            self.assertEqual(
                by_path["execucao-01.md"]["category"], "captain_received_operational"
            )
            self.assertEqual(by_path["execucao-01.md"]["flow"], "received")
            self.assertEqual(
                by_path["continuacao-01.md"]["category"], "captain_authored_handoff"
            )
            self.assertEqual(by_path["continuacao-01.md"]["flow"], "authored")
            self.assertNotIn("estado.md", by_path)
            self.assertNotIn("notes.txt", by_path)
            self.assertEqual(aggregates["captain_authored_technical"]["glob"], "pedido-*.md")
            self.assertEqual(aggregates["captain_authored_technical"]["files"], 1)


class DeterministicOutputTest(unittest.TestCase):
    def test_two_runs_match_and_out_matches_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            baseline = tmp_path / "base.json"
            frozen_baseline_for(FIXTURE_DIR, baseline)
            out_file = tmp_path / "out.json"
            first = run_om(FIXTURE_DIR, baseline, out=out_file)
            self.assertEqual(first.returncode, 0, msg=first.stderr)
            second = run_om(FIXTURE_DIR, baseline)
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(out_file.read_text(encoding="utf-8"), first.stdout)
            # Deterministic JSON uses sorted keys and a stable indent.
            parsed = json.loads(first.stdout)
            self.assertEqual(
                first.stdout,
                json.dumps(parsed, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
            )


class MismatchTest(unittest.TestCase):
    def test_exact_mismatch_fails_with_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src"
            make_minimal_source(src)
            baseline = tmp_path / "base.json"
            doc = frozen_baseline_for(src, baseline)
            doc["aggregates"]["captain_authored_technical"]["words"] += 1
            baseline.write_text(
                json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            proc = run_om(src, baseline)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("mismatch", proc.stderr.lower())

    def test_invalid_baseline_format_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src"
            make_minimal_source(src)
            baseline = tmp_path / "base.json"
            baseline.write_text("not json\n", encoding="utf-8", newline="\n")
            proc = run_om(src, baseline)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("baseline", proc.stderr.lower())


class EncodingEdgeTest(unittest.TestCase):
    def test_fixture_bom_and_empty_measured_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "base.json"
            frozen_baseline_for(FIXTURE_DIR, baseline)
            proc = run_om(FIXTURE_DIR, baseline)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            doc = json.loads(proc.stdout)
            by_path = {f["path"]: f for f in doc["files"]}
            bom = by_path["retorno-00-bom.md"]
            self.assertEqual(bom["bytes"], 13)
            self.assertEqual(bom["words"], 2)
            self.assertEqual(bom["lines"], 2)
            empty = by_path["pedido-00-empty.md"]
            self.assertEqual((empty["bytes"], empty["words"], empty["lines"]), (0, 0, 0))

    def test_invalid_file_never_becomes_silent_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "src"
            root.mkdir()
            write_bytes(root / "pedido-01-a.md", b"\xff\xfe\x00bad")
            baseline = Path(tmp) / "base.json"
            baseline.write_text("{}\n", encoding="utf-8", newline="\n")
            proc = run_om(root, baseline)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("unreadable", proc.stderr.lower())


class OutInsideSourceTest(unittest.TestCase):
    def test_out_inside_source_refused_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src"
            make_minimal_source(src)
            baseline = tmp_path / "base.json"
            frozen_baseline_for(src, baseline)
            inside = src / "out.json"
            proc = run_om(src, baseline, out=inside)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("refusing", proc.stderr.lower())
            self.assertFalse(inside.exists())
            nested = src / "sub" / "out.json"
            proc2 = run_om(src, baseline, out=nested)
            self.assertNotEqual(proc2.returncode, 0)
            self.assertFalse(nested.exists())


class ReadOnlyFixtureTest(unittest.TestCase):
    def test_fixture_names_hashes_mtimes_unchanged(self):
        before = snapshot_tree(FIXTURE_DIR)
        self.assertGreater(len(before), 0)
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "base.json"
            frozen_baseline_for(FIXTURE_DIR, baseline)
            proc = run_om(FIXTURE_DIR, baseline)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        after = snapshot_tree(FIXTURE_DIR)
        self.assertEqual(before, after)


class FrozenBaselineTest(unittest.TestCase):
    def test_frozen_expectation_matches_published_tables(self):
        doc = json.loads(FROZEN_BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(doc["format"], "om-benchmark-legacy/1")
        self.assertIn("manifest_algorithm", doc)
        self.assertIn("manifest", doc)
        agg = doc["aggregates"]
        expected = {
            "captain_authored_technical": (28, 3401, 22730, 173896),
            "captain_received_technical": (28, 2918, 25220, 203457),
            "captain_authored_operational": (25, 434, 3428, 32749),
            "captain_received_operational": (25, 249, 1518, 12089),
            "captain_authored_handoff": (3, 244, 1600, 10976),
        }
        for category, (files, lines, words, n_bytes) in expected.items():
            self.assertIn(category, agg)
            self.assertEqual(agg[category]["files"], files, msg=category)
            self.assertEqual(agg[category]["lines"], lines, msg=category)
            self.assertEqual(agg[category]["words"], words, msg=category)
            self.assertEqual(agg[category]["bytes"], n_bytes, msg=category)

        by_path = {f["path"]: f for f in doc["files"]}
        self.assertEqual(len(doc["files"]), 109)
        for name in (
            "pedido-13-a.md",
            "pedido-13-b.md",
            "retorno-13-a.md",
            "retorno-13-b.md",
        ):
            self.assertIn(name, by_path)

        def part(names):
            files = [by_path[n] for n in names]
            return (
                len(files),
                sum(f["lines"] for f in files),
                sum(f["words"] for f in files),
                sum(f["bytes"] for f in files),
            )

        self.assertEqual(part(["pedido-13-a.md", "pedido-13-b.md"]), (2, 211, 1609, 12485))
        self.assertEqual(
            part(["retorno-13-a.md", "retorno-13-b.md"]), (2, 275, 2803, 21553)
        )
        self.assertEqual(
            (by_path["pedido-13-a.md"]["bytes"], by_path["pedido-13-a.md"]["lines"], by_path["pedido-13-a.md"]["words"]),
            (7194, 126, 949),
        )
        self.assertEqual(
            (by_path["pedido-13-b.md"]["bytes"], by_path["pedido-13-b.md"]["lines"], by_path["pedido-13-b.md"]["words"]),
            (5291, 85, 660),
        )
        self.assertEqual(
            (by_path["retorno-13-a.md"]["bytes"], by_path["retorno-13-a.md"]["lines"], by_path["retorno-13-a.md"]["words"]),
            (9893, 87, 1233),
        )
        self.assertEqual(
            (by_path["retorno-13-b.md"]["bytes"], by_path["retorno-13-b.md"]["lines"], by_path["retorno-13-b.md"]["words"]),
            (11660, 188, 1570),
        )

        # Manifest is reproducible from the ordered file records.
        ordered = sorted(doc["files"], key=lambda r: r["path"])
        blob = "".join("%s:%s\n" % (r["sha256"], r["path"]) for r in ordered)
        self.assertEqual(hashlib.sha256(blob.encode("utf-8")).hexdigest(), doc["manifest"])
        self.assertTrue(re.search(r"sha256", doc["manifest_algorithm"], re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()

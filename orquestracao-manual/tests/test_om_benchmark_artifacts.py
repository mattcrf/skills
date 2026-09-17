"""Tests for the portable artifacts benchmark (generic + optional history)."""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
ORQ_DIR = TEST_DIR.parent
OM_PATH = ORQ_DIR / "scripts" / "om.py"
ART_PATH = ORQ_DIR / "scripts" / "_om_artifacts.py"
SYN_SPEC = TEST_DIR / "fixtures" / "artifacts" / "synthetic-spec.json"
SYN_ROOT = TEST_DIR / "fixtures" / "artifacts"
CODE_SRC = SYN_ROOT / "task-code"
DIAG_SRC = SYN_ROOT / "task-diagnostic"
DOCS_SRC = SYN_ROOT / "task-docs"
CANON_SPEC = ORQ_DIR / "manutencao" / "benchmarks" / "lua-translator-02-artifacts-spec.json"
CANON_BASE = ORQ_DIR / "manutencao" / "benchmarks" / "lua-translator-02-artifacts.json"
HISTORY_ENV = "OM_PHASE_A_HISTORY"


def run_artifacts(source, spec, baseline, extra=None):
    cmd = [
        sys.executable,
        "-B",
        str(OM_PATH),
        "benchmark",
        "artifacts",
        "--source",
        str(source),
        "--spec",
        str(spec),
        "--baseline",
        str(baseline),
    ]
    if extra:
        cmd += [str(x) for x in extra]
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", timeout=120
    )


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_baseline_via_lib(source, spec_path):
    import importlib.util

    sp = importlib.util.spec_from_file_location("art_lib", ART_PATH)
    assert sp is not None and sp.loader is not None
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    src = Path(source)
    spec_data = load_json(spec_path)
    spec = mod._check_spec(spec_data, Path(spec_path))
    spec_h = hashlib.sha256(Path(spec_path).read_bytes()).hexdigest().lower()
    entries = mod._walk_source(src)
    by_rule, rel_to_rule = mod._apply_rules(entries, spec["rules"])
    manifest = mod._build_manifest(entries)
    aggs = {
        rid: {"files": len(lst), "bytes": sum(s for _, s, _ in lst)}
        for rid, lst in by_rule.items()
    }
    totals = {"files": len(entries), "bytes": sum(s for _, s, _ in entries)}
    dupes = mod._build_dupes(entries)
    per_scope, _ = mod._scope_files(entries, rel_to_rule, spec["scopes"], src)
    rep = mod._build_repetition(per_scope, src, spec["thresholds"], spec["top_n"])
    doc = {
        "format": mod.REPORT_FORMAT,
        "spec_sha256": spec_h,
        "manifest": manifest,
        "manifest_algorithm": mod.MANIFEST_ALGO,
        "aggregates": aggs,
        "totals": totals,
        "duplicates": dupes,
        "repetition": rep,
    }
    return doc, mod


def _syn_rules():
    doc = load_json(SYN_SPEC)
    return [(r["id"], re.compile(r["pattern"])) for r in doc["rules"]]


def _rule_of(rel, rules=None):
    rules = rules or _syn_rules()
    hits = [rid for rid, rx in rules if rx.fullmatch(rel) is not None]
    return hits


def _write_minimal_source(root):
    (root / "coord").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "evidence").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "build").mkdir(parents=True, exist_ok=True)
    (root / "coord" / "morning-01.md").write_text(
        "Code task alpha\nShared note\nCode detail A\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "coord" / "evening-01.md").write_text(
        "Code task beta\nShared note\nCode detail B\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "src" / "app.py").write_text(
        "def main():\n    return 1\n", encoding="utf-8", newline="\n"
    )
    (root / "evidence" / "check.py").write_text(
        "def check():\n    return True\n", encoding="utf-8", newline="\n"
    )
    (root / "logs" / "run.json").write_text(
        '{"run": 1, "status": "ok"}\n', encoding="utf-8", newline="\n"
    )
    (root / "build" / "cache.dat").write_text(
        "code cache 1\n", encoding="utf-8", newline="\n"
    )


class SyntheticDerivationTest(unittest.TestCase):
    def _baseline_tmp(self, src):
        doc, _ = build_baseline_via_lib(src, SYN_SPEC)
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8", newline="\n"
        )
        tmp.write(json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n")
        tmp.close()
        self.addCleanup(os.unlink, tmp.name)
        return Path(tmp.name), doc

    def test_code_aggregates(self):
        base_path, doc = self._baseline_tmp(CODE_SRC)
        proc = run_artifacts(CODE_SRC, SYN_SPEC, base_path)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        got = json.loads(proc.stdout)
        self.assertEqual(
            got["aggregates"]["coordination"], {"files": 2, "bytes": 83}
        )
        self.assertEqual(
            got["aggregates"]["human_source"], {"files": 1, "bytes": 25}
        )
        self.assertEqual(got["aggregates"]["log_raw"], {"files": 2, "bytes": 54})
        self.assertEqual(
            got["aggregates"]["mechanical_evidence"], {"files": 1, "bytes": 29}
        )
        self.assertEqual(
            got["aggregates"]["reproducible_scratch"], {"files": 1, "bytes": 13}
        )
        self.assertEqual(got["totals"], {"files": 7, "bytes": 204})
        self.assertEqual(got["manifest"], doc["manifest"])
        self.assertEqual(len(got["manifest"]), 64)

    def test_diagnostic_readonly_aggregates(self):
        base_path, _ = self._baseline_tmp(DIAG_SRC)
        proc = run_artifacts(DIAG_SRC, SYN_SPEC, base_path)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        got = json.loads(proc.stdout)
        self.assertEqual(
            got["aggregates"]["coordination"], {"files": 2, "bytes": 86}
        )
        self.assertEqual(
            got["aggregates"]["human_source"], {"files": 1, "bytes": 28}
        )
        self.assertEqual(got["aggregates"]["log_raw"], {"files": 1, "bytes": 15})
        self.assertEqual(
            got["aggregates"]["mechanical_evidence"], {"files": 1, "bytes": 30}
        )
        self.assertEqual(
            got["aggregates"]["reproducible_scratch"], {"files": 0, "bytes": 0}
        )
        self.assertEqual(got["totals"], {"files": 5, "bytes": 159})
        self.assertEqual(got["duplicates"]["groups"], 0)
        self.assertEqual(got["duplicates"]["files"], 0)

    def test_docs_duplicates(self):
        base_path, _ = self._baseline_tmp(DOCS_SRC)
        proc = run_artifacts(DOCS_SRC, SYN_SPEC, base_path)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        got = json.loads(proc.stdout)
        self.assertEqual(
            got["aggregates"]["coordination"], {"files": 2, "bytes": 76}
        )
        self.assertEqual(
            got["aggregates"]["human_source"], {"files": 3, "bytes": 64}
        )
        self.assertEqual(got["aggregates"]["log_raw"], {"files": 0, "bytes": 0})
        self.assertEqual(
            got["aggregates"]["mechanical_evidence"], {"files": 1, "bytes": 29}
        )
        self.assertEqual(
            got["aggregates"]["reproducible_scratch"], {"files": 1, "bytes": 13}
        )
        self.assertEqual(got["totals"], {"files": 7, "bytes": 182})
        dup = got["duplicates"]
        self.assertEqual(dup["groups"], 1)
        self.assertEqual(dup["files"], 2)
        self.assertEqual(dup["physical_bytes"], 34)
        self.assertEqual(dup["unique_bytes"], 17)
        self.assertEqual(dup["repeated_bytes"], 17)
        self.assertEqual(len(dup["group_list"]), 1)

    def test_code_duplicates(self):
        base_path, _ = self._baseline_tmp(CODE_SRC)
        got = json.loads(run_artifacts(CODE_SRC, SYN_SPEC, base_path).stdout)
        self.assertEqual(got["duplicates"]["groups"], 1)
        self.assertEqual(got["duplicates"]["files"], 2)
        self.assertEqual(got["duplicates"]["physical_bytes"], 54)
        self.assertEqual(got["duplicates"]["unique_bytes"], 27)
        self.assertEqual(got["duplicates"]["repeated_bytes"], 27)

    def test_repetition_small(self):
        base_path, _ = self._baseline_tmp(CODE_SRC)
        got = json.loads(run_artifacts(CODE_SRC, SYN_SPEC, base_path).stdout)
        rep = got["repetition"]
        self.assertEqual(rep["kind"], "exact_repetition")
        self.assertEqual(rep["thresholds"], [2, 5, 10])
        self.assertEqual(rep["top_n"], 25)
        self.assertEqual(rep["totals"]["files"], 2)
        full = rep["full"]["without_empty"]["2"]
        self.assertEqual(
            (full["distinct"], full["occurrences"], full["redundant"]), (1, 2, 1)
        )
        for entry in rep["top"]:
            self.assertEqual(entry["kind"], "candidate")
            self.assertIn("line_sha256", entry)
            self.assertNotIn("text", entry)
            self.assertNotIn("line", [k for k in entry.keys() if k == "line"])
            self.assertEqual(len(entry["line_sha256"]), 64)
            self.assertGreaterEqual(entry["files"], 2)
        note = rep["note"].lower()
        self.assertIn("false", note)
        self.assertIn("candidate", json.dumps(rep).lower())

    def test_docs_repetition(self):
        base_path, _ = self._baseline_tmp(DOCS_SRC)
        got = json.loads(run_artifacts(DOCS_SRC, SYN_SPEC, base_path).stdout)
        rep = got["repetition"]
        self.assertEqual(rep["totals"]["files"], 2)
        full = rep["full"]["without_empty"]["2"]
        self.assertEqual(
            (full["distinct"], full["occurrences"], full["redundant"]), (2, 4, 2)
        )
        self.assertEqual(len(rep["top"]), 2)
        for entry in rep["top"]:
            self.assertGreaterEqual(entry["files"], 2)

    def test_three_fixtures_represent_natures_by_rules(self):
        rules = _syn_rules()
        code_rels = sorted(
            p.relative_to(CODE_SRC).as_posix()
            for p in CODE_SRC.rglob("*")
            if p.is_file()
        )
        diag_rels = sorted(
            p.relative_to(DIAG_SRC).as_posix()
            for p in DIAG_SRC.rglob("*")
            if p.is_file()
        )
        docs_rels = sorted(
            p.relative_to(DOCS_SRC).as_posix()
            for p in DOCS_SRC.rglob("*")
            if p.is_file()
        )
        # code: coordination + real file in src/ + evidence + log + build/cache
        self.assertTrue(any(r.startswith("coord/") for r in code_rels))
        self.assertIn("src/app.py", code_rels)
        self.assertEqual(_rule_of("src/app.py", rules), ["human_source"])
        self.assertIn("evidence/check.py", code_rels)
        self.assertEqual(
            _rule_of("evidence/check.py", rules), ["mechanical_evidence"]
        )
        self.assertTrue(any(r.startswith("logs/") for r in code_rels))
        for r in [x for x in code_rels if x.startswith("logs/")]:
            self.assertEqual(_rule_of(r, rules), ["log_raw"])
        self.assertTrue(any(r.startswith("build/") for r in code_rels))
        for r in [x for x in code_rels if x.startswith("build/")]:
            self.assertEqual(_rule_of(r, rules), ["reproducible_scratch"])
        for r in [x for x in code_rels if x.startswith("coord/")]:
            self.assertEqual(_rule_of(r, rules), ["coordination"])
        # diagnostic read-only: coordination + analysis/note + evidence + log,
        # without implementation source
        self.assertTrue(any(r.startswith("coord/") for r in diag_rels))
        self.assertIn("notes/finding.md", diag_rels)
        self.assertEqual(_rule_of("notes/finding.md", rules), ["human_source"])
        self.assertIn("evidence/check.py", diag_rels)
        self.assertIn("logs/capture.json", diag_rels)
        self.assertEqual(
            [r for r in diag_rels if r.startswith("src/")], []
        )
        self.assertEqual(
            [r for r in diag_rels if r.startswith("build/") or r.startswith("cache/")],
            [],
        )
        for r in diag_rels:
            self.assertEqual(len(_rule_of(r, rules)), 1)
        # documentation/configuration: coordination + docs/ + config/ +
        # evidence and cache/preview
        self.assertTrue(any(r.startswith("coord/") for r in docs_rels))
        self.assertIn("docs/guide.md", docs_rels)
        self.assertEqual(_rule_of("docs/guide.md", rules), ["human_source"])
        self.assertIn("config/settings.json", docs_rels)
        self.assertEqual(
            _rule_of("config/settings.json", rules), ["human_source"]
        )
        self.assertIn("evidence/check.py", docs_rels)
        self.assertIn("cache/preview.dat", docs_rels)
        self.assertEqual(
            _rule_of("cache/preview.dat", rules), ["reproducible_scratch"]
        )
        self.assertEqual([r for r in docs_rels if r.startswith("src/")], [])
        self.assertEqual([r for r in docs_rels if r.startswith("logs/")], [])

    def test_top_requires_min_threshold(self):
        # Would fail before the fix: unique lines filled top up to top_n.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "src"
            _write_minimal_source(root)
            (root / "coord" / "morning-01.md").write_text(
                "Shared marker\nUnique alpha A\nUnique alpha B\n",
                encoding="utf-8",
                newline="\n",
            )
            (root / "coord" / "evening-01.md").write_text(
                "Shared marker\nUnique beta A\nUnique beta B\n",
                encoding="utf-8",
                newline="\n",
            )
            doc, _ = build_baseline_via_lib(root, SYN_SPEC)
            fd, name = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            Path(name).write_text(
                json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8"
            )
            self.addCleanup(os.unlink, name)
            proc = run_artifacts(root, SYN_SPEC, Path(name))
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            got = json.loads(proc.stdout)
            top = got["repetition"]["top"]
            self.assertEqual(len(top), 1)
            self.assertEqual(top[0]["files"], 2)
            self.assertEqual(top[0]["occurrences"], 2)
            for entry in top:
                self.assertGreaterEqual(entry["files"], 2)


class ExclusiveCoverageTest(unittest.TestCase):
    def _tmp_spec(self, rules, scopes):
        doc = {
            "format": "om-benchmark-artifacts-spec/1",
            "rules": rules,
            "text_scopes": scopes,
            "thresholds": [2, 5, 10],
            "top_n": 25,
        }
        fd, name = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        Path(name).write_text(
            json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        self.addCleanup(os.unlink, name)
        return Path(name)

    def _tmp_base(self, src, spec):
        doc, _ = build_baseline_via_lib(src, spec)
        fd, name = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        Path(name).write_text(
            json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        self.addCleanup(os.unlink, name)
        return Path(name)

    def _reseal(self, base_path, spec_path):
        doc = load_json(base_path)
        doc["spec_sha256"] = hashlib.sha256(
            Path(spec_path).read_bytes()
        ).hexdigest()
        Path(base_path).write_text(
            json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

    def test_file_without_rule_fails_empty_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "src"
            (root / "coord").mkdir(parents=True)
            (root / "coord" / "morning-01.md").write_text(
                "a\n", encoding="utf-8", newline="\n"
            )
            (root / "coord" / "evening-01.md").write_text(
                "b\n", encoding="utf-8", newline="\n"
            )
            (root / "stray.txt").write_text("x\n", encoding="utf-8", newline="\n")
            spec = self._tmp_spec(
                [{"id": "coordination", "pattern": "^coord/[^/]+\\.md$"}],
                [
                    {"id": "scope_evening", "pattern": "^coord/evening-.*\\.md$"},
                    {"id": "scope_morning", "pattern": "^coord/morning-.*\\.md$"},
                ],
            )
            dummy = self._tmp_base(CODE_SRC, SYN_SPEC)
            self._reseal(dummy, spec)
            proc = run_artifacts(root, spec, dummy)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout.strip(), "")

    def test_overlapping_rules_fail(self):
        spec = self._tmp_spec(
            [
                {"id": "coordination", "pattern": "^coord/.*$"},
                {"id": "human_source", "pattern": "^coord/morning-.*\\.md$"},
            ],
            [
                {"id": "scope_evening", "pattern": "^coord/evening-.*\\.md$"},
                {"id": "scope_morning", "pattern": "^coord/morning-.*\\.md$"},
            ],
        )
        dummy = self._tmp_base(CODE_SRC, SYN_SPEC)
        self._reseal(dummy, spec)
        proc = run_artifacts(CODE_SRC, spec, dummy)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.strip(), "")

    def test_invalid_regex_fails(self):
        spec_doc = {
            "format": "om-benchmark-artifacts-spec/1",
            "rules": [{"id": "coordination", "pattern": "([unclosed"}],
            "text_scopes": [
                {"id": "scope_evening", "pattern": "^coord/evening-.*\\.md$"},
                {"id": "scope_morning", "pattern": "^coord/morning-.*\\.md$"},
            ],
            "thresholds": [2, 5, 10],
            "top_n": 25,
        }
        fd, name = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        Path(name).write_text(json.dumps(spec_doc) + "\n")
        self.addCleanup(os.unlink, name)
        dummy = self._tmp_base(CODE_SRC, SYN_SPEC)
        proc = run_artifacts(CODE_SRC, Path(name), dummy)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.strip(), "")

    def test_overlapping_scopes_fail(self):
        spec = self._tmp_spec(
            [
                {"id": "coordination", "pattern": "^coord/[^/]+\\.md$"},
                {"id": "human_source", "pattern": "^src/[^/]+\\.py$"},
                {"id": "log_raw", "pattern": "^logs/[^/]+\\.json$"},
            ],
            [
                {"id": "s1", "pattern": "^coord/.*$"},
                {"id": "s2", "pattern": "^coord/morning-.*\\.md$"},
            ],
        )
        dummy = self._tmp_base(CODE_SRC, SYN_SPEC)
        self._reseal(dummy, spec)
        proc = run_artifacts(CODE_SRC, spec, dummy)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.strip(), "")

    def test_scopes_spanning_rules_fail(self):
        spec = self._tmp_spec(
            [
                {"id": "coordination", "pattern": "^coord/[^/]+\\.md$"},
                {"id": "human_source", "pattern": "^src/[^/]+\\.py$"},
                {"id": "log_raw", "pattern": "^logs/[^/]+\\.json$"},
            ],
            [
                {"id": "s1", "pattern": "^coord/.*\\.md$"},
                {"id": "s2", "pattern": "^src/.*\\.py$"},
            ],
        )
        dummy = self._tmp_base(CODE_SRC, SYN_SPEC)
        self._reseal(dummy, spec)
        proc = run_artifacts(CODE_SRC, spec, dummy)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.strip(), "")


class SealAndBaselineTest(unittest.TestCase):
    def _baseline_for_code(self):
        doc, _ = build_baseline_via_lib(CODE_SRC, SYN_SPEC)
        fd, name = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        Path(name).write_text(
            json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self.addCleanup(os.unlink, name)
        return Path(name), doc

    def test_seal_mismatch_fails_empty(self):
        base, _ = self._baseline_for_code()
        doc = load_json(base)
        doc["spec_sha256"] = "0" * 64
        Path(base).write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n")
        proc = run_artifacts(CODE_SRC, SYN_SPEC, base)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertTrue(proc.stderr.strip() != "")

    def test_baseline_divergence_returns_1_with_report(self):
        base, _ = self._baseline_for_code()
        doc = load_json(base)
        first = next(iter(doc["aggregates"].keys()))
        doc["aggregates"][first]["bytes"] += 1
        Path(base).write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n")
        proc = run_artifacts(CODE_SRC, SYN_SPEC, base)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(proc.stdout.strip() != "")
        self.assertIn("mismatch", proc.stderr.lower())
        got = json.loads(proc.stdout)
        self.assertIn("manifest", got)

    def test_invalid_utf8_in_scope_fails_via_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "src"
            _write_minimal_source(root)
            (root / "coord" / "morning-01.md").write_bytes(b"\xff\xfe bad")
            base, _ = self._baseline_for_code()
            proc = run_artifacts(root, SYN_SPEC, base)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout.strip(), "")
            err = proc.stderr.strip().lower()
            self.assertTrue(err != "")
            self.assertIn("invalid text", err)

    def test_no_out_option(self):
        base, _ = self._baseline_for_code()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            proc = run_artifacts(CODE_SRC, SYN_SPEC, base, extra=["--out", str(out)])
            self.assertEqual(proc.returncode, 2)
            self.assertFalse(out.exists())

    def test_spec_has_no_absolute_root(self):
        text = SYN_SPEC.read_text(encoding="utf-8")
        self.assertNotIn("C:\\", text)
        self.assertNotIn("C:/", text)
        self.assertNotIn("mattc", text.lower())
        self.assertNotIn("neolua", text.lower())
        self.assertNotIn("rathena", text.lower())
        self.assertNotIn("..", text)
        doc = load_json(SYN_SPEC)
        self.assertEqual(doc["thresholds"], [2, 5, 10])
        self.assertEqual(doc["top_n"], 25)
        ids = sorted(r["id"] for r in doc["rules"])
        self.assertEqual(
            ids,
            [
                "coordination",
                "human_source",
                "log_raw",
                "mechanical_evidence",
                "reproducible_scratch",
            ],
        )

    def test_output_has_no_personal_paths(self):
        base, _ = self._baseline_for_code()
        proc = run_artifacts(CODE_SRC, SYN_SPEC, base)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        low = proc.stdout.lower()
        self.assertNotIn("c:\\", low)
        self.assertNotIn("c:/", low)
        self.assertNotIn("mattc", low)
        self.assertNotIn("neolua", low)
        self.assertNotIn("rathena", low)


class DeterminismTest(unittest.TestCase):
    def test_two_runs_match_and_sorted(self):
        doc, _ = build_baseline_via_lib(CODE_SRC, SYN_SPEC)
        fd, name = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        Path(name).write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n")
        self.addCleanup(os.unlink, name)
        first = run_artifacts(CODE_SRC, SYN_SPEC, Path(name))
        second = run_artifacts(CODE_SRC, SYN_SPEC, Path(name))
        self.assertEqual(first.returncode, 0, msg=first.stderr)
        self.assertEqual(second.returncode, 0, msg=second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        parsed = json.loads(first.stdout)
        self.assertEqual(
            first.stdout,
            json.dumps(parsed, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        )

    def test_symlink_fails_when_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "src"
            _write_minimal_source(root)
            target = root / "coord" / "morning-01.md"
            link = root / "coord" / "link.md"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError) as exc:
                self.skipTest("symlink not supported: %s" % exc)
            doc, _ = build_baseline_via_lib(CODE_SRC, SYN_SPEC)
            fd, name = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            doc["spec_sha256"] = hashlib.sha256(
                SYN_SPEC.read_bytes()
            ).hexdigest()
            Path(name).write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n")
            self.addCleanup(os.unlink, name)
            proc = run_artifacts(root, SYN_SPEC, Path(name))
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout.strip(), "")


class SmallAndGenericTest(unittest.TestCase):
    def test_om_py_small(self):
        lines = OM_PATH.read_text(encoding="utf-8").splitlines()
        self.assertLess(len(lines), 380)

    def test_engine_has_no_domain(self):
        text = ART_PATH.read_text(encoding="utf-8")
        low = text.lower()
        for bad in ("neolua", "rathena"):
            self.assertNotIn(bad, low)
        for bad in ("pedido", "retorno", "despacho", "execucao", "continuacao", "citacao"):
            self.assertNotIn(bad, low)
        self.assertNotIn("translate_item_scripts", text)
        for bad in ("32831762", "22827061", "7651309", "1424898"):
            self.assertNotIn(bad, text)
        self.assertNotIn("mattc", low)
        self.assertNotIn("c:\\", low)
        self.assertNotIn("c:/", low)

    def test_engine_has_no_lua_substring(self):
        low = ART_PATH.read_text(encoding="utf-8").lower()
        self.assertNotIn("lua", low)

    def test_fixtures_have_no_domain_or_personal(self):
        bad_tokens = ("c:\\", "c:/", "mattc", "neolua", "rathena")
        for root in (CODE_SRC, DIAG_SRC, DOCS_SRC):
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(SYN_ROOT).as_posix()
                self.assertNotIn("..", rel)
                self.assertFalse(path.is_absolute() and ".." in str(path))
                rel_low = rel.lower()
                for bad in bad_tokens:
                    self.assertNotIn(bad, rel_low, msg=rel)
                try:
                    txt = path.read_bytes().decode("utf-8-sig")
                except UnicodeDecodeError:
                    self.fail("fixture not readable: %s" % rel)
                low = txt.lower()
                for bad in bad_tokens:
                    self.assertNotIn(bad, low, msg=rel)


class CanonicalHistoryTest(unittest.TestCase):
    def history_root(self):
        raw = os.environ.get(HISTORY_ENV)
        if not raw:
            self.skipTest("integration requires %s" % HISTORY_ENV)
        root = Path(raw)
        self.assertTrue(root.is_dir(), msg=str(root))
        return root

    def test_canonical_numbers(self):
        root = self.history_root()
        proc = run_artifacts(root, CANON_SPEC, CANON_BASE)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["format"], "om-benchmark-artifacts/1")
        self.assertEqual(doc["manifest"], "900a2c13c0aa76825fbae5ebe70d398396b78c261dc02f8358d063395964ce0b")
        self.assertEqual(doc["totals"], {"files": 417, "bytes": 32831762})
        agg = doc["aggregates"]
        self.assertEqual(agg["coordination"], {"files": 110, "bytes": 433365})
        self.assertEqual(agg["human_source"], {"files": 97, "bytes": 495129})
        self.assertEqual(agg["log_raw"], {"files": 87, "bytes": 22827061})
        self.assertEqual(agg["mechanical_evidence"], {"files": 9, "bytes": 1424898})
        self.assertEqual(agg["reproducible_scratch"], {"files": 114, "bytes": 7651309})
        dup = doc["duplicates"]
        self.assertEqual(dup["groups"], 34)
        self.assertEqual(dup["files"], 82)
        self.assertEqual(dup["physical_bytes"], 13888763)
        self.assertEqual(dup["unique_bytes"], 6141007)
        self.assertEqual(dup["repeated_bytes"], 7747756)
        rep = doc["repetition"]
        self.assertEqual(rep["totals"]["files"], 109)
        self.assertEqual(rep["totals"]["bytes_raw"], 433167)
        self.assertEqual(rep["totals"]["lines"], 7246)
        self.assertEqual(rep["totals"]["lines_nonempty"], 6079)
        self.assertEqual(rep["totals"]["lines_empty"], 1167)
        self.assertEqual(rep["totals"]["text_bytes"], 426030)
        without = rep["full"]["without_empty"]
        self.assertEqual(
            (without["2"]["distinct"], without["2"]["occurrences"], without["2"]["redundant"]),
            (304, 1528, 1224),
        )
        self.assertEqual(
            (without["5"]["distinct"], without["5"]["occurrences"], without["5"]["redundant"]),
            (73, 962, 889),
        )
        self.assertEqual(
            (without["10"]["distinct"], without["10"]["occurrences"], without["10"]["redundant"]),
            (40, 765, 725),
        )
        self.assertEqual(len(rep["top"]), 25)
        for entry in rep["top"]:
            self.assertGreaterEqual(entry["files"], 2)

    def test_probes_are_human_and_raw_not(self):
        root = self.history_root()
        spec = load_json(CANON_SPEC)
        rules = [(r["id"], re.compile(r["pattern"])) for r in spec["rules"]]
        def rule_of(rel):
            hits = [rid for rid, rx in rules if rx.fullmatch(rel) is not None]
            self.assertEqual(len(hits), 1, msg=rel)
            return hits[0]
        for name in ("probe-10a.py", "probe-11a.py", "probe-13b.py"):
            self.assertEqual(rule_of(name), "human_source", msg=name)
        for name in (
            "neolua-08c/raw-08c-re.json",
            "neolua-08c/raw-08c-pre-re.json",
            "neolua-08c/compile-08c-re.txt",
        ):
            self.assertEqual(rule_of(name), "log_raw", msg=name)
        self.assertEqual(rule_of("baseline-08a/translate_item_scripts.py"), "mechanical_evidence")
        self.assertEqual(
            rule_of("baseline-08a/__pycache__/translate_item_scripts.cpython-313.pyc"),
            "reproducible_scratch",
        )

    def test_canonical_seals_and_smallness(self):
        root = self.history_root()
        spec_text = CANON_SPEC.read_text(encoding="utf-8")
        self.assertNotIn("C:\\", spec_text)
        self.assertNotIn("C:/", spec_text)
        self.assertNotIn("mattc", spec_text.lower())
        base = load_json(CANON_BASE)
        self.assertEqual(base["spec_sha256"], file_sha(CANON_SPEC))
        blob = CANON_BASE.read_text(encoding="utf-8")
        self.assertNotIn("pedido-13-a.md", blob)
        self.assertLess(len(blob.encode("utf-8")), 100 * 1024)
        proc = run_artifacts(root, CANON_SPEC, CANON_BASE)
        self.assertNotIn("C:\\", proc.stdout)
        self.assertNotIn("C:/", proc.stdout)
        self.assertNotIn("mattc", proc.stdout.lower())
        doc = json.loads(proc.stdout)
        for entry in doc["repetition"]["top"]:
            self.assertNotIn("text", entry)

    def test_canonical_determinism(self):
        root = self.history_root()
        first = run_artifacts(root, CANON_SPEC, CANON_BASE)
        second = run_artifacts(root, CANON_SPEC, CANON_BASE)
        self.assertEqual(first.returncode, 0, msg=first.stderr)
        self.assertEqual(second.returncode, 0, msg=second.stderr)
        self.assertEqual(first.stdout, second.stdout)


if __name__ == "__main__":
    unittest.main()

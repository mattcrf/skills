"""Tests for the three-case replay benchmark (portable + optional history)."""

import hashlib
import importlib.util
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
REPO_DIR = ORQ_DIR.parent
OM_PATH = ORQ_DIR / "scripts" / "om.py"
MODULE_PATH = ORQ_DIR / "scripts" / "_om_replay.py"
BENCH_DIR = ORQ_DIR / "manutencao" / "benchmarks"
SPEC_PATH = BENCH_DIR / "lua-translator-02-replay-spec.json"
BASELINE_PATH = BENCH_DIR / "lua-translator-02-replay.json"
LEGACY_PATH = BENCH_DIR / "lua-translator-02.json"
HISTORY_ENV = "OM_PHASE_A_HISTORY"
HEX64_RE = re.compile(r"[0-9a-f]{64}")
CASE_SHAPES = {
    "simple": "simple",
    "correction": "correction_continuation",
    "manager_batch": "manager_batch",
}
CASE_TASKS = {"simple": ["01-a"], "correction": ["13-a", "13-b"], "manager_batch": ["08-a", "08-c"]}
CASE_ORIGINALS = {
    "simple": ["pedido-01-a.md"],
    "correction": ["pedido-13-a.md", "pedido-13-b.md"],
    "manager_batch": ["pedido-08-a.md", "pedido-08-c.md"],
}
FORBIDDEN_ENGINE_WORDS = (
    "lua",
    "rathena",
    "neolua",
    "autobonus",
    "translator",
    "switch",
    "410028",
    "18985",
    "c1ec49e",
    "9e5cfeb",
    "pedido",
    "retorno",
    "despacho",
    "execucao",
    "continuacao",
    "octal",
    "styled",
)


def load_replay():
    spec = importlib.util.spec_from_file_location("om_replay_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_replay(spec, baseline):
    return subprocess.run(
        [
            sys.executable,
            "-B",
            str(OM_PATH),
            "benchmark",
            "replay",
            "--spec",
            str(spec),
            "--baseline",
            str(baseline),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def synthetic_spec():
    return {
        "format": "om-benchmark-replay-spec/1",
        "operation": {
            "current_context": 1,
            "profiles": {"scout": ["read-only"], "implementer": ["mutating"]},
        },
        "limits": {"task_bytes_max": 2000, "task_words_max": 250},
        "sources": [
            {
                "id": "origin-a.md",
                "bytes": 120,
                "words": 20,
                "sha256": "ab" * 32,
            }
        ],
        "cases": [
            {
                "id": "unit",
                "shape": "unit",
                "original_source_ids": ["origin-a.md"],
                "required_items": ["U1-OBJ.1", "U1-RET.1"],
                "tasks": [
                    {
                        "id": "u-1",
                        "kind": "scout",
                        "effect": "read-only",
                        "profile": "scout",
                        "context": 1,
                        "depends": [],
                        "sections": [
                            {
                                "field": "goal",
                                "heading": "Goal",
                                "text": "Do the unit thing.",
                            },
                            {
                                "field": "return",
                                "heading": "Return",
                                "text": "Report the unit thing.",
                            },
                        ],
                        "items": {"U1-OBJ.1": "goal", "U1-RET.1": "return"},
                    }
                ],
            }
        ],
    }


def write_json(path, doc):
    Path(path).write_text(
        json.dumps(doc, sort_keys=False, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return Path(path)


def build_baseline(spec_path, dest):
    module = load_replay()
    raw = Path(spec_path).read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest().lower()
    spec = module.check_spec(json.loads(raw.decode("utf-8-sig")), Path(spec_path))
    ordered = module.order_tasks(spec["cases"])
    validation = module.validate_generated(spec["operation"], ordered)
    document = module.build_report(spec, sha256, ordered, validation)
    Path(dest).write_text(
        json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return document


class CanonicalReplayTest(unittest.TestCase):
    def test_frozen_baseline_matches(self):
        proc = run_replay(SPEC_PATH, BASELINE_PATH)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(proc.stderr, "")

    def test_stdout_is_the_frozen_report(self):
        proc = run_replay(SPEC_PATH, BASELINE_PATH)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(json.loads(proc.stdout), load_json(BASELINE_PATH))

    def test_report_is_deterministic(self):
        first = run_replay(SPEC_PATH, BASELINE_PATH)
        second = run_replay(SPEC_PATH, BASELINE_PATH)
        self.assertEqual(first.returncode, 0, msg=first.stderr)
        self.assertEqual(second.returncode, 0, msg=second.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def test_three_shapes_tasks_and_relations(self):
        report = load_json(BASELINE_PATH)
        self.assertEqual([case["id"] for case in report["cases"]], list(CASE_SHAPES))
        for case in report["cases"]:
            self.assertEqual(case["shape"], CASE_SHAPES[case["id"]])
            self.assertEqual([task["id"] for task in case["tasks"]], CASE_TASKS[case["id"]])
            self.assertEqual(case["original_sources"], CASE_ORIGINALS[case["id"]])
        correction = next(c for c in report["cases"] if c["id"] == "correction")
        self.assertEqual(
            correction["relation"], {
                "kind": "correction_dependency",
                "verified": True,
                "items": [],
                "from": "13-b",
                "to": "13-a",
            }
        )
        self.assertEqual(correction["tasks"][1]["depends"], ["13-a"])
        batch = next(c for c in report["cases"] if c["id"] == "manager_batch")
        self.assertEqual(batch["relation"]["kind"], "parallel_independence")
        self.assertEqual(batch["relation"]["writer"], "08-a")
        self.assertTrue(batch["relation"]["independent"])
        self.assertEqual(batch["relation"]["items"], ["M-LOAD.1", "M0-DS.1"])
        self.assertEqual(batch["relation"]["read_only"], ["08-c"])
        effects = {task["id"]: task["effect"] for task in batch["tasks"]}
        self.assertEqual(effects, {"08-a": "mutating", "08-c": "read-only"})
        for task in batch["tasks"]:
            self.assertEqual(task["depends"], [])

    def test_coverage_and_limits_hold(self):
        report = load_json(BASELINE_PATH)
        limits = report["limits"]
        self.assertEqual(limits, {"task_bytes_max": 2000, "task_words_max": 250})
        coverage = report["coverage"]
        self.assertEqual(coverage["required"], coverage["mapped"])
        self.assertEqual(coverage["missing"], [])
        self.assertEqual(coverage["percent"], 100.0)
        for case in report["cases"]:
            for task in case["tasks"]:
                self.assertTrue(task["within_limits"], msg=task["id"])
                self.assertLessEqual(task["bytes"], limits["task_bytes_max"])
                self.assertLessEqual(task["words"], limits["task_words_max"])
                self.assertEqual(task["missing_items"], [])
        average = report["average_task"]
        self.assertTrue(average["within_limits"])
        self.assertLessEqual(average["bytes"], limits["task_bytes_max"])
        self.assertLessEqual(average["words"], limits["task_words_max"])
        self.assertLessEqual(average["bytes"], 2000)
        self.assertLessEqual(average["words"], 250)

    def test_reductions_are_measured_not_fixed(self):
        report = load_json(BASELINE_PATH)
        for case in report["cases"]:
            original = case["original"]
            generated = case["generated"]
            self.assertGreater(original["bytes"], generated["bytes"])
            self.assertGreater(original["words"], generated["words"])
            expected_bytes = (
                (original["bytes"] - generated["bytes"]) / original["bytes"] * 100.0
            )
            expected_words = (
                (original["words"] - generated["words"]) / original["words"] * 100.0
            )
            self.assertEqual(case["reduction_percent"]["bytes"], expected_bytes)
            self.assertEqual(case["reduction_percent"]["words"], expected_words)

    def test_validation_outcome_is_recorded(self):
        report = load_json(BASELINE_PATH)
        self.assertEqual(
            report["validation"],
            {"tasks": 5, "ok": 5, "failed": [], "doctor": "ok"},
        )

    def test_algorithm_and_provenance_are_sealed(self):
        report = load_json(BASELINE_PATH)
        self.assertEqual(report["format"], "om-benchmark-replay/1")
        self.assertEqual(
            set(report["algorithm"]), {"bytes", "note", "words"}
        )
        self.assertIn("\\S+", report["algorithm"]["words"])
        self.assertIn("byte", report["algorithm"]["bytes"])
        self.assertEqual(report["spec_sha256"], file_sha(SPEC_PATH))
        self.assertEqual(report["provenance"]["spec_sha256"], report["spec_sha256"])
        self.assertTrue(HEX64_RE.fullmatch(report["spec_sha256"]))


class SpecAlignmentTest(unittest.TestCase):
    def test_sources_match_the_frozen_phase_a_fixture(self):
        spec = load_json(SPEC_PATH)
        records = {r["path"]: r for r in load_json(LEGACY_PATH)["files"]}
        self.assertEqual(len(spec["sources"]), 18)
        for source in spec["sources"]:
            with self.subTest(source=source["id"]):
                record = records.get(source["id"])
                self.assertIsNotNone(record, msg="not in the legacy fixture")
                self.assertEqual(source["sha256"], record["sha256"])
                self.assertEqual(source["bytes"], record["bytes"])
                self.assertEqual(source["words"], record["words"])

    def test_required_items_match_the_declared_mapping(self):
        spec = load_json(SPEC_PATH)
        seen = set()
        for case in spec["cases"]:
            mapped = set()
            for task in case["tasks"]:
                mapped.update(task["items"])
            relation = case.get("relation")
            if relation is not None and relation["kind"] == "parallel_independence":
                mapped.update(relation["items"])
            self.assertEqual(sorted(mapped), sorted(case["required_items"]))
            self.assertFalse(seen & mapped, msg="duplicate item id across cases")
            seen |= mapped
        self.assertEqual(len(seen), 96)

    def test_engine_uses_no_case_vocabulary(self):
        text = MODULE_PATH.read_text(encoding="utf-8").lower()
        for word in FORBIDDEN_ENGINE_WORDS:
            self.assertNotIn(word, text, msg=word)

    def test_no_generated_task_files_are_committed(self):
        names = {path.name for path in BENCH_DIR.iterdir()}
        self.assertNotIn("01-a.md", names)
        self.assertNotIn("13-b.md", names)
        self.assertNotIn("08-c.md", names)
        self.assertFalse(any(path.suffix == ".md" for path in BENCH_DIR.iterdir()))

    def test_replay_writes_nothing_beside_stdout(self):
        before = {
            path.name: (file_sha(path), path.stat().st_mtime_ns)
            for path in BENCH_DIR.iterdir()
            if path.is_file()
        }
        proc = run_replay(SPEC_PATH, BASELINE_PATH)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        after = {
            path.name: (file_sha(path), path.stat().st_mtime_ns)
            for path in BENCH_DIR.iterdir()
            if path.is_file()
        }
        self.assertEqual(before, after)


class SyntheticReplayTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def round_trip(self, spec_doc):
        spec_path = write_json(self.root / "spec.json", spec_doc)
        baseline_path = self.root / "baseline.json"
        build_baseline(spec_path, baseline_path)
        return run_replay(spec_path, baseline_path)

    def rejected_round_trip(self, spec_doc):
        spec_path = write_json(self.root / "spec.json", spec_doc)
        return run_replay(spec_path, self.root / "missing-baseline.json")

    def test_synthetic_round_trip(self):
        proc = self.round_trip(synthetic_spec())
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["format"], "om-benchmark-replay/1")
        self.assertEqual(report["coverage"]["percent"], 100.0)
        self.assertEqual(report["validation"]["failed"], [])
        self.assertEqual(report["validation"]["doctor"], "ok")
        task = report["cases"][0]["tasks"][0]
        self.assertEqual(sorted(task["mapped_items"]), ["U1-OBJ.1", "U1-RET.1"])

    def test_unmapped_required_item_is_rejected(self):
        doc = synthetic_spec()
        doc["cases"][0]["required_items"].append("U1-N.1")
        proc = self.rejected_round_trip(doc)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertIn("invalid spec", proc.stderr)

    def test_unknown_mapped_item_is_rejected(self):
        doc = synthetic_spec()
        doc["cases"][0]["tasks"][0]["items"]["U1-X.9"] = "goal"
        proc = self.rejected_round_trip(doc)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertIn("invalid spec", proc.stderr)

    def test_dependency_outside_the_case_is_rejected(self):
        doc = synthetic_spec()
        doc["cases"][0]["tasks"][0]["depends"] = ["missing-task"]
        proc = self.rejected_round_trip(doc)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertIn("invalid spec", proc.stderr)

    def test_relation_writer_must_be_the_only_mutating_task(self):
        doc = synthetic_spec()
        case = doc["cases"][0]
        case["tasks"][0]["items"] = {"U1-OBJ.1": "goal"}
        case["tasks"].append(
            {
                "id": "u-2",
                "kind": "writer",
                "effect": "mutating",
                "profile": "implementer",
                "context": 1,
                "depends": [],
                "sections": [
                    {"field": "return", "heading": "Return", "text": "Report it."}
                ],
                "items": {"U1-RET.1": "return"},
            }
        )
        case["relation"] = {
            "kind": "parallel_independence",
            "writer": "u-1",
        }
        proc = self.rejected_round_trip(doc)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertIn("invalid spec relation", proc.stderr)

    def test_correction_relation_requires_the_dependency(self):
        doc = synthetic_spec()
        case = doc["cases"][0]
        case["tasks"][0]["items"] = {"U1-OBJ.1": "goal"}
        case["tasks"].append(
            {
                "id": "u-2",
                "kind": "writer",
                "effect": "mutating",
                "profile": "implementer",
                "context": 1,
                "depends": [],
                "sections": [
                    {"field": "return", "heading": "Return", "text": "Report it."}
                ],
                "items": {"U1-RET.1": "return"},
            }
        )
        case["relation"] = {
            "kind": "correction_dependency",
            "from": "u-2",
            "to": "u-1",
        }
        proc = self.rejected_round_trip(doc)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("invalid spec relation", proc.stderr)

    def test_baseline_mismatch_fails_with_diagnostics(self):
        doc = synthetic_spec()
        spec_path = write_json(self.root / "spec.json", doc)
        baseline_path = self.root / "baseline.json"
        build_baseline(spec_path, baseline_path)
        broken = load_json(baseline_path)
        broken["average_task"]["bytes"] += 1.0
        write_json(baseline_path, broken)
        proc = run_replay(spec_path, baseline_path)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("mismatch: average_task differs", proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["coverage"]["percent"], 100.0)

    def test_spec_seal_mismatch_fails(self):
        doc = synthetic_spec()
        spec_path = write_json(self.root / "spec.json", doc)
        baseline_path = self.root / "baseline.json"
        build_baseline(spec_path, baseline_path)
        spec_path.write_text(
            spec_path.read_text(encoding="utf-8").replace("unit thing", "unit work"),
            encoding="utf-8",
            newline="\n",
        )
        proc = run_replay(spec_path, baseline_path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("spec seal mismatch", proc.stderr)

    def test_exceeding_limits_fails_without_a_baseline(self):
        doc = synthetic_spec()
        doc["limits"]["task_words_max"] = 1
        spec_path = write_json(self.root / "spec.json", doc)
        baseline_path = self.root / "baseline.json"
        build_baseline(spec_path, baseline_path)
        proc = run_replay(spec_path, baseline_path)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("replay exceeds task limits", proc.stderr)


class ControlPublishTest(unittest.TestCase):
    def test_generated_tasks_publish_and_pass_doctor(self):
        module = load_replay()
        raw = SPEC_PATH.read_bytes()
        spec = module.check_spec(json.loads(raw.decode("utf-8-sig")), SPEC_PATH)
        ordered = module.order_tasks(spec["cases"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lines = [
                'format = "om-operation/1"',
                'id = "replay-validation"',
                'project_root = "%s"' % root.as_posix(),
                "current_context = 1",
                "",
            ]
            for name in sorted(spec["operation"]["profiles"]):
                lines.append("[profiles.%s]" % name)
                lines.append(
                    "effects = [%s]"
                    % ", ".join(
                        '"%s"' % effect
                        for effect in spec["operation"]["profiles"][name]
                    )
                )
                lines.append("")
            (root / "operation.toml").write_text(
                "\n".join(lines), encoding="utf-8", newline="\n"
            )
            drafts = root / ".drafts"
            drafts.mkdir()
            for task in ordered:
                draft = drafts / ("%s.md" % task["id"])
                draft.write_bytes(module.render_task(task))
                published = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(OM_PATH),
                        "task",
                        "publish",
                        "--operation",
                        str(root),
                        "--task",
                        str(draft),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=60,
                )
                self.assertEqual(published.returncode, 0, msg=published.stderr)
                self.assertIn("published %s" % task["id"], published.stdout)
            doctor = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(OM_PATH),
                    "doctor",
                    "--operation",
                    str(root),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=60,
            )
            self.assertEqual(doctor.returncode, 0, msg=doctor.stderr)
            self.assertIn("tasks=5 events=5", doctor.stdout)


class CanonicalHistoryTest(unittest.TestCase):
    def test_spec_sources_match_the_history_files(self):
        raw = os.environ.get(HISTORY_ENV)
        if not raw:
            self.skipTest("integration requires %s" % HISTORY_ENV)
        root = Path(raw)
        if not root.is_dir():
            self.fail("history root is not a directory: %s" % root)
        spec = load_json(SPEC_PATH)
        for source in spec["sources"]:
            target = root / source["id"]
            self.assertTrue(target.is_file(), msg=source["id"])
            self.assertEqual(source["sha256"], file_sha(target), msg=source["id"])
            self.assertEqual(source["bytes"], target.stat().st_size, msg=source["id"])


if __name__ == "__main__":
    unittest.main()

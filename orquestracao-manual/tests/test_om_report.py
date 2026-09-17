"""Tests for the deterministic Phase A cost report (portable + canonical)."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
ORQ_DIR = TEST_DIR.parent
OM_PATH = ORQ_DIR / "scripts" / "om.py"
OM_REPORT_PATH = ORQ_DIR / "scripts" / "_om_report.py"
CANONICAL_LEGACY = ORQ_DIR / "manutencao" / "benchmarks" / "lua-translator-02.json"
CANONICAL_QUALITY = ORQ_DIR / "manutencao" / "benchmarks" / "lua-translator-02-quality.json"
CANONICAL_SPEC = (
    ORQ_DIR / "manutencao" / "benchmarks" / "lua-translator-02-report-spec.json"
)
REPORT_DIR = TEST_DIR / "fixtures" / "report"
SYNTHETIC_LEGACY = REPORT_DIR / "synthetic-legacy.json"
SYNTHETIC_QUALITY = REPORT_DIR / "synthetic-quality.json"
SYNTHETIC_SPEC = REPORT_DIR / "synthetic-spec.json"


def run_report(legacy, quality, spec, extra=None):
    cmd = [
        sys.executable,
        "-B",
        str(OM_PATH),
        "benchmark",
        "report",
        "--legacy",
        str(legacy),
        "--quality",
        str(quality),
        "--spec",
        str(spec),
    ]
    if extra:
        cmd += [str(x) for x in extra]
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", timeout=60
    )


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json_tmp(tmpdir, name, doc):
    target = Path(tmpdir) / name
    target.write_text(
        json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return target


class CanonicalIntegrationTest(unittest.TestCase):
    def test_canonical_numbers(self):
        proc = run_report(CANONICAL_LEGACY, CANONICAL_QUALITY, CANONICAL_SPEC)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["format"], "om-report/1")

        full = doc["full_operation_lower_bound"]
        self.assertEqual(full["authored_requests"]["files"], 28)
        self.assertEqual(full["authored_requests"]["words"], 22730)
        self.assertEqual(full["authored_requests"]["bytes"], 173896)
        self.assertEqual(full["received_returns"]["files"], 28)
        self.assertEqual(full["received_returns"]["words"], 25220)
        self.assertEqual(full["received_returns"]["bytes"], 203457)
        self.assertEqual(full["combined"]["words"], 47950)
        self.assertEqual(full["combined"]["bytes"], 377353)

        over = doc["textual_overhead"]
        self.assertEqual((over["dispatch"]["words"], over["dispatch"]["bytes"]), (3428, 32749))
        self.assertEqual(over["dispatch"]["files"], 25)
        self.assertEqual((over["execution"]["words"], over["execution"]["bytes"]), (1518, 12089))
        self.assertEqual(over["execution"]["files"], 25)
        self.assertEqual((over["handoff"]["words"], over["handoff"]["bytes"]), (1600, 10976))
        self.assertEqual(over["handoff"]["files"], 3)
        self.assertEqual(over["known_textual_total"]["words"], 54496)
        self.assertEqual(over["known_textual_total"]["bytes"], 433167)

        sl = doc["replay_slice"]
        self.assertEqual((sl["requests"]["words"], sl["requests"]["bytes"]), (1609, 12485))
        self.assertEqual(sl["requests"]["files"], 2)
        self.assertEqual((sl["returns"]["words"], sl["returns"]["bytes"]), (2803, 21553))
        self.assertEqual(sl["returns"]["files"], 2)
        self.assertEqual(sl["combined"]["words"], 4412)
        self.assertEqual(sl["combined"]["bytes"], 34038)

        quality = doc["frozen_quality"]
        self.assertEqual(quality["required_blocking_ids"], ["D1", "D2", "D3"])
        self.assertEqual(quality["required_blocking_count"], 3)
        self.assertEqual(
            quality["control_case_ids"],
            ["control-10-a", "control-11-a", "control-14-a", "control-read-only-clean"],
        )
        self.assertEqual(quality["control_count"], 4)

        budgets = doc["budgets"]
        self.assertEqual(budgets["authored_requests_words_max"], 5700)
        self.assertEqual(budgets["received_returns_words_max"], 5600)
        self.assertEqual(budgets["combined_words_max"], 11300)
        self.assertEqual(budgets["decision_packet_words_avg_max"], 200)
        self.assertEqual(budgets["resume_capsule_words_max"], 300)
        self.assertEqual(budgets["captain_fixed_context_words_max"], 1400)

        red = doc["reductions_percent"]
        exp_a = (22730 - 5700) / 22730 * 100.0
        exp_r = (25220 - 5600) / 25220 * 100.0
        exp_c = (47950 - 11300) / 47950 * 100.0
        self.assertAlmostEqual(red["authored_requests"], exp_a, places=6)
        self.assertAlmostEqual(red["received_returns"], exp_r, places=6)
        self.assertAlmostEqual(red["combined"], exp_c, places=6)
        # Published one-decimal limits remain verifiable.
        self.assertGreaterEqual(round(red["authored_requests"], 1), 74.9)
        self.assertGreaterEqual(round(red["received_returns"], 1), 77.8)
        self.assertGreaterEqual(round(red["combined"], 1), 76.4)

        for item in doc["unrecoverable"]:
            self.assertEqual(item["status"], "unrecoverable")
            self.assertNotIn("words", item)
            self.assertNotIn("bytes", item)
            self.assertNotIn("value", item)
            self.assertTrue(item["reason"])

        inputs = doc["inputs"]
        self.assertEqual(inputs["legacy_format"], "om-benchmark-legacy/1")
        self.assertEqual(inputs["quality_format"], "om-benchmark-quality/1")
        self.assertEqual(inputs["spec_format"], "om-report-spec/1")
        self.assertEqual(inputs["legacy_sha256"], file_sha256(CANONICAL_LEGACY))
        self.assertEqual(inputs["quality_sha256"], file_sha256(CANONICAL_QUALITY))
        self.assertEqual(inputs["spec_sha256"], file_sha256(CANONICAL_SPEC))
        legacy_doc = load_json(CANONICAL_LEGACY)
        self.assertEqual(inputs["legacy_manifest"], legacy_doc["manifest"])

    def test_canonical_wording(self):
        proc = run_report(CANONICAL_LEGACY, CANONICAL_QUALITY, CANONICAL_SPEC)
        doc = json.loads(proc.stdout)
        text = proc.stdout.lower()
        # Word counts use words, never a tokens unit.
        self.assertNotIn('"tokens"', text)
        self.assertNotIn('"token"', text)
        replay_note = doc["replay_slice"]["note"].lower()
        self.assertIn("denominator", replay_note)
        self.assertIn("not the global target", replay_note)
        self.assertIn("not proof", replay_note)
        full_note = doc["full_operation_lower_bound"]["note"].lower()
        self.assertIn("lower bound", full_note)
        prov_note = doc["provenance"]["note"].lower()
        self.assertIn("lower bound", prov_note)
        self.assertIn("not the total captain work", prov_note)
        # Frozen quality lists IDs, not long claims.
        frozen_text = json.dumps(doc["frozen_quality"]).lower()
        self.assertIn("d1", frozen_text)
        self.assertNotIn("fallthrough", frozen_text)
        self.assertNotIn("octal", frozen_text)


class SyntheticDerivationTest(unittest.TestCase):
    def test_synthetic_totals(self):
        proc = run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, SYNTHETIC_SPEC)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        doc = json.loads(proc.stdout)
        full = doc["full_operation_lower_bound"]
        self.assertEqual((full["authored_requests"]["words"], full["authored_requests"]["bytes"]), (30, 300))
        self.assertEqual((full["received_returns"]["words"], full["received_returns"]["bytes"]), (40, 400))
        self.assertEqual((full["combined"]["words"], full["combined"]["bytes"]), (70, 700))

    def test_separation_of_overhead(self):
        doc = json.loads(run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, SYNTHETIC_SPEC).stdout)
        over = doc["textual_overhead"]
        self.assertEqual((over["dispatch"]["words"], over["dispatch"]["bytes"]), (5, 50))
        self.assertEqual((over["execution"]["words"], over["execution"]["bytes"]), (6, 60))
        self.assertEqual((over["handoff"]["words"], over["handoff"]["bytes"]), (7, 70))
        self.assertEqual(over["known_textual_total"]["words"], 88)
        self.assertEqual(over["known_textual_total"]["bytes"], 880)
        # Technical bound excludes overhead.
        self.assertNotEqual(doc["full_operation_lower_bound"]["combined"]["words"], 88)
        self.assertEqual(
            doc["full_operation_lower_bound"]["combined"]["words"]
            + over["dispatch"]["words"]
            + over["execution"]["words"]
            + over["handoff"]["words"],
            88,
        )

    def test_slice_distinct(self):
        doc = json.loads(run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, SYNTHETIC_SPEC).stdout)
        sl = doc["replay_slice"]
        self.assertEqual((sl["requests"]["words"], sl["requests"]["bytes"]), (10, 100))
        self.assertEqual((sl["returns"]["words"], sl["returns"]["bytes"]), (15, 150))
        self.assertEqual((sl["combined"]["words"], sl["combined"]["bytes"]), (25, 250))
        self.assertLess(sl["combined"]["words"], doc["full_operation_lower_bound"]["combined"]["words"])
        self.assertLess(sl["combined"]["bytes"], doc["full_operation_lower_bound"]["combined"]["bytes"])

    def test_unrecoverable_never_zero(self):
        doc = json.loads(run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, SYNTHETIC_SPEC).stdout)
        self.assertEqual(len(doc["unrecoverable"]), 2)
        for item in doc["unrecoverable"]:
            self.assertEqual(item["status"], "unrecoverable")
            self.assertNotIn("words", item)
            self.assertNotIn("bytes", item)
            self.assertNotIn("value", item)
            self.assertNotIn("count", item)
            self.assertTrue(item["reason"])

    def test_budgets_and_reductions_calculated(self):
        proc = run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, SYNTHETIC_SPEC)
        doc = json.loads(proc.stdout)
        spec = load_json(SYNTHETIC_SPEC)
        for key, value in spec["budgets"].items():
            self.assertEqual(doc["budgets"][key], value)
        red = doc["reductions_percent"]
        self.assertAlmostEqual(red["authored_requests"], (30 - 10) / 30 * 100.0, places=6)
        self.assertAlmostEqual(red["received_returns"], (40 - 12) / 40 * 100.0, places=6)
        self.assertAlmostEqual(red["combined"], (70 - 22) / 70 * 100.0, places=6)

    def test_quality_derived(self):
        doc = json.loads(run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, SYNTHETIC_SPEC).stdout)
        self.assertEqual(doc["frozen_quality"]["required_blocking_ids"], ["O1", "O2"])
        self.assertEqual(doc["frozen_quality"]["required_blocking_count"], 2)
        self.assertEqual(doc["frozen_quality"]["control_case_ids"], ["beta", "clean"])
        self.assertEqual(doc["frozen_quality"]["control_count"], 2)


class SealAndValidationTest(unittest.TestCase):
    def test_legacy_hash_mismatch_fails_without_partial_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "legacy.json"
            doc = load_json(SYNTHETIC_LEGACY)
            doc["files"][0]["words"] += 1
            write_json_tmp(tmp, "legacy.json", doc)
            proc = run_report(tampered, SYNTHETIC_QUALITY, SYNTHETIC_SPEC)
            self.assertEqual(proc.returncode, 2, msg=proc.stdout)
            self.assertEqual(proc.stdout.strip(), "")
            self.assertIn("hash", proc.stderr.lower())

    def test_quality_hash_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tampered = write_json_tmp(tmp, "quality.json", {"format": "x"})
            # Copy real quality then flip one byte to keep JSON valid but hash divergent.
            raw = Path(SYNTHETIC_QUALITY).read_bytes() + b" "
            tampered.write_bytes(raw)
            proc = run_report(SYNTHETIC_LEGACY, tampered, SYNTHETIC_SPEC)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout.strip(), "")
            self.assertTrue(proc.stderr.strip() != "")

    def test_missing_category_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = load_json(SYNTHETIC_SPEC)
            spec["technical"]["authored_requests_category"] = "no_such_category"
            bad = write_json_tmp(tmp, "spec.json", spec)
            # Reseal is intentionally not done: keep original seals by restoring them.
            sealed = load_json(SYNTHETIC_SPEC)
            spec["legacy_sha256"] = sealed["legacy_sha256"]
            spec["quality_sha256"] = sealed["quality_sha256"]
            bad = write_json_tmp(tmp, "spec.json", spec)
            proc = run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, bad)
            self.assertEqual(proc.returncode, 2, msg=proc.stdout)
            self.assertEqual(proc.stdout.strip(), "")
            self.assertIn("category", proc.stderr.lower())

    def test_missing_path_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = load_json(SYNTHETIC_SPEC)
            spec["replay_slice"]["request_paths"] = ["no-such.md"]
            bad = write_json_tmp(tmp, "spec.json", spec)
            proc = run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, bad)
            self.assertEqual(proc.returncode, 2, msg=proc.stdout)
            self.assertEqual(proc.stdout.strip(), "")
            self.assertIn("path", proc.stderr.lower())

    def test_incoherent_budget_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = load_json(SYNTHETIC_SPEC)
            spec["budgets"]["combined_words_max"] = 999
            bad = write_json_tmp(tmp, "spec.json", spec)
            proc = run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, bad)
            self.assertEqual(proc.returncode, 2, msg=proc.stdout)
            self.assertEqual(proc.stdout.strip(), "")
            self.assertIn("budget", proc.stderr.lower())

    def test_invalid_legacy_format_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "legacy.json"
            bad.write_text("not json\n", encoding="utf-8", newline="\n")
            proc = run_report(bad, SYNTHETIC_QUALITY, SYNTHETIC_SPEC)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout.strip(), "")
            self.assertTrue(proc.stderr.strip() != "")

    def test_absolute_spec_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = load_json(SYNTHETIC_SPEC)
            spec["legacy_id"] = "C:/abs/path.json"
            bad = write_json_tmp(tmp, "spec.json", spec)
            proc = run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, bad)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout.strip(), "")

    def test_no_out_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "out.json"
            proc = run_report(
                SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, SYNTHETIC_SPEC, extra=["--out", str(out_file)]
            )
            self.assertEqual(proc.returncode, 2)
            self.assertFalse(out_file.exists())

    def test_spec_seals_match_files_and_ids_relative(self):
        for spec_path, legacy_path, quality_path in (
            (SYNTHETIC_SPEC, SYNTHETIC_LEGACY, SYNTHETIC_QUALITY),
            (CANONICAL_SPEC, CANONICAL_LEGACY, CANONICAL_QUALITY),
        ):
            spec = load_json(spec_path)
            self.assertEqual(spec["legacy_sha256"], file_sha256(legacy_path))
            self.assertEqual(spec["quality_sha256"], file_sha256(quality_path))
            for value in (spec["legacy_id"], spec["quality_id"]):
                self.assertFalse(value.startswith("/"))
                self.assertNotIn(":", value)
                self.assertNotIn("..", value)
            for value in spec["replay_slice"]["request_paths"] + spec["replay_slice"]["return_paths"]:
                self.assertFalse(value.startswith("/"))
                self.assertNotIn(":", value)


class DeterministicOutputTest(unittest.TestCase):
    def test_two_runs_match_and_sorted(self):
        first = run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, SYNTHETIC_SPEC)
        second = run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, SYNTHETIC_SPEC)
        self.assertEqual(first.returncode, 0, msg=first.stderr)
        self.assertEqual(second.returncode, 0, msg=second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        parsed = json.loads(first.stdout)
        self.assertEqual(
            first.stdout,
            json.dumps(parsed, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        )

    def test_canonical_deterministic(self):
        first = run_report(CANONICAL_LEGACY, CANONICAL_QUALITY, CANONICAL_SPEC)
        second = run_report(CANONICAL_LEGACY, CANONICAL_QUALITY, CANONICAL_SPEC)
        self.assertEqual(first.stdout, second.stdout)

    def test_inputs_unchanged(self):
        def snapshot(paths):
            return {str(p): (file_sha256(p), Path(p).stat().st_mtime_ns) for p in paths}

        targets = [CANONICAL_LEGACY, CANONICAL_QUALITY, CANONICAL_SPEC, SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, SYNTHETIC_SPEC]
        before = snapshot(targets)
        proc = run_report(SYNTHETIC_LEGACY, SYNTHETIC_QUALITY, SYNTHETIC_SPEC)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(snapshot(targets), before)


class SmallEntrypointTest(unittest.TestCase):
    def test_om_py_small_and_generic(self):
        text = OM_PATH.read_text(encoding="utf-8")
        self.assertLess(len(text.splitlines()), 400)
        for forbidden in ("22730", "25220", "47950", "54496", "433167", "4412"):
            self.assertNotIn(forbidden, text)

    def test_report_lib_derives_without_totals(self):
        text = OM_REPORT_PATH.read_text(encoding="utf-8")
        for forbidden in ("22730", "25220", "47950", "377353", "3428", "32749", "1609", "2803", "4412", "5700", "5600", "11300"):
            self.assertNotIn(forbidden, text)

    def test_canonical_spec_has_budgets_not_totals(self):
        text = CANONICAL_SPEC.read_text(encoding="utf-8")
        for forbidden in ("22730", "25220", "47950", "54496", "433167", "4412"):
            self.assertNotIn(forbidden, text)
        spec = load_json(CANONICAL_SPEC)
        self.assertEqual(spec["budgets"]["authored_requests_words_max"], 5700)
        self.assertEqual(spec["budgets"]["combined_words_max"], 11300)


if __name__ == "__main__":
    unittest.main()

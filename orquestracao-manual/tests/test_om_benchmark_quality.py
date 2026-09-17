"""Tests for the adjudicated quality benchmark (portable unit + optional history)."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
ORQ_DIR = TEST_DIR.parent
OM_PATH = ORQ_DIR / "scripts" / "om.py"
SYNTHETIC_FIXTURE = TEST_DIR / "fixtures" / "quality" / "synthetic-quality.json"
SYNTHETIC_EVIDENCE = TEST_DIR / "fixtures" / "quality" / "synthetic-evidence"
QUALITY_DIR = TEST_DIR / "fixtures" / "quality"
CANONICAL_FIXTURE = (
    ORQ_DIR / "manutencao" / "benchmarks" / "lua-translator-02-quality.json"
)
HISTORY_ENV = "OM_PHASE_A_HISTORY"


def run_quality(fixture, result, evidence_root, out=None):
    cmd = [
        sys.executable,
        "-B",
        str(OM_PATH),
        "benchmark",
        "quality",
        "--fixture",
        str(fixture),
        "--result",
        str(result),
    ]
    if evidence_root is not None:
        cmd += ["--evidence-root", str(evidence_root)]
    if out is not None:
        cmd += ["--out", str(out)]
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", timeout=60
    )


def run_synthetic(result_name, out=None):
    return run_quality(
        SYNTHETIC_FIXTURE, QUALITY_DIR / result_name, SYNTHETIC_EVIDENCE, out=out
    )


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


class SyntheticScoringTest(unittest.TestCase):
    def test_target_pass(self):
        proc = run_synthetic("synthetic-target-pass.json")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["verdict"], "pass")
        self.assertEqual(doc["recall"]["required"], ["O1", "O2"])
        self.assertEqual(doc["recall"]["covered"], ["O1", "O2"])
        self.assertEqual(doc["recall"]["missing"], [])
        self.assertEqual(doc["rejected_findings"], [])
        self.assertEqual(doc["unconfirmed_findings"], [])
        self.assertEqual(doc["unnecessary_expansions"], [])
        self.assertEqual(doc["missing_required_triggers"], [])

    def test_control_reason_not_unnecessary(self):
        proc = run_synthetic("synthetic-target-pass.json")
        doc = json.loads(proc.stdout)
        cases = [e["case_id"] for e in doc["unnecessary_expansions"]]
        self.assertNotIn("beta", cases)

    def test_escalate_all_with_full_recall_fails(self):
        proc = run_synthetic("synthetic-escalate-all.json")
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["recall"]["covered"], ["O1", "O2"])
        self.assertEqual(doc["recall"]["missing"], [])
        self.assertEqual(doc["verdict"], "fail")
        self.assertIn("G9", doc["rejected_findings"])
        self.assertTrue(len(doc["unnecessary_expansions"]) > 0)

    def test_clean_expanded_without_finding_fails(self):
        proc = run_synthetic("synthetic-clean-expanded.json")
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["verdict"], "fail")
        self.assertIn(
            {"case_id": "clean", "reason": "mechanical-a"},
            doc["unnecessary_expansions"],
        )

    def test_missing_item_fails(self):
        proc = run_synthetic("synthetic-missing-o2.json")
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["verdict"], "fail")
        self.assertEqual(doc["recall"]["missing"], ["O2"])

    def test_unconfirmed_needs_adjudication(self):
        proc = run_synthetic("synthetic-unconfirmed.json")
        self.assertEqual(proc.returncode, 2, msg=proc.stdout)
        self.assertNotIn("format error", proc.stderr.lower())
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["verdict"], "needs-adjudication")
        self.assertEqual(doc["unconfirmed_findings"], ["G4"])

    def test_missing_trigger_fails(self):
        proc = run_synthetic("synthetic-missing-trigger.json")
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["verdict"], "fail")
        self.assertIn(
            {"case_id": "beta", "reason": "mechanical-a"},
            doc["missing_required_triggers"],
        )


class SyntheticFormatErrorTest(unittest.TestCase):
    def assert_format_error(self, name):
        proc = run_synthetic(name)
        self.assertEqual(proc.returncode, 2, msg=proc.stdout)
        self.assertIn("format error", proc.stderr.lower(), msg=name)
        self.assertEqual(proc.stdout.strip(), "", msg=name)

    def test_duplicate_id(self):
        self.assert_format_error("synthetic-duplicate-id.json")

    def test_unknown_oracle(self):
        self.assert_format_error("synthetic-unknown-oracle.json")

    def test_unknown_case(self):
        self.assert_format_error("synthetic-unknown-case.json")

    def test_confirmed_empty(self):
        self.assert_format_error("synthetic-confirmed-empty.json")

    def test_unconfirmed_with_oracle(self):
        self.assert_format_error("synthetic-unconfirmed-with-oracle.json")

    def test_mismatched_oracle(self):
        self.assert_format_error("synthetic-mismatched-oracle.json")


class SyntheticCoverageTest(unittest.TestCase):
    def run_candidate_doc(self, doc):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.json"
            candidate.write_text(
                json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            return run_quality(SYNTHETIC_FIXTURE, candidate, SYNTHETIC_EVIDENCE)

    def test_missing_clean_is_format_error_never_pass(self):
        base = load_json(QUALITY_DIR / "synthetic-target-pass.json")
        base["cases"] = [c for c in base["cases"] if c["case_id"] != "clean"]
        proc = self.run_candidate_doc(base)
        self.assertEqual(proc.returncode, 2, msg=proc.stdout)
        self.assertIn("format error", proc.stderr.lower())
        self.assertIn("missing case", proc.stderr.lower())
        self.assertEqual(proc.stdout.strip(), "")

    def test_missing_alpha_is_format_error(self):
        base = load_json(QUALITY_DIR / "synthetic-target-pass.json")
        base["cases"] = [c for c in base["cases"] if c["case_id"] != "alpha"]
        proc = self.run_candidate_doc(base)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("format error", proc.stderr.lower())

    def test_duplicate_reason_is_format_error(self):
        base = load_json(QUALITY_DIR / "synthetic-target-pass.json")
        for entry in base["cases"]:
            if entry["case_id"] == "alpha":
                entry["expanded_review_reasons"] = ["mechanical-a", "mechanical-a"]
        proc = self.run_candidate_doc(base)
        self.assertEqual(proc.returncode, 2, msg=proc.stdout)
        self.assertIn("format error", proc.stderr.lower())
        self.assertIn("duplicate reason", proc.stderr.lower())
        self.assertEqual(proc.stdout.strip(), "")


class SyntheticProvenanceTest(unittest.TestCase):
    def test_roles_have_verifiable_evidence_clean_is_synthetic(self):
        doc = load_json(SYNTHETIC_FIXTURE)
        cases = {c["case_id"]: c for c in doc["cases"]}
        for case_id in ("alpha", "beta"):
            prov = cases[case_id]["provenance"]
            self.assertEqual(prov["origin"], "historical", msg=case_id)
            self.assertGreater(len(prov["evidence"]), 0, msg=case_id)
            for ev in prov["evidence"]:
                target = SYNTHETIC_EVIDENCE / ev["path"]
                self.assertTrue(target.is_file(), msg=str(target))
                self.assertEqual(
                    hashlib.sha256(target.read_bytes()).hexdigest(), ev["sha256"]
                )
        clean = cases["clean"]["provenance"]
        self.assertEqual(clean["origin"], "synthetic")
        self.assertEqual(clean["evidence"], [])


class EvidenceRequiredTest(unittest.TestCase):
    def test_missing_evidence_root_does_not_score(self):
        # --evidence-root is required=True in argparse, so absence is a parser
        # usage error (exit 2). Accept it as long as no scoring or write occurs.
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "out.json"
            cmd = [
                sys.executable,
                "-B",
                str(OM_PATH),
                "benchmark",
                "quality",
                "--fixture",
                str(SYNTHETIC_FIXTURE),
                "--result",
                str(QUALITY_DIR / "synthetic-target-pass.json"),
                "--out",
                str(out_file),
            ]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", timeout=60
            )
            self.assertEqual(proc.returncode, 2, msg=proc.stdout)
            self.assertIn("evidence-root", proc.stderr.lower())
            self.assertEqual(proc.stdout.strip(), "")
            self.assertFalse(out_file.exists())
        proc = run_quality(SYNTHETIC_FIXTURE, QUALITY_DIR / "synthetic-target-pass.json", None)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(proc.returncode, 2, msg=proc.stdout)
        self.assertIn("evidence-root", proc.stderr.lower())
        self.assertEqual(proc.stdout.strip(), "")


class OutBoundaryTest(unittest.TestCase):
    def test_out_inside_evidence_root_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Copy synthetic evidence to an isolated root so the test never
            # touches versioned inputs and can assert nothing was written.
            root = tmp_path / "evidence"
            root.mkdir()
            for child in SYNTHETIC_EVIDENCE.iterdir():
                (root / child.name).write_bytes(child.read_bytes())
            inside = root / "out.json"
            nested = root / "sub" / "out.json"
            dotdot = root / "sub" / ".." / "out.json"
            for candidate in (inside, nested, dotdot):
                proc = run_quality(SYNTHETIC_FIXTURE, QUALITY_DIR / "synthetic-target-pass.json", root, out=candidate)
                self.assertEqual(proc.returncode, 2, msg=str(candidate))
                self.assertIn("format error", proc.stderr.lower())
                self.assertIn("--out", proc.stderr)
                self.assertFalse(inside.exists(), msg=str(candidate))
                self.assertFalse(nested.exists(), msg=str(candidate))

    def test_out_equal_to_fixture_refused(self):
        proc = run_quality(
            SYNTHETIC_FIXTURE,
            QUALITY_DIR / "synthetic-target-pass.json",
            SYNTHETIC_EVIDENCE,
            out=SYNTHETIC_FIXTURE,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("format error", proc.stderr.lower())
        # Fixture must remain a valid fixture, not overwritten by scoring output.
        doc = load_json(SYNTHETIC_FIXTURE)
        self.assertEqual(doc["format"], "om-benchmark-quality/1")

    def test_out_equal_to_result_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            candidate = tmp_path / "candidate.json"
            candidate.write_bytes(
                (QUALITY_DIR / "synthetic-target-pass.json").read_bytes()
            )
            before = hashlib.sha256(candidate.read_bytes()).hexdigest()
            proc = run_quality(SYNTHETIC_FIXTURE, candidate, SYNTHETIC_EVIDENCE, out=candidate)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("format error", proc.stderr.lower())
            self.assertEqual(hashlib.sha256(candidate.read_bytes()).hexdigest(), before)

    def test_external_out_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "out.json"
            proc = run_quality(
                SYNTHETIC_FIXTURE,
                QUALITY_DIR / "synthetic-target-pass.json",
                SYNTHETIC_EVIDENCE,
                out=out_file,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertEqual(out_file.read_text(encoding="utf-8"), proc.stdout)


class DeterministicOutputTest(unittest.TestCase):
    def test_two_runs_match_and_out_matches_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "out.json"
            first = run_synthetic("synthetic-target-pass.json", out=out_file)
            self.assertEqual(first.returncode, 0, msg=first.stderr)
            second = run_synthetic("synthetic-target-pass.json")
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(out_file.read_text(encoding="utf-8"), first.stdout)
            parsed = json.loads(first.stdout)
            self.assertEqual(
                first.stdout,
                json.dumps(parsed, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
            )
            for key in (
                "recall",
                "rejected_findings",
                "unconfirmed_findings",
                "unnecessary_expansions",
                "missing_required_triggers",
                "verdict",
            ):
                self.assertIn(key, parsed)


class ReadOnlyInputsTest(unittest.TestCase):
    def test_synthetic_inputs_unchanged(self):
        def snapshot(root):
            data = {}
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    data[path.relative_to(root).as_posix()] = hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
            return data

        before_dir = snapshot(QUALITY_DIR)
        before_fixture = hashlib.sha256(
            SYNTHETIC_FIXTURE.read_bytes()
        ).hexdigest()
        proc = run_synthetic("synthetic-target-pass.json")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(snapshot(QUALITY_DIR), before_dir)
        self.assertEqual(
            hashlib.sha256(SYNTHETIC_FIXTURE.read_bytes()).hexdigest(), before_fixture
        )


class CanonicalHistoryIntegrationTest(unittest.TestCase):
    def history_root(self):
        raw = os.environ.get(HISTORY_ENV)
        if not raw:
            self.skipTest("integration requires %s" % HISTORY_ENV)
        root = Path(raw)
        self.assertTrue(root.is_dir(), msg=str(root))
        return root

    def run_canonical(self, name, root, out=None):
        return run_quality(CANONICAL_FIXTURE, QUALITY_DIR / name, root, out=out)

    def test_canonical_fixture_against_history(self):
        root = self.history_root()
        doc = load_json(CANONICAL_FIXTURE)
        self.assertEqual(doc["format"], "om-benchmark-quality/1")
        oracles = {o["id"]: o for o in doc["oracles"]}
        self.assertEqual(sorted(oracles.keys()), ["D1", "D2", "D3"])
        boundary = doc["information_boundary"]
        self.assertIn("80a0001", boundary["oracle_only"])
        self.assertNotIn("80a0001", boundary["executor_inputs"])
        for entry in oracles.values():
            for ev in entry["evidence"]:
                target = root / ev["path"]
                self.assertTrue(target.is_file(), msg=str(target))
                self.assertEqual(
                    hashlib.sha256(target.read_bytes()).hexdigest(), ev["sha256"]
                )
        cases = {c["case_id"]: c for c in doc["cases"]}
        expected_paths = {
            "control-10-a": "retorno-10-a.md",
            "control-11-a": "retorno-11-a.md",
            "control-14-a": "retorno-14-a.md",
            "replay-13-a": "retorno-13-a.md",
        }
        for case_id in ("control-10-a", "control-11-a", "control-14-a", "replay-13-a"):
            prov = cases[case_id]["provenance"]
            self.assertEqual(prov["origin"], "historical", msg=case_id)
            self.assertGreater(len(prov["evidence"]), 0, msg=case_id)
            paths = sorted(ev["path"] for ev in prov["evidence"])
            self.assertIn(expected_paths[case_id], paths, msg=case_id)
            for ev in prov["evidence"]:
                target = root / ev["path"]
                self.assertTrue(target.is_file(), msg=str(target))
                self.assertEqual(
                    hashlib.sha256(target.read_bytes()).hexdigest(), ev["sha256"]
                )
                n_lines = len(target.read_text(encoding="utf-8-sig").splitlines())
                for anchor in ev["anchors"]:
                    start_s, _, end_s = anchor.partition("-")
                    self.assertLessEqual(int(end_s or start_s), n_lines, msg=anchor)
        clean = cases["control-read-only-clean"]["provenance"]
        self.assertEqual(clean["origin"], "synthetic")
        self.assertEqual(clean["evidence"], [])

    def test_canonical_target_pass(self):
        root = self.history_root()
        proc = self.run_canonical("target-pass.json", root)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["verdict"], "pass")
        self.assertEqual(doc["recall"]["covered"], ["D1", "D2", "D3"])

    def test_canonical_escalate_all_fails(self):
        root = self.history_root()
        proc = self.run_canonical("escalate-all.json", root)
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["recall"]["covered"], ["D1", "D2", "D3"])
        self.assertNotEqual(doc["verdict"], "pass")

    def test_canonical_missing_and_unconfirmed(self):
        root = self.history_root()
        missing = self.run_canonical("missing-d3.json", root)
        self.assertEqual(missing.returncode, 1)
        self.assertEqual(json.loads(missing.stdout)["recall"]["missing"], ["D3"])
        pending = self.run_canonical("unconfirmed.json", root)
        self.assertEqual(pending.returncode, 2)
        self.assertEqual(json.loads(pending.stdout)["verdict"], "needs-adjudication")

    def test_canonical_format_errors(self):
        root = self.history_root()
        for name in ("duplicate-id.json", "unknown-oracle.json", "unknown-case.json"):
            proc = self.run_canonical(name, root)
            self.assertEqual(proc.returncode, 2, msg=name)
            self.assertIn("format error", proc.stderr.lower(), msg=name)

    def test_canonical_missing_clean_is_format_error(self):
        root = self.history_root()
        base = load_json(QUALITY_DIR / "target-pass.json")
        base["cases"] = [
            c for c in base["cases"] if c["case_id"] != "control-read-only-clean"
        ]
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.json"
            candidate.write_text(
                json.dumps(base, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            proc = run_quality(CANONICAL_FIXTURE, candidate, root)
            self.assertEqual(proc.returncode, 2, msg=proc.stdout)
            self.assertIn("format error", proc.stderr.lower())
            self.assertIn("missing case", proc.stderr.lower())
            self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()

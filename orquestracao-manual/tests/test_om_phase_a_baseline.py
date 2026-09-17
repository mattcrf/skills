"""Tests for the complementary Phase A factual baseline fixture.

Facts are re-derived from Git and from ``OM_PHASE_A_HISTORY``, never from the
fixture alone.
"""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
ORQ_DIR = TEST_DIR.parent
REPO_DIR = ORQ_DIR.parent
OM_PATH = ORQ_DIR / "scripts" / "om.py"
BENCH_DIR = ORQ_DIR / "manutencao" / "benchmarks"
FIXTURE_PATH = BENCH_DIR / "lua-translator-02-phase-a.json"
LEGACY_PATH = BENCH_DIR / "lua-translator-02.json"
ARTIFACTS_PATH = BENCH_DIR / "lua-translator-02-artifacts.json"
REPORT_SPEC_PATH = BENCH_DIR / "lua-translator-02-report-spec.json"
HISTORY_ENV = "OM_PHASE_A_HISTORY"
WORD_RE = re.compile(r"\S+")
TASK_ID_RE = re.compile(r"[0-9]+[a-z]?(?:-[a-z])?")
HEX64_RE = re.compile(r"[0-9a-f]{64}")
TOP_KEYS = ("format", "algorithm", "context", "bridge", "proliferation",
            "capsules", "references", "unrecoverable")
ALGO_KEYS = ("words", "bytes", "lines")
CONTEXT_KEYS = ("origin", "paths", "revisions", "operational_words", "method")
BRIDGE_KEYS = ("origin", "dispatches", "executions", "transports", "tasks_total",
               "task_lines_dispatched", "direct_or_earlier", "dispatches_one_task",
               "dispatches_two_tasks", "method")
BRIDGE_COUNTS = ("dispatches", "executions", "transports", "tasks_total",
                 "task_lines_dispatched", "direct_or_earlier", "dispatches_one_task",
                 "dispatches_two_tasks")
PROLIF_KEYS = ("origin", "root_json_files", "root_json_bytes", "neolua_dirs",
               "baseline_dirs", "markdown_files", "census", "method")
PROLIF_COUNTS = ("root_json_files", "root_json_bytes", "neolua_dirs",
                 "baseline_dirs", "markdown_files")
CAPSULE_KEYS = ("origin", "glob", "files", "max_lines", "method")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_om():
    spec = importlib.util.spec_from_file_location("om_phase_a_under_test", OM_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def word_count(text):
    return len(WORD_RE.findall(text))


def git_run(*args):
    return subprocess.run(
        ["git", "-C", str(REPO_DIR)] + list(args), capture_output=True, timeout=60
    )


def require_history():
    raw = os.environ.get(HISTORY_ENV)
    if not raw:
        raise unittest.SkipTest("integration requires %s" % HISTORY_ENV)
    root = Path(raw)
    if not root.is_dir():
        raise AssertionError("history root is not a directory: %s" % root)
    return root


def despacho_task_rows(path):
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 5 or not TASK_ID_RE.fullmatch(cells[0]):
            continue
        rows.append(cells)
    return rows


def keys_of(obj, expected, label):
    if not isinstance(obj, dict) or set(obj) != set(expected):
        raise AssertionError("%s keys differ from the strict schema" % label)


def positive_int(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AssertionError("%s must be a positive integer" % label)


def nonempty_str(value, label):
    if not isinstance(value, str) or not value:
        raise AssertionError("%s must be a non-empty string" % label)


def block(doc, name, expected, origin):
    obj = doc[name]
    keys_of(obj, expected, name)
    nonempty_str(obj["origin"], "%s.origin" % name)
    if obj["origin"] != origin:
        raise AssertionError("%s.origin must be %s" % (name, origin))
    return obj


def check_fixture(doc):
    if not isinstance(doc, dict) or set(doc) != set(TOP_KEYS):
        raise AssertionError("fixture keys differ from the strict schema")
    if doc["format"] != "om-phase-a-baseline/1":
        raise AssertionError("unexpected fixture format: %r" % doc["format"])

    algo = doc["algorithm"]
    keys_of(algo, ALGO_KEYS, "algorithm")
    if "\\S+" not in algo["words"]:
        raise AssertionError("algorithm.words must name the \\S+ expression")
    for value in algo.values():
        nonempty_str(value, "algorithm value")

    context = block(doc, "context", CONTEXT_KEYS, "git")
    if not isinstance(context["paths"], list) or not context["paths"]:
        raise AssertionError("context.paths must list the measured paths")
    for rel in context["paths"]:
        if not isinstance(rel, str) or rel == "" or rel.startswith("/") or ":" in rel:
            raise AssertionError("context.paths entries must be relative paths")
    positive_int(context["operational_words"], "context.operational_words")
    if not isinstance(context["revisions"], list) or not context["revisions"]:
        raise AssertionError("context.revisions must not be empty")
    for rev in context["revisions"]:
        keys_of(rev, ("commit", "words"), "context revision")
        nonempty_str(rev["commit"], "context revision commit")
        positive_int(rev["words"], "context revision words")

    bridge = block(doc, "bridge", BRIDGE_KEYS, "history")
    for key in BRIDGE_COUNTS:
        positive_int(bridge[key], "bridge.%s" % key)
    if bridge["dispatches_one_task"] + bridge["dispatches_two_tasks"] != bridge["dispatches"]:
        raise AssertionError("bridge task-per-dispatch counts must add up")
    if bridge["direct_or_earlier"] != bridge["tasks_total"] - bridge["task_lines_dispatched"]:
        raise AssertionError("bridge direct_or_earlier must be the unlisted remainder")
    if bridge["transports"] != bridge["dispatches"] + bridge["executions"]:
        raise AssertionError("bridge.transports must be dispatches plus executions")

    prolif = block(doc, "proliferation", PROLIF_KEYS, "history")
    for key in PROLIF_COUNTS:
        positive_int(prolif[key], "proliferation.%s" % key)
    census = prolif["census"]
    keys_of(census, ("fixture", "files", "bytes"), "proliferation.census")
    if census["fixture"] != Path(ARTIFACTS_PATH).name:
        raise AssertionError("census must reference the sealed artifacts fixture")
    positive_int(census["files"], "census.files")
    positive_int(census["bytes"], "census.bytes")

    capsules = block(doc, "capsules", CAPSULE_KEYS, "history")
    for key in ("glob", "method"):
        nonempty_str(capsules[key], "capsules.%s" % key)
    for key in ("files", "max_lines"):
        positive_int(capsules[key], "capsules.%s" % key)

    references = doc["references"]
    if not isinstance(references, list) or not references:
        raise AssertionError("references must be a non-empty list")
    ids = set()
    for ref in references:
        keys_of(ref, ("id", "path", "format", "sha256"), "reference")
        if not isinstance(ref["id"], str) or ref["id"] in ids:
            raise AssertionError("reference ids must be unique strings")
        ids.add(ref["id"])
        if ref["path"].startswith("/") or ":" in ref["path"] or ".." in ref["path"]:
            raise AssertionError("reference paths must be relative")
        if not HEX64_RE.fullmatch(ref["sha256"]):
            raise AssertionError("reference sha256 must be 64 lowercase hex chars")

    items = doc["unrecoverable"]
    if not isinstance(items, list) or not items:
        raise AssertionError("unrecoverable must be a non-empty list")
    seen = set()
    for item in items:
        keys_of(item, ("id", "reason"), "unrecoverable item")
        if not isinstance(item["id"], str) or item["id"] in seen:
            raise AssertionError("unrecoverable ids must be unique strings")
        seen.add(item["id"])
        nonempty_str(item["reason"], "unrecoverable reason")
    return doc


class FixtureSchemaTest(unittest.TestCase):
    def test_strict_schema_and_wording(self):
        check_fixture(load_json(FIXTURE_PATH))
        text = FIXTURE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("token", text.lower())
        self.assertNotIn("C:\\", text)
        self.assertNotIn("C:/", text)
        self.assertNotIn("mattc", text.lower())
        self.assertNotIn("manifest", text)
        self.assertLess(len(text.encode("utf-8")), 16 * 1024)

    def test_references_are_sealed_by_hash_and_format(self):
        doc = check_fixture(load_json(FIXTURE_PATH))
        for ref in doc["references"]:
            target = ORQ_DIR / ref["path"]
            self.assertTrue(target.is_file(), msg=ref["path"])
            self.assertEqual(ref["sha256"], file_sha(target), msg=ref["id"])
            self.assertEqual(ref["format"], load_json(target)["format"], msg=ref["id"])


class CrossReferenceTest(unittest.TestCase):
    def test_bridge_counters_match_the_legacy_fixture(self):
        doc = check_fixture(load_json(FIXTURE_PATH))
        by_category = {}
        for record in load_json(LEGACY_PATH)["files"]:
            by_category.setdefault(record["category"], []).append(record)
        self.assertEqual(len(by_category["captain_authored_operational"]),
                         doc["bridge"]["dispatches"])
        self.assertEqual(len(by_category["captain_received_operational"]),
                         doc["bridge"]["executions"])
        self.assertEqual(len(by_category["captain_authored_technical"]),
                         doc["bridge"]["tasks_total"])

    def test_capsules_match_the_legacy_file_records(self):
        doc = check_fixture(load_json(FIXTURE_PATH))
        records = [r for r in load_json(LEGACY_PATH)["files"]
                   if r["path"].startswith("continuacao-")]
        self.assertEqual(len(records), doc["capsules"]["files"])
        self.assertEqual(max(r["lines"] for r in records), doc["capsules"]["max_lines"])

    def test_census_matches_the_sealed_artifacts_fixture(self):
        doc = check_fixture(load_json(FIXTURE_PATH))
        census = doc["proliferation"]["census"]
        totals = load_json(ARTIFACTS_PATH)["totals"]
        self.assertEqual(census["files"], totals["files"])
        self.assertEqual(census["bytes"], totals["bytes"])

    def test_report_spec_unrecoverable_items_remain_covered(self):
        doc = check_fixture(load_json(FIXTURE_PATH))
        frozen = {item["id"] for item in doc["unrecoverable"]}
        inherited = {i["id"] for i in load_json(REPORT_SPEC_PATH)["unrecoverable"]}
        self.assertTrue(inherited.issubset(frozen), msg=sorted(inherited - frozen))


class ContextTest(unittest.TestCase):
    def test_current_operational_paths_still_measure_the_frozen_words(self):
        doc = check_fixture(load_json(FIXTURE_PATH))
        measured = sum(word_count((REPO_DIR / rel).read_text(encoding="utf-8-sig"))
                       for rel in doc["context"]["paths"])
        self.assertEqual(measured, doc["context"]["operational_words"],
                         msg="working tree context words drifted from the frozen baseline")

    def test_historical_revisions_derive_the_frozen_words(self):
        doc = check_fixture(load_json(FIXTURE_PATH))
        try:
            probe = git_run("rev-parse", "--show-toplevel")
        except OSError as exc:
            self.skipTest("git CLI unavailable: %s" % exc)
        if probe.returncode != 0:
            self.skipTest("not a git repository checkout: %s" % REPO_DIR)
        missing = []
        for rev in doc["context"]["revisions"]:
            commit = rev["commit"]
            if git_run("rev-parse", "--verify", "%s^{commit}" % commit).returncode != 0:
                missing.append(commit)
                continue
            measured = 0
            for rel in doc["context"]["paths"]:
                shown = git_run("show", "%s:%s" % (commit, rel))
                if shown.returncode != 0:
                    self.fail("canonical revision %s exists but lacks %s: %s"
                              % (commit, rel,
                                 shown.stderr.decode("utf-8", "replace").strip()))
                measured += word_count(shown.stdout.decode("utf-8-sig"))
            self.assertEqual(measured, rev["words"],
                             msg="revision %s measures %s words, fixture froze %s"
                             % (commit, measured, rev["words"]))
        if missing:
            self.skipTest("canonical revisions not present here: %s" % ", ".join(missing))


class BridgeTopologyTest(unittest.TestCase):
    def test_task_lines_derived_from_the_dispatch_tables(self):
        doc = check_fixture(load_json(FIXTURE_PATH))
        root = require_history()
        despachos = sorted(root.glob("despacho-*.md"))
        execucoes = sorted(root.glob("execucao-*.md"))
        pedidos = sorted(root.glob("pedido-*.md"))
        per_file = [despacho_task_rows(path) for path in despachos]
        self.assertTrue(all(rows for rows in per_file), msg="a despacho has no task table")
        rows = sum(len(entry) for entry in per_file)
        one_task = sum(1 for entry in per_file if len(entry) == 1)
        two_tasks = sum(1 for entry in per_file if len(entry) == 2)
        bridge = doc["bridge"]
        self.assertEqual(len(despachos), bridge["dispatches"])
        self.assertEqual(len(execucoes), bridge["executions"])
        self.assertEqual(len(pedidos), bridge["tasks_total"])
        self.assertEqual(bridge["transports"], len(despachos) + len(execucoes))
        self.assertEqual(rows, bridge["task_lines_dispatched"])
        self.assertEqual(one_task, bridge["dispatches_one_task"])
        self.assertEqual(two_tasks, bridge["dispatches_two_tasks"])
        self.assertEqual(one_task + two_tasks, len(despachos))
        self.assertEqual(bridge["direct_or_earlier"], len(pedidos) - rows)


class ProliferationTest(unittest.TestCase):
    def test_walk_derives_the_frozen_proliferation_and_census(self):
        doc = check_fixture(load_json(FIXTURE_PATH))
        root = require_history()
        files = [p for p in root.rglob("*") if p.is_file()]
        root_jsons = [p for p in root.iterdir() if p.is_file() and p.suffix == ".json"]
        first_dirs = [p for p in root.iterdir() if p.is_dir()]
        markdown = [p for p in files if p.suffix.lower() == ".md"]
        prolif = doc["proliferation"]
        self.assertEqual(len(root_jsons), prolif["root_json_files"])
        self.assertEqual(sum(p.stat().st_size for p in root_jsons), prolif["root_json_bytes"])
        self.assertEqual(len([p for p in first_dirs if p.name.startswith("neolua-")]),
                         prolif["neolua_dirs"])
        self.assertEqual(len([p for p in first_dirs if p.name.startswith("baseline-")]),
                         prolif["baseline_dirs"])
        self.assertEqual(len(markdown), prolif["markdown_files"])
        self.assertEqual(len(files), prolif["census"]["files"])
        self.assertEqual(sum(p.stat().st_size for p in files), prolif["census"]["bytes"])


class CapsulesTest(unittest.TestCase):
    def test_line_convention_matches_the_legacy_benchmark(self):
        om = load_om()
        self.assertEqual(om._count_lines(""), 0)
        self.assertEqual(om._count_lines("a\n"), 2)

    def test_capsules_derived_from_the_history_root(self):
        doc = check_fixture(load_json(FIXTURE_PATH))
        root = require_history()
        om = load_om()
        capsules = sorted(root.glob(doc["capsules"]["glob"]))
        counts = [om._count_lines(p.read_text(encoding="utf-8-sig")) for p in capsules]
        self.assertEqual(len(capsules), doc["capsules"]["files"])
        self.assertEqual(max(counts), doc["capsules"]["max_lines"])


if __name__ == "__main__":
    unittest.main()

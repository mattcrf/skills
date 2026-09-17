import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
ORQ_DIR = TEST_DIR.parent
OM_PATH = ORQ_DIR / "scripts" / "om.py"


class ControlPlaneTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.operation = self.root / "operation"
        self.operation.mkdir()
        project = (self.root / "project").resolve()
        project.mkdir()
        operation_toml = """\
format = "om-operation/1"
id = "demo-operation"
project_root = "{project}"
current_context = 1

[profiles.reader]
effects = ["read-only"]

[profiles.writer]
effects = ["mutating"]
""".format(project=project.as_posix())
        (self.operation / "operation.toml").write_text(operation_toml, encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def task(self, task_id="demo-001", effect="read-only", profile="reader", depends=None):
        depends = [] if depends is None else depends
        path = self.root / (task_id + ".md")
        path.write_text(
            """\
+++
id = "{task_id}"
kind = "writer"
effect = "{effect}"
profile = "{profile}"
context = 1
depends = {depends}
+++

# Objective

Demonstrate one small task.

# Acceptance

- The result is observable.
""".format(task_id=task_id, effect=effect, profile=profile, depends=json.dumps(depends)),
            encoding="utf-8",
        )
        return path

    def run_om(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(OM_PATH), *args],
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=20,
        )

    def publish(self, task):
        return self.run_om(
            "task",
            "publish",
            "--operation",
            str(self.operation),
            "--task",
            str(task),
        )

    def test_happy_path_publish_status_doctor_resume(self):
        published = self.publish(self.task())
        self.assertEqual(published.returncode, 0, published.stderr)
        self.assertIn("published demo-001 state=ready event=1", published.stdout)

        status = self.run_om("status", "--operation", str(self.operation))
        self.assertEqual(status.returncode, 0, status.stderr)
        document = json.loads(status.stdout)
        self.assertEqual(document["format"], "om-status/1")
        self.assertEqual(document["tasks"][0]["state"], "ready")

        doctor = self.run_om("doctor", "--operation", str(self.operation))
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertIn("tasks=1 events=1", doctor.stdout)

        resume = self.run_om(
            "resume", "--operation", str(self.operation), "--role", "captain"
        )
        self.assertEqual(resume.returncode, 0, resume.stderr)
        self.assertIn("# Resume - captain", resume.stdout)
        self.assertIn("Dispatch `demo-001`", resume.stdout)

    def test_duplicate_publish_is_rejected_without_new_event(self):
        task = self.task()
        self.assertEqual(self.publish(task).returncode, 0)
        rejected = self.publish(task)
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("task already published", rejected.stderr)
        events = (self.operation / "events.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(events), 1)

    def test_doctor_rejects_changed_published_task(self):
        self.assertEqual(self.publish(self.task()).returncode, 0)
        published = self.operation / "tasks" / "demo-001.md"
        published.write_text(published.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
        doctor = self.run_om("doctor", "--operation", str(self.operation))
        self.assertEqual(doctor.returncode, 1)
        self.assertIn("published task changed", doctor.stderr)

    def test_profile_cannot_grant_a_different_effect(self):
        rejected = self.publish(self.task(effect="mutating", profile="reader"))
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("effect is not granted", rejected.stderr)
        self.assertFalse((self.operation / "events.jsonl").exists())

    def test_mutating_task_uses_writer_profile(self):
        published = self.publish(self.task(effect="mutating", profile="writer"))
        self.assertEqual(published.returncode, 0, published.stderr)
        status = self.run_om("status", "--operation", str(self.operation))
        task = json.loads(status.stdout)["tasks"][0]
        self.assertEqual((task["effect"], task["profile"]), ("mutating", "writer"))

    def test_missing_dependency_is_rejected(self):
        rejected = self.publish(self.task(depends=["missing-task"]))
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("missing dependencies", rejected.stderr)

    def test_doctor_rejects_event_chain_tampering(self):
        self.assertEqual(self.publish(self.task()).returncode, 0)
        event_path = self.operation / "events.jsonl"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["profile"] = "writer"
        event_path.write_text(json.dumps(event) + "\n", encoding="utf-8")
        doctor = self.run_om("doctor", "--operation", str(self.operation))
        self.assertEqual(doctor.returncode, 1)
        self.assertIn("invalid event hash", doctor.stderr)

    def test_concurrent_publish_of_two_tasks_keeps_both_events(self):
        rounds = 8
        base_command = [
            sys.executable,
            "-B",
            str(OM_PATH),
            "task",
            "publish",
            "--operation",
            str(self.operation),
            "--task",
        ]
        for round_number in range(1, rounds + 1):
            task_ids = ["demo-a%02d" % round_number, "demo-b%02d" % round_number]
            drafts = [self.task(task_id) for task_id in task_ids]
            processes = [
                subprocess.Popen(
                    base_command + [str(draft)],
                    text=True,
                    encoding="utf-8",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                for draft in drafts
            ]
            outputs = [process.communicate(timeout=60) for process in processes]
            for task_id, process, (out, err) in zip(task_ids, processes, outputs):
                self.assertEqual(process.returncode, 0, err)
                self.assertIn("published %s state=ready" % task_id, out)
            events = (self.operation / "events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(events), 2 * round_number)
            for task_id in task_ids:
                self.assertTrue((self.operation / "tasks" / (task_id + ".md")).is_file())
            doctor = self.run_om("doctor", "--operation", str(self.operation))
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            self.assertIn(
                "tasks=%d events=%d" % (2 * round_number, 2 * round_number),
                doctor.stdout,
            )

    def test_non_string_kind_and_effect_are_rejected_cleanly(self):
        cases = (
            ('kind = "writer"', 'kind = ["writer"]', "om: invalid task kind"),
            ('effect = "read-only"', 'effect = ["read-only"]', "om: invalid task effect"),
        )
        for original, replacement, message in cases:
            with self.subTest(replacement=replacement):
                task = self.task()
                text = task.read_text(encoding="utf-8")
                self.assertIn(original, text)
                task.write_text(text.replace(original, replacement), encoding="utf-8")
                rejected = self.publish(task)
                self.assertEqual(rejected.returncode, 1)
                self.assertIn(message, rejected.stderr)
                self.assertNotIn("Traceback", rejected.stderr)
                self.assertFalse((self.operation / "events.jsonl").exists())

    def test_non_ascii_paths_reach_both_output_streams(self):
        operation = self.root / "opera\u00e7\u00e3o-\u65e5\u672c"
        operation.mkdir()
        project = (self.root / "projeto-\u65e5\u672c").resolve()
        project.mkdir()
        (operation / "operation.toml").write_text(
            'format = "om-operation/1"\n'
            'id = "unicode-operation"\n'
            'project_root = "%s"\n'
            "current_context = 1\n"
            "\n[profiles.reader]\neffects = [\"read-only\"]\n"
            "\n[profiles.writer]\neffects = [\"mutating\"]\n" % project.as_posix(),
            encoding="utf-8",
        )
        published = self.run_om(
            "task",
            "publish",
            "--operation",
            str(operation),
            "--task",
            str(self.task()),
        )
        self.assertEqual(published.returncode, 0, published.stderr)
        doctor = self.run_om("doctor", "--operation", str(operation))
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        resume = self.run_om("resume", "--operation", str(operation), "--role", "captain")
        self.assertEqual(resume.returncode, 0, resume.stderr)
        self.assertIn(str(project), resume.stdout)
        missing = operation / "ausente"
        failed = self.run_om("doctor", "--operation", str(missing))
        self.assertEqual(failed.returncode, 1)
        self.assertNotIn("Traceback", failed.stderr)
        self.assertIn(str(missing), failed.stderr)

    def test_atomic_write_parent_failure_uses_error_contract(self):
        (self.operation / "tasks").write_text("blocking file", encoding="utf-8")
        rejected = self.publish(self.task())
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("om: cannot write:", rejected.stderr)
        self.assertNotIn("Traceback", rejected.stderr)


if __name__ == "__main__":
    unittest.main()

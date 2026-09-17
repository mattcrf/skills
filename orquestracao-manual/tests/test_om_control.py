import json
import re
import subprocess
import sys
import tempfile
import time
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

    def publish_chain(self, length):
        for index in range(length):
            task_id = "demo-%02d" % index
            depends = [] if index == 0 else ["demo-%02d" % (index - 1)]
            published = self.publish(self.task(task_id, depends=depends))
            self.assertEqual(published.returncode, 0, published.stderr)

    def test_init_new_publish_and_dispatch_are_a_complete_preparation_path(self):
        operation = self.root / "fresh-operation"
        project = self.root / "fresh-project"
        project.mkdir()
        initialized = self.run_om(
            "op",
            "init",
            "--operation",
            str(operation),
            "--project-root",
            str(project),
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.assertTrue((operation / "operation.toml").is_file())
        self.assertEqual(
            (operation / ".gitignore").read_text(encoding="utf-8"),
            "/.cache/\n/.scratch/\n",
        )

        writer = self.run_om(
            "task",
            "new",
            "--operation",
            str(operation),
            "--id",
            "write-one",
            "--kind",
            "writer",
            "--title",
            "Implement one change",
        )
        self.assertEqual(writer.returncode, 0, writer.stderr)
        writer_path = Path(writer.stdout.removeprefix("draft ").strip())
        self.assertTrue(writer_path.is_file())
        rejected = self.run_om(
            "task", "publish", "--operation", str(operation), "--task", str(writer_path)
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("task still contains TODO markers", rejected.stderr)
        writer_path.write_text(
            writer_path.read_text(encoding="utf-8").replace(
                "TODO:", "Defined:",
            ),
            encoding="utf-8",
        )
        published_writer = self.run_om(
            "task", "publish", "--operation", str(operation), "--task", str(writer_path)
        )
        self.assertEqual(published_writer.returncode, 0, published_writer.stderr)

        verifier = self.run_om(
            "task",
            "new",
            "--operation",
            str(operation),
            "--id",
            "verify-one",
            "--kind",
            "verifier",
            "--depends",
            "write-one",
        )
        self.assertEqual(verifier.returncode, 0, verifier.stderr)
        verifier_path = Path(verifier.stdout.removeprefix("draft ").strip())
        verifier_path.write_text(
            verifier_path.read_text(encoding="utf-8").replace(
                "TODO:", "Defined:",
            ),
            encoding="utf-8",
        )
        published_verifier = self.run_om(
            "task", "publish", "--operation", str(operation), "--task", str(verifier_path)
        )
        self.assertEqual(published_verifier.returncode, 0, published_verifier.stderr)

        dispatched = self.run_om(
            "bridge", "dispatch", "--operation", str(operation), "--slots", "2"
        )
        self.assertEqual(dispatched.returncode, 0, dispatched.stderr)
        dispatch = (operation / "dispatch.md").read_text(encoding="utf-8")
        self.assertIn("| write-one |", dispatch)
        self.assertIn("| verify-one |", dispatch)
        self.assertIn("write-one", dispatch)
        self.assertIn("SKILL.md", dispatch)
        self.assertIn("references\\gerente.md", dispatch)
        self.assertIn("references\\trabalhador.md", dispatch)
        self.assertNotIn("Não há scout", dispatch)
        self.assertNotIn("não tente", dispatch.lower())
        self.assertIn('manager: Leia "', dispatched.stdout)

        doctor = self.run_om("doctor", "--operation", str(operation))
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertIn("tasks=2 events=2", doctor.stdout)

    def test_task_size_is_measured_but_never_blocks_publication(self):
        task = self.task()
        task.write_text(
            task.read_text(encoding="utf-8") + ("evidence " * 800),
            encoding="utf-8",
        )

        published = self.publish(task)

        self.assertEqual(published.returncode, 0, published.stderr)
        self.assertIn("budget=over", published.stdout)
        self.assertTrue((self.operation / "tasks" / "demo-001.md").is_file())

    def test_dispatch_is_immutable_and_slots_are_bounded(self):
        self.assertEqual(self.publish(self.task()).returncode, 0)
        first = self.run_om("bridge", "dispatch", "--operation", str(self.operation))
        self.assertEqual(first.returncode, 0, first.stderr)
        repeated = self.run_om("bridge", "dispatch", "--operation", str(self.operation))
        self.assertEqual(repeated.returncode, 1)
        self.assertIn("dispatch already exists", repeated.stderr)
        excessive = self.run_om(
            "bridge",
            "dispatch",
            "--operation",
            str(self.operation),
            "--slots",
            "4",
            "--out",
            str(self.operation / "dispatch-02.md"),
        )
        self.assertEqual(excessive.returncode, 1)
        self.assertIn("slots must be between 1 and 3", excessive.stderr)

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

    def test_publish_stores_the_lock_under_cache(self):
        self.assertEqual(self.publish(self.task()).returncode, 0)
        self.assertTrue((self.operation / ".cache" / "control.lock").is_file())
        self.assertFalse((self.operation / "control.lock").exists())

    def test_status_doctor_resume_wait_for_the_lock(self):
        self.assertEqual(self.publish(self.task()).returncode, 0)
        holder_code = (
            "import os, sys\n"
            "from pathlib import Path\n"
            "path = Path({root!r}) / '.cache' / 'control.lock'\n"
            "path.parent.mkdir(parents=True, exist_ok=True)\n"
            "handle = path.open('a+b')\n"
            "handle.seek(0, os.SEEK_END)\n"
            "if handle.tell() == 0:\n"
            "    handle.write(b'\\0')\n"
            "    handle.flush()\n"
            "handle.seek(0)\n"
            "if os.name == 'nt':\n"
            "    import msvcrt\n"
            "    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)\n"
            "else:\n"
            "    import fcntl\n"
            "    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)\n"
            "sys.stdout.write('locked\\n')\n"
            "sys.stdout.flush()\n"
            "sys.stdin.readline()\n"
        ).format(root=str(self.operation))
        holder = subprocess.Popen(
            [sys.executable, "-B", "-c", holder_code],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(holder.stdout.readline().strip(), "locked")
        readers = [
            subprocess.Popen(
                [sys.executable, "-B", str(OM_PATH), command, "--operation", str(self.operation)]
                + extra,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            for command, extra in (
                ("status", []),
                ("doctor", []),
                ("resume", ["--role", "captain"]),
            )
        ]
        try:
            time.sleep(1.5)
            self.assertTrue(
                all(process.poll() is None for process in readers),
                "a reader did not wait for the active lock",
            )
            holder.stdin.write("release\n")
            holder.stdin.flush()
            outputs = [process.communicate(timeout=60) for process in readers]
        finally:
            for process in readers:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=20)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
            if holder.poll() is None:
                holder.kill()
            holder.wait(timeout=20)
            if holder.stdin is not None:
                holder.stdin.close()
            if holder.stdout is not None:
                holder.stdout.close()
        for process, (out, err) in zip(readers, outputs):
            self.assertEqual(process.returncode, 0, err)
        self.assertIn('"state": "ready"', outputs[0][0])
        self.assertIn("tasks=1 events=1", outputs[1][0])
        self.assertIn("Dispatch `demo-001`", outputs[2][0])

    def test_reader_and_publishers_share_the_lock_without_deadlock(self):
        drafts = [self.task("demo-p1"), self.task("demo-p2")]
        commands = [
            [
                sys.executable,
                "-B",
                str(OM_PATH),
                "task",
                "publish",
                "--operation",
                str(self.operation),
                "--task",
                str(draft),
            ]
            for draft in drafts
        ]
        commands += [
            [sys.executable, "-B", str(OM_PATH), command, "--operation", str(self.operation)]
            for command in ("status", "doctor")
        ]
        processes = [
            subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            for command in commands
        ]
        try:
            outputs = [process.communicate(timeout=60) for process in processes]
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=20)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
        for process, (out, err) in zip(processes, outputs):
            self.assertEqual(process.returncode, 0, err)
        events = (self.operation / "events.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(events), 2)
        doctor = self.run_om("doctor", "--operation", str(self.operation))
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertIn("tasks=2 events=2", doctor.stdout)

    def test_cache_failure_uses_the_error_contract(self):
        (self.operation / ".cache").write_text("blocking file", encoding="utf-8")
        draft = self.task()
        commands = (
            ("status", "--operation", str(self.operation)),
            ("doctor", "--operation", str(self.operation)),
            ("resume", "--operation", str(self.operation), "--role", "captain"),
            ("task", "publish", "--operation", str(self.operation), "--task", str(draft)),
        )
        for command in commands:
            with self.subTest(command=command):
                failed = self.run_om(*command)
                self.assertEqual(failed.returncode, 1)
                self.assertIn("om: cannot open lock file:", failed.stderr)
                self.assertNotIn("Traceback", failed.stderr)
        self.assertFalse((self.operation / "events.jsonl").exists())

    def test_brief_output_is_exact(self):
        self.publish_chain(3)
        brief = self.run_om("status", "--operation", str(self.operation), "--brief")
        self.assertEqual(brief.returncode, 0, brief.stderr)
        self.assertEqual(
            brief.stdout,
            "operation=demo-operation context=1 events=3 tasks=3\n"
            "demo-00 ready\n"
            "demo-01 blocked depends=demo-00\n"
            "demo-02 blocked depends=demo-01\n",
        )
        self.assertNotIn("sha256", brief.stdout)
        self.assertNotIn("{", brief.stdout)
        self.assertIsNone(re.search(r"[0-9a-f]{64}", brief.stdout))
        with self.assertRaises(json.JSONDecodeError):
            json.loads(brief.stdout)

    def test_default_status_json_is_compatible(self):
        self.publish_chain(2)
        status = self.run_om("status", "--operation", str(self.operation))
        self.assertEqual(status.returncode, 0, status.stderr)
        document = json.loads(status.stdout)
        self.assertEqual(
            set(document), {"format", "operation", "context", "event_head", "tasks"}
        )
        self.assertEqual(document["format"], "om-status/1")
        self.assertEqual(document["operation"], "demo-operation")
        self.assertEqual(document["context"], 1)
        self.assertEqual(document["event_head"]["seq"], 2)
        self.assertEqual(len(document["event_head"]["hash"]), 64)
        self.assertEqual(
            set(document["tasks"][0]),
            {"id", "kind", "effect", "profile", "state", "depends"},
        )
        self.assertEqual(document["tasks"][0]["state"], "ready")
        self.assertEqual(document["tasks"][1]["state"], "blocked")

    def test_brief_is_at_least_60_percent_smaller_than_json(self):
        self.publish_chain(6)
        full = self.run_om("status", "--operation", str(self.operation))
        brief = self.run_om("status", "--operation", str(self.operation), "--brief")
        self.assertEqual(full.returncode, 0, full.stderr)
        self.assertEqual(brief.returncode, 0, brief.stderr)
        full_bytes = len(full.stdout.encode("utf-8"))
        brief_bytes = len(brief.stdout.encode("utf-8"))
        self.assertLessEqual(
            brief_bytes * 100,
            full_bytes * 40,
            msg="brief=%d bytes, json=%d bytes" % (brief_bytes, full_bytes),
        )

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

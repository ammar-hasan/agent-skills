from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "tmux_agent.py"


@unittest.skipUnless(shutil.which("tmux"), "tmux is required")
class TmuxAgentIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = f"tmux-agent-test-{uuid.uuid4().hex[:12]}"
        self.temporary = tempfile.TemporaryDirectory(prefix="tmux-agent-test-")
        self.run_tmux("new-session", "-d", "-s", self.session, "-n", "worker")

    def tearDown(self) -> None:
        subprocess.run(
            ["tmux", "kill-session", "-t", self.session],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        self.temporary.cleanup()

    def run_tmux(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["tmux", *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def run_helper(self, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(HELPER), *args],
            input=stdin,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def test_generic_state_signal_and_compact_watch(self) -> None:
        target = self.run_tmux(
            "new-window", "-d", "-P", "-F",
            "#{session_name}:#{window_index}.#{pane_index}",
            "-t", f"{self.session}:",
            "python3 -c 'import time; time.sleep(30)'",
        ).stdout.strip()
        assigned = json.loads(self.run_helper(
            "assign", "--target", target, "--task-id", "generic-test",
            "--deadline-minutes", "2", "--no-enter",
            stdin="Perform a harmless integration test.",
        ).stdout)
        self.assertEqual(assigned["state"], "assigned")
        self.assertEqual(assigned["sequence"], 0)

        signaled = json.loads(self.run_helper(
            "signal", "--target", target, "--task-id", "generic-test",
            "--state", "working", "--phase", "integration",
        ).stdout)
        self.assertEqual(signaled["sequence"], 1)

        observed = json.loads(self.run_helper(
            "watch", "--target", target, "--task-id", "generic-test",
            "--since-sequence", "0", "--timeout", "1",
        ).stdout)
        self.assertTrue(observed["changed"])
        self.assertNotIn("content", observed)

        unchanged = json.loads(self.run_helper(
            "watch", "--target", target, "--task-id", "generic-test",
            "--since-sequence", "1", "--timeout", "1",
        ).stdout)
        self.assertFalse(unchanged["changed"])
        self.assertTrue(unchanged["timed_out"])
        self.assertGreaterEqual(unchanged["spurious_wakes"], 1)

    def test_active_retask_requires_replace_and_resets_metadata(self) -> None:
        target = self.run_tmux(
            "new-window", "-d", "-P", "-F",
            "#{session_name}:#{window_index}.#{pane_index}",
            "-t", f"{self.session}:",
            "python3 -c 'import time; time.sleep(30)'",
        ).stdout.strip()
        first = json.loads(self.run_helper(
            "assign", "--target", target, "--task-id", "first-task",
            "--deadline-minutes", "10", "--no-enter",
            stdin="First assignment.",
        ).stdout)
        old_channel = first["signal_channel"]
        self.run_helper(
            "signal", "--target", target, "--task-id", "first-task",
            "--state", "working", "--phase", "old-work", "--summary", "stale summary",
        )

        refused = subprocess.run(
            [
                "python3", str(HELPER), "assign", "--target", target,
                "--task-id", "second-task", "--no-enter",
            ],
            input="Second assignment.",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("use --replace", refused.stderr)

        watcher = subprocess.Popen(
            [
                "python3", str(HELPER), "watch", "--target", target,
                "--task-id", "first-task", "--since-sequence", "1", "--timeout", "5",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            time.sleep(0.1)
            replaced = json.loads(self.run_helper(
                "assign", "--target", target, "--task-id", "second-task",
                "--deadline-minutes", "2", "--replace", "--no-enter",
                stdin="Second assignment.",
            ).stdout)
            watcher_stdout, watcher_stderr = watcher.communicate(timeout=3)
        finally:
            if watcher.poll() is None:
                watcher.kill()
                watcher.communicate()

        self.assertEqual(watcher.returncode, 0, watcher_stderr)
        replacement_event = json.loads(watcher_stdout)
        self.assertTrue(replacement_event["task_changed"])
        self.assertEqual(replacement_event["previous_task_id"], "first-task")
        self.assertEqual(replacement_event["task_id"], "second-task")

        self.assertTrue(replaced["task_changed"])
        self.assertEqual(replaced["previous_task_id"], "first-task")
        self.assertEqual(replaced["state"], "assigned")
        self.assertEqual(replaced["sequence"], 0)
        self.assertEqual(replaced["summary"], "")
        self.assertNotEqual(replaced["signal_channel"], old_channel)
        self.assertGreater(replaced["deadline"], int(time.time()))

    def test_forced_signal_task_repair_clears_stale_metadata(self) -> None:
        target = self.run_tmux(
            "new-window", "-d", "-P", "-F",
            "#{session_name}:#{window_index}.#{pane_index}",
            "-t", f"{self.session}:",
            "python3 -c 'import time; time.sleep(30)'",
        ).stdout.strip()
        first = json.loads(self.run_helper(
            "assign", "--target", target, "--task-id", "wrong-task",
            "--deadline-minutes", "10", "--no-enter",
            stdin="Assignment with a mistaken task identifier.",
        ).stdout)
        repaired = json.loads(self.run_helper(
            "signal", "--target", target, "--task-id", "correct-task",
            "--state", "working", "--phase", "recovered", "--force",
        ).stdout)
        self.assertTrue(repaired["task_changed"])
        self.assertEqual(repaired["previous_task_id"], "wrong-task")
        self.assertEqual(repaired["sequence"], 1)
        self.assertEqual(repaired["summary"], "")
        self.assertEqual(repaired["deadline"], 0)
        self.assertNotEqual(repaired["signal_channel"], first["signal_channel"])

    def test_send_refuses_an_unconfirmed_shell_pane(self) -> None:
        result = subprocess.run(
            [
                "python3", str(HELPER), "send", "--target", f"{self.session}:0.0",
                "--no-enter",
            ],
            input="Do not execute this as shell input.",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to paste agent input", result.stderr)

    def test_answer_submits_text_to_a_generic_child_prompt(self) -> None:
        target = self.run_tmux(
            "new-window", "-d", "-P", "-F",
            "#{session_name}:#{window_index}.#{pane_index}",
            "-t", f"{self.session}:",
            "python3 -u -c 'value=input(); print(\"ANSWER=\" + value, flush=True); import time; time.sleep(5)'",
        ).stdout.strip()
        result = json.loads(self.run_helper(
            "answer", "--target", target, stdin="Use the existing format.\n",
        ).stdout)
        self.assertEqual(result["mode"], "text")
        self.assertTrue(result["submitted"])

        captured = ""
        for _ in range(20):
            captured = self.run_helper("capture", "--target", target).stdout
            if "ANSWER=Use the existing format." in captured:
                break
            time.sleep(0.05)
        self.assertIn("ANSWER=Use the existing format.", captured)

    def test_answer_accepts_explicit_navigation_keys(self) -> None:
        target = self.run_tmux(
            "new-window", "-d", "-P", "-F",
            "#{session_name}:#{window_index}.#{pane_index}",
            "-t", f"{self.session}:",
            "python3 -c 'import time; time.sleep(5)'",
        ).stdout.strip()
        result = json.loads(self.run_helper(
            "answer", "--target", target, "--keys", "down", "space", "enter",
        ).stdout)
        self.assertEqual(result["mode"], "keys")
        self.assertEqual(result["keys"], ["down", "space", "enter"])

    def test_capture_hash_suppresses_unchanged_screen(self) -> None:
        # A shell prompt can finish drawing between captures on a fresh runner.
        # Wait for a quiet fixture so this tests deduplication of stable output.
        target = self.run_tmux(
            "new-window", "-d", "-P", "-F",
            "#{session_name}:#{window_index}.#{pane_index}",
            "-t", f"{self.session}:",
            "python3 -u -c 'print(\"CAPTURE_READY\", flush=True); import time; time.sleep(30)'",
        ).stdout.strip()
        deadline = time.monotonic() + 5
        while True:
            first = json.loads(self.run_helper("capture", "--target", target, "--json").stdout)
            if "CAPTURE_READY" in first["content"]:
                break
            if time.monotonic() >= deadline:
                self.fail("Capture fixture did not become ready")
            time.sleep(0.05)
        second = json.loads(self.run_helper(
            "capture", "--target", target, "--since-hash", first["screen_hash"], "--json",
        ).stdout)
        self.assertFalse(second["changed"])
        self.assertEqual(second["content"], "")

    def test_snapshot_dry_run_and_restore_preserve_topology(self) -> None:
        original_target = f"{self.session}:0.0"
        self.run_tmux("split-window", "-d", "-h", "-t", f"{self.session}:0")
        for option, value in (
            ("@agent_task_id", "restore-test"),
            ("@agent_state", "complete"),
            ("@agent_phase", "done"),
            ("@agent_sequence", "4"),
            ("@agent_signal_channel", "old-channel"),
        ):
            self.run_tmux("set-option", "-p", "-t", original_target, option, value)
        snapshot = Path(self.temporary.name) / "snapshot.json"
        result = json.loads(self.run_helper(
            "snapshot", "--session", self.session, "--output", str(snapshot),
            "--require-restorable",
        ).stdout)
        self.assertEqual(result["panes"], 2)
        plan = json.loads(self.run_helper("restore", "--input", str(snapshot)).stdout)
        self.assertTrue(plan["ready"])

        self.run_tmux("kill-session", "-t", self.session)
        restored = json.loads(self.run_helper("restore", "--input", str(snapshot), "--yes").stdout)
        self.assertEqual(restored["restored_panes"], 2)
        panes = self.run_tmux("list-panes", "-t", f"{self.session}:0", "-F", "#{pane_id}").stdout.splitlines()
        self.assertEqual(len(panes), 2)
        restored_state = self.run_tmux(
            "show-options", "-p", "-q", "-v", "-t", f"{self.session}:0.0", "@agent_state",
        ).stdout.strip()
        restored_sequence = self.run_tmux(
            "show-options", "-p", "-q", "-v", "-t", f"{self.session}:0.0", "@agent_sequence",
        ).stdout.strip()
        restored_channel = self.run_tmux(
            "show-options", "-p", "-q", "-v", "-t", f"{self.session}:0.0", "@agent_signal_channel",
        ).stdout.strip()
        self.assertEqual(restored_state, "restored")
        self.assertEqual(restored_sequence, "5")
        self.assertNotEqual(restored_channel, "old-channel")


if __name__ == "__main__":
    unittest.main()

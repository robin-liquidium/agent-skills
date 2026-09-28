import asyncio
import contextlib
import io
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import telegram_cli as cli


def dialog(chat_id, name):
    return SimpleNamespace(
        id=chat_id,
        name=name,
        entity=SimpleNamespace(id=abs(chat_id), title=name, username=None, bot=False),
        is_user=False,
        is_group=True,
        is_channel=False,
        unread_count=0,
        unread_mentions_count=0,
        date=None,
        pinned=False,
        archived=False,
        dialog=SimpleNamespace(notify_settings=None),
    )


class FakeClient:
    def __init__(self, dialogs):
        self.dialogs = dialogs
        self.yielded = 0
        self.disconnected = False
        self.cancelled = False

    async def iter_dialogs(self, **kwargs):
        assert kwargs == {"limit": 2000, "archived": None}
        for item in self.dialogs:
            self.yielded += 1
            yield item

    async def get_messages(self, *args, **kwargs):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    async def disconnect(self):
        self.disconnected = True


class DialogResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_numeric_id_stops_at_first_match(self):
        client = FakeClient([dialog(1, "first"), dialog(-1234567890, "target"), dialog(3, "later")])
        result = await cli.resolve_dialog(client, "-1234567890")
        self.assertEqual(result.id, -1234567890)
        self.assertEqual(client.yielded, 2)

    async def test_name_scans_for_ambiguity(self):
        client = FakeClient([dialog(1, "Same"), dialog(2, "other"), dialog(3, "same")])
        with self.assertRaisesRegex(SystemExit, "Ambiguous chat"):
            await cli.resolve_dialog(client, "same")
        self.assertEqual(client.yielded, 3)

    async def test_deadline_cancels_read_and_disconnects(self):
        client = FakeClient([dialog(123, "target")])
        with patch.object(cli, "load_settings", return_value=None), \
             patch.object(cli, "build_client", return_value=client), \
             patch.object(cli, "OPERATION_TIMEOUT_SECONDS", 0.03), \
             patch.object(sys, "argv", ["telegram-cli", "messages", "--chat", "123"]):
            with self.assertRaises(TimeoutError):
                await cli.async_main()
        self.assertTrue(client.cancelled)
        self.assertTrue(client.disconnected)

    async def test_auth_is_not_subject_to_read_deadline(self):
        async def slow_auth(args, parser):
            await asyncio.sleep(0.03)
            return 0

        with patch.object(cli, "run_command", slow_auth), \
             patch.object(cli, "OPERATION_TIMEOUT_SECONDS", 0.01), \
             patch.object(sys, "argv", ["telegram-cli", "auth"]):
            self.assertEqual(await cli.async_main(), 0)


class TimeoutReportingTests(unittest.TestCase):
    def test_timeout_reports_write_uncertainty(self):
        async def timed_out():
            raise TimeoutError

        stderr = io.StringIO()
        with patch.object(cli, "maybe_reexec_local_venv"), \
             patch.object(cli, "async_main", timed_out), \
             contextlib.redirect_stderr(stderr):
            self.assertEqual(cli.main(), 124)
        self.assertIn("outcome is unknown", stderr.getvalue())
        self.assertIn("before retrying", stderr.getvalue())


class LauncherCleanupTests(unittest.TestCase):
    def test_termination_stops_transient_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            bin_dir = home / "bin"
            bin_dir.mkdir()
            credential = home / ".config/credentials.encrypted/telegram-mcp-tunnel.env.cred"
            credential.parent.mkdir(parents=True)
            credential.touch()
            loader = home / ".local/libexec/with-systemd-env-credential"
            loader.parent.mkdir(parents=True)
            loader.write_text("#!/bin/sh\nexit 0\n")
            loader.chmod(0o700)
            run_pid_file = home / "run.pid"
            run_args_file = home / "run.args"
            stop_log = home / "stop.log"
            systemd_run = bin_dir / "systemd-run"
            systemd_run.write_text(
                "#!/bin/sh\nprintf '%s' \"$$\" > \"$MOCK_RUN_PID_FILE\"\n"
                "printf '%s\\n' \"$@\" > \"$MOCK_RUN_ARGS_FILE\"\nexec sleep 30\n"
            )
            systemd_run.chmod(0o700)
            systemctl = bin_dir / "systemctl"
            systemctl.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" > \"$MOCK_STOP_LOG\"\n"
                "kill \"$(cat \"$MOCK_RUN_PID_FILE\")\"\n"
            )
            systemctl.chmod(0o700)
            env = dict(os.environ, HOME=str(home), PATH=f"{bin_dir}:{os.environ['PATH']}",
                       MOCK_RUN_PID_FILE=str(run_pid_file), MOCK_RUN_ARGS_FILE=str(run_args_file),
                       MOCK_STOP_LOG=str(stop_log))
            process = subprocess.Popen([str(SKILL_DIR / "scripts/telegram-cli"), "messages", "--chat", "123"], env=env)
            try:
                for _ in range(100):
                    if run_args_file.exists():
                        break
                    time.sleep(0.01)
                self.assertTrue(run_args_file.exists())
                self.assertIn(str(SKILL_DIR / "scripts/telegram-cli"), run_args_file.read_text())
                process.send_signal(signal.SIGTERM)
                self.assertEqual(process.wait(timeout=5), 143)
                self.assertIn("--user stop telegram-cli-", stop_log.read_text())
                pid = int(run_pid_file.read_text())
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    unittest.main()

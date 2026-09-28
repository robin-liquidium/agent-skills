import importlib.util
import json
import os
import shutil
import stat
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "scripts" / "twitterapi_io.py"
SETUP_PATH = SKILL_DIR / "scripts" / "setup-api-key.sh"
LAUNCHER_PATH = SKILL_DIR / "scripts" / "twitterapi-io"
spec = importlib.util.spec_from_file_location("twitterapi_io", MODULE_PATH)
twitterapi_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(twitterapi_io)


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.config_path = self.home / ".config" / "twitterapi-io" / "config.json"
        self.config_path.parent.mkdir(parents=True)
        self.config_patch = mock.patch.multiple(
            twitterapi_io,
            CONFIG_DIR=self.config_path.parent,
            CONFIG_PATH=self.config_path,
            ENV_FALLBACK_PATH=self.home / "absent.env",
        )
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    def test_get_api_key_resolves_vault_reference(self):
        self.config_path.write_text(json.dumps({"api_key": {"$agent_secret": "test/twitter-key"}}))
        completed = subprocess.CompletedProcess([], 0, stdout="fake-api-key\n")
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            twitterapi_io.subprocess, "run", return_value=completed
        ) as run, mock.patch.object(twitterapi_io.Path, "home", return_value=self.home):
            self.assertEqual(twitterapi_io.get_api_key(), "fake-api-key")
        self.assertEqual(run.call_args.args[0], [str(self.home / ".local/bin/secrets"), "get", "test/twitter-key"])
        self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_get_api_key_rejects_embedded_newline(self):
        with mock.patch.dict(os.environ, {"TWITTERAPI_IO_KEY": "fake-key\nx-evil: 1"}, clear=True), \
             self.assertRaisesRegex(SystemExit, "Invalid TwitterAPI key"):
            twitterapi_io.get_api_key()

    def test_get_api_key_vault_timeout_uses_existing_error(self):
        self.config_path.write_text(json.dumps({"api_key": {"$agent_secret": "test/twitter-key"}}))
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            twitterapi_io.subprocess, "run", side_effect=subprocess.TimeoutExpired("secrets", 15)
        ), self.assertRaisesRegex(SystemExit, "Cannot load TwitterAPI credential"):
            twitterapi_io.get_api_key()

    def test_save_config_rotates_vault_without_plaintext_file(self):
        original = json.dumps({"api_key": {"$agent_secret": "test/other-key"}}) + "\n"
        self.config_path.write_text(original)
        with mock.patch.object(twitterapi_io.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run, mock.patch.object(
            twitterapi_io.Path, "home", return_value=self.home
        ):
            twitterapi_io.save_config({"api_key": "replacement-fake-key"})
        self.assertEqual(self.config_path.read_text(), original)
        self.assertEqual(run.call_args.args[0], [str(self.home / ".local/bin/secrets"), "set", "test/other-key", "--stdin"])
        self.assertEqual(run.call_args.kwargs["input"], "replacement-fake-key")
        self.assertEqual(run.call_args.kwargs["timeout"], 15)
        self.assertNotIn("replacement-fake-key", " ".join(run.call_args.args[0]))

    def test_save_config_vault_timeout_uses_existing_error(self):
        original = json.dumps({"api_key": {"$agent_secret": "test/other-key"}}) + "\n"
        self.config_path.write_text(original)
        with mock.patch.object(twitterapi_io.subprocess, "run", side_effect=subprocess.TimeoutExpired("secrets", 15)), \
             self.assertRaisesRegex(SystemExit, "Cannot update TwitterAPI credential"):
            twitterapi_io.save_config({"api_key": "replacement-fake-key"})
        self.assertEqual(self.config_path.read_text(), original)

    def test_malformed_vault_reference_cannot_be_replaced_with_plaintext(self):
        original = json.dumps({"api_key": {"$agent_secret": ""}}) + "\n"
        self.config_path.write_text(original)
        result = subprocess.run(
            ["bash", str(SETUP_PATH)], input="replacement-fake-key\n", text=True, capture_output=True,
            env={**os.environ, "HOME": str(self.home)}, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config_path.read_text(), original)
        self.assertNotIn("replacement-fake-key", result.stdout + result.stderr)
        with self.assertRaisesRegex(SystemExit, "Invalid agent-secrets reference"):
            twitterapi_io.save_config({"api_key": "replacement-fake-key"})
        self.assertEqual(self.config_path.read_text(), original)

    def test_curl_receives_secret_on_stdin_only(self):
        with mock.patch.object(twitterapi_io, "get_api_key", return_value="fake-api-key"), mock.patch.object(
            twitterapi_io.subprocess, "check_output", return_value=b'{"ok": true}'
        ) as check_output:
            self.assertEqual(twitterapi_io.curl_json("/test", {"name": "a b"}), {"ok": True})
        command = check_output.call_args.args[0]
        self.assertIn("@-", command)
        self.assertEqual(command[-1], "https://api.twitterapi.io/test?name=a+b")
        self.assertNotIn("fake-api-key", " ".join(command))
        self.assertEqual(check_output.call_args.kwargs["input"], b"x-api-key: fake-api-key\n")

    @unittest.skipUnless(shutil.which("curl"), "curl is required")
    def test_curl_sends_stdin_header_to_server(self):
        received = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received["key"] = self.headers.get("x-api-key")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok": true}')

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with mock.patch.object(twitterapi_io, "get_api_key", return_value="fake-api-key"), mock.patch.object(
                twitterapi_io, "BASE_URL", f"http://127.0.0.1:{server.server_port}"
            ):
                self.assertEqual(twitterapi_io.curl_json("/test"), {"ok": True})
            self.assertEqual(received["key"], "fake-api-key")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_setup_saves_private_config(self):
        result = subprocess.run(
            ["bash", str(SETUP_PATH)], input="fake-api-key\n", text=True, capture_output=True,
            env={**os.environ, "HOME": str(self.home)}, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.config_path.read_text()), {"api_key": "fake-api-key"})
        self.assertEqual(stat.S_IMODE(self.config_path.stat().st_mode), 0o600)
        self.assertNotIn("fake-api-key", result.stdout + result.stderr)

    def test_setup_rotates_arbitrary_existing_vault_reference(self):
        original = json.dumps({"api_key": {"$agent_secret": "test/other-key"}}) + "\n"
        self.config_path.write_text(original)
        secrets = self.home / ".local" / "bin" / "secrets"
        secrets.parent.mkdir(parents=True)
        secrets.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$HOME/secrets-args"\n')
        secrets.chmod(0o700)
        result = subprocess.run(
            ["bash", str(SETUP_PATH)], text=True, capture_output=True,
            env={**os.environ, "HOME": str(self.home)}, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / "secrets-args").read_text(), "set\ntest/other-key\n")
        self.assertEqual(self.config_path.read_text(), original)

    def test_linux_launcher_selects_encrypted_credential_when_config_absent(self):
        home = self.home / "literal${HOME}"
        home.mkdir()
        credential = home / ".config" / "credentials.encrypted" / "twitterapi-mcp-tunnel.env.cred"
        credential.parent.mkdir(parents=True)
        credential.write_text("fake encrypted credential")
        loader = home / ".local" / "libexec" / "with-systemd-env-credential"
        loader.parent.mkdir(parents=True)
        loader.write_text("#!/bin/sh\nexit 0\n")
        loader.chmod(0o700)
        fake_bin = home / "bin"
        fake_bin.mkdir()
        systemd_run = fake_bin / "systemd-run"
        systemd_run.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$HOME/systemd-run-args"\n')
        systemd_run.chmod(0o700)
        result = subprocess.run(
            ["bash", "scripts/twitterapi-io", "help", "${LITERAL}", "$$"], cwd=SKILL_DIR, text=True, capture_output=True,
            env={**os.environ, "HOME": str(home), "PATH": f"{fake_bin}:{os.environ['PATH']}"}, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = (home / "systemd-run-args").read_text().splitlines()
        self.assertIn(f"--property=LoadCredentialEncrypted=runtime.env:{credential}", arguments)
        self.assertIn(str(loader).replace("$", "$$"), arguments)
        self.assertIn("--same-dir", arguments)
        self.assertNotIn("--expand-environment=no", arguments)
        self.assertEqual(arguments[-4:], [str(LAUNCHER_PATH), "help", "$${LITERAL}", "$$$$"])

        (home / "systemd-run-args").unlink()
        config = home / ".config/twitterapi-io/config.json"
        config.parent.mkdir(parents=True)
        config.write_text('{"api_key": ""}')
        result = subprocess.run(
            ["bash", "scripts/twitterapi-io", "help"], cwd=SKILL_DIR, text=True, capture_output=True,
            env={**os.environ, "HOME": str(home), "PATH": f"{fake_bin}:{os.environ['PATH']}"}, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((home / "systemd-run-args").exists())

    def test_explicit_key_skips_encrypted_launcher(self):
        credential = self.home / ".config/credentials.encrypted/twitterapi-mcp-tunnel.env.cred"
        credential.parent.mkdir(parents=True)
        credential.touch()
        loader = self.home / ".local/libexec/with-systemd-env-credential"
        loader.parent.mkdir(parents=True)
        loader.write_text("#!/bin/sh\nexit 0\n")
        loader.chmod(0o700)
        fake_bin = self.home / "bin"
        fake_bin.mkdir()
        (fake_bin / "systemd-run").write_text("#!/bin/sh\nexit 99\n")
        (fake_bin / "systemd-run").chmod(0o700)
        (fake_bin / "python3").write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
        (fake_bin / "python3").chmod(0o700)
        result = subprocess.run(["bash", str(LAUNCHER_PATH), "help"], text=True, capture_output=True,
                                env={**os.environ, "HOME": str(self.home), "PATH": f"{fake_bin}:{os.environ['PATH']}",
                                     "TWITTERAPI_IO_KEY": "explicit-key"}, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(MODULE_PATH), result.stdout)


if __name__ == "__main__":
    unittest.main()

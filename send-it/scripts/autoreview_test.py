#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import copy
import importlib.util
import io
import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).with_name("autoreview")
LOADER = SourceFileLoader("autoreview_module", str(SCRIPT_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
AUTOREVIEW = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(AUTOREVIEW)


FINAL_REPORT = {
    "findings": [],
    "overall_correctness": "patch is correct",
    "overall_explanation": "clean",
    "overall_confidence": 0.9,
}

DRAFT_REPORT = {
    "findings": [
        {
            "title": "Draft finding",
            "body": "draft",
            "priority": "P3",
            "confidence": 0.2,
            "category": "maintainability",
            "code_location": {"file_path": "draft.js", "line": 1},
        }
    ],
    "overall_correctness": "patch is incorrect",
    "overall_explanation": "draft",
    "overall_confidence": 0.2,
}


class AutoreviewCursorTests(unittest.TestCase):
    def test_extract_json_prefers_terminal_result_event(self) -> None:
        stream = "\n".join(
            [
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {"role": "assistant", "content": [{"type": "text", "text": json.dumps(DRAFT_REPORT)}]},
                    }
                ),
                json.dumps(
                    {
                        "type": "result",
                        "subtype": "success",
                        "result": json.dumps(FINAL_REPORT),
                        "session_id": "session-id",
                        "request_id": "request-id",
                    }
                ),
            ]
        )
        self.assertEqual(AUTOREVIEW.extract_json(stream), FINAL_REPORT)

    def test_extract_json_can_fallback_to_assistant_message(self) -> None:
        stream = json.dumps(
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": json.dumps(FINAL_REPORT)}]},
            }
        )
        self.assertEqual(AUTOREVIEW.extract_json(stream), FINAL_REPORT)

    def test_extract_json_does_not_fallback_past_bad_terminal_result(self) -> None:
        stream = "\n".join(
            [
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {"role": "assistant", "content": [{"type": "text", "text": json.dumps(FINAL_REPORT)}]},
                    }
                ),
                json.dumps(
                    {
                        "type": "result",
                        "subtype": "success",
                        "result": "not json",
                    }
                ),
            ]
        )
        with self.assertRaises(SystemExit) as exc_info:
            AUTOREVIEW.extract_json(stream)
        self.assertIn("review engine result was not structured JSON", str(exc_info.exception))


class AutoreviewPriorityTests(unittest.TestCase):
    def test_default_priority_is_p0(self) -> None:
        with mock.patch.object(sys, "argv", ["autoreview"]):
            args = AUTOREVIEW.parse_args()
        self.assertEqual(args.max_priority, "P0")

    def test_priority_filter_omits_lower_findings_and_cleans_verdict(self) -> None:
        report = copy.deepcopy(DRAFT_REPORT)
        AUTOREVIEW.filter_findings_by_priority(report, "P0")
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["overall_correctness"], "patch is correct")
        self.assertIn("below the requested P0", report["overall_explanation"])


class AutoreviewSecretScannerTests(unittest.TestCase):
    def test_typescript_type_annotations_are_not_credential_material(self) -> None:
        source = "\n".join(
            (
                "export function modelRuntime(",
                "  env: NodeJS.ProcessEnv = process.env,",
                "): ModelRuntime {",
                "  return env.MODEL_RUNTIME;",
                "}",
                "",
                "export function modelRuntimeCredentials(",
                "  env: NodeJS.ProcessEnv,",
                "): NodeJS.ProcessEnv {",
                "  const credentials: NodeJS.ProcessEnv = {};",
                "  return credentials;",
                "}",
            )
        )

        self.assertFalse(
            AUTOREVIEW.secret_text_risk(
                source,
                javascript_dialect="typescript",
            )
        )
        self.assertEqual(
            AUTOREVIEW.review_secret_fragments(
                source,
                javascript_dialect="typescript",
            ),
            set(),
        )

    def test_typescript_typed_declaration_still_scans_initializer(self) -> None:
        literal_value = "actual-production-" + "secret"
        source = (
            "const credentials: NodeJS.ProcessEnv = "
            f'"{literal_value}";'
        )

        self.assertTrue(
            AUTOREVIEW.secret_text_risk(
                source,
                javascript_dialect="typescript",
            )
        )
        self.assertEqual(
            AUTOREVIEW.review_secret_fragments(
                source,
                javascript_dialect="typescript",
            ),
            {literal_value},
        )

    def test_boolean_declarations_are_not_credential_material(self) -> None:
        secret_field = "is" + "Secret"
        client_secret_field = "hasClient" + "Secret"
        cases = (
            (f"val {secret_field}: Boolean? = null,", None),
            (f"var {client_secret_field}: Boolean = false", None),
            (f"abstract val {secret_field}: Boolean?", None),
            (f"val {secret_field}: Boolean?", None),
            (f"const {client_secret_field}: boolean = true;", "typescript"),
            (f"declare const {client_secret_field}: boolean;", "typescript"),
            (f"let {secret_field}: Bool? = nil", None),
            (f"let {secret_field}: Bool?", None),
        )

        for content, javascript_dialect in cases:
            with self.subTest(content=content):
                self.assertFalse(
                    AUTOREVIEW.secret_text_risk(
                        content,
                        javascript_dialect=javascript_dialect,
                    )
                )

    def test_boolean_and_null_literal_values_are_not_credentials(self) -> None:
        cases = (
            ("is" + "Secret", "true"),
            ("requires" + "Password", "false"),
            ("access" + "Token", "null"),
        )
        for field_name, literal in cases:
            content = f"{field_name} = {literal}"
            with self.subTest(content=content):
                self.assertFalse(AUTOREVIEW.secret_text_risk(content))

    def test_boolean_annotation_does_not_hide_real_credential_literal(self) -> None:
        literal_value = "actual-production-" + "secret"
        secret_field = "is" + "Secret"
        client_secret_field = "hasClient" + "Secret"
        cases = (
            (f'val {secret_field}: Boolean? = "{literal_value}",', None),
            (f'var {client_secret_field}: Boolean = "{literal_value}"', None),
            (
                f'const {client_secret_field}: boolean = "{literal_value}";',
                "typescript",
            ),
            (f'let {secret_field}: Bool? = "{literal_value}"', None),
        )

        for content, javascript_dialect in cases:
            with self.subTest(content=content):
                self.assertTrue(
                    AUTOREVIEW.secret_text_risk(
                        content,
                        javascript_dialect=javascript_dialect,
                    )
                )

    def test_boolean_prefix_values_remain_credentials(self) -> None:
        field_name = "client" + "Secret"
        for prefix in ("Boolean", "boolean", "Bool"):
            literal_value = prefix + "-prod-credential"
            content = f"{field_name}: {literal_value}"
            with self.subTest(content=content):
                self.assertTrue(AUTOREVIEW.secret_text_risk(content))

    def test_boolean_type_tokens_in_config_remain_credentials(self) -> None:
        field_name = "client" + "Secret"
        for literal_value in ("Boolean?", "Boolean?=abc1234"):
            content = f"{field_name}: {literal_value}"
            with self.subTest(content=content):
                self.assertTrue(AUTOREVIEW.secret_text_risk(content))


class AutoreviewCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.home_dir = tempfile.TemporaryDirectory(prefix="autoreview-test-home.")
        cls.home_patch = mock.patch.object(Path, "home", return_value=Path(cls.home_dir.name))
        cls.home_patch.start()
        cls.home_keys = ("HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH")
        cls.old_home_env = {key: os.environ.get(key) for key in cls.home_keys}
        os.environ["HOME"] = cls.home_dir.name
        os.environ["USERPROFILE"] = cls.home_dir.name
        os.environ.pop("HOMEDRIVE", None)
        os.environ.pop("HOMEPATH", None)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.home_patch.stop()
        for key, value in cls.old_home_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls.home_dir.cleanup()

    def test_harness_rejects_disabled_cursor_engine(self) -> None:
        harness_path = SCRIPT_PATH.with_name("test-review-harness.py")
        namespace = runpy.run_path(str(harness_path))
        with self.assertRaises(SystemExit):
            namespace["parse_args"](["--engine", "cursor"])

    def test_cursor_agent_bin_cli_alias(self) -> None:
        with mock.patch.object(
            sys,
            "argv",
            ["autoreview", "--cursor-agent-bin", "/tmp/legacy-cursor"],
        ):
            args = AUTOREVIEW.parse_args()
        self.assertEqual(args.cursor_bin, "/tmp/legacy-cursor")

    def test_cursor_agent_bin_env_alias(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"CURSOR_AGENT_BIN": "/tmp/legacy-cursor"},
            clear=False,
        ):
            os.environ.pop("CURSOR_BIN", None)
            with mock.patch.object(sys, "argv", ["autoreview"]):
                args = AUTOREVIEW.parse_args()
        self.assertEqual(args.cursor_bin, "/tmp/legacy-cursor")

    def test_cursor_agent_reviewer_alias_normalizes_to_cursor(self) -> None:
        self.assertEqual(
            AUTOREVIEW.parse_reviewer_token("cursor-agent:auto"),
            ("cursor", "auto", None),
        )

    def test_cursor_agent_keyed_option_normalizes_to_cursor(self) -> None:
        self.assertEqual(
            AUTOREVIEW.parse_keyed_options(["cursor-agent=auto"], "model"),
            (None, {"cursor": "auto"}),
        )

    def test_codex_config_status_exposes_keys_only(self) -> None:
        args = argparse.Namespace(codex_config=['model_verbosity="low"'])
        self.assertEqual(AUTOREVIEW.codex_config_keys(args), ["model_verbosity"])

    def test_opencodex_freezes_selected_catalog_without_loading_user_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            repo.mkdir()
            catalog = root / "catalog.json"
            selected = {"slug": "kimi-code/k3", "display_name": "Kimi"}
            catalog.write_text(json.dumps({"models": [selected, {"slug": "xai/grok-4.7"}]}))
            config = {"openai_base_url": "http://127.0.0.1:10100/v1", "model_catalog_json": str(catalog),
                      "mcp_servers": {"hostile": {"command": "touch"}}, "developer_instructions": "run send-it"}
            with mock.patch.object(AUTOREVIEW, "codex_source_home", return_value=root), mock.patch.object(
                AUTOREVIEW, "load_codex_auth_config", return_value=config
            ):
                flags = AUTOREVIEW.codex_opencodex_flags(argparse.Namespace(codex_opencodex=True), repo, root, "kimi-code/k3")
            frozen = root / "opencodex-catalog.json"
            catalog.write_text("{}")
            self.assertEqual(json.loads(frozen.read_text()), {"models": [selected]})
            self.assertIn('openai_base_url="http://127.0.0.1:10100/v1"', flags)
            self.assertNotIn("hostile", " ".join(flags))
            self.assertNotIn("developer_instructions", " ".join(flags))

    def test_opencodex_rejects_remote_routes_and_repository_catalogs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            repo.mkdir()
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps({"models": [{"slug": "kimi-code/k3"}]}))
            config = {"model_catalog_json": str(catalog)}
            with mock.patch.object(AUTOREVIEW, "codex_source_home", return_value=root), mock.patch.object(
                AUTOREVIEW, "load_codex_auth_config", return_value=config
            ):
                for endpoint in ["https://example.com/v1", "http://127.0.0.1.evil.example/v1", "http://user@localhost/v1", "http://localhost/v1?token=x"]:
                    config["openai_base_url"] = endpoint
                    with self.subTest(endpoint=endpoint), self.assertRaises(SystemExit):
                        AUTOREVIEW.codex_opencodex_flags(argparse.Namespace(codex_opencodex=True), repo, root, "kimi-code/k3")
                config["openai_base_url"] = "http://127.0.0.1:10100/v1"
                linked = root / "linked.json"
                linked.symlink_to(repo / "catalog.json")
                config["model_catalog_json"] = str(linked)
                with self.assertRaisesRegex(SystemExit, "outside"):
                    AUTOREVIEW.codex_opencodex_flags(argparse.Namespace(codex_opencodex=True), repo, root, "kimi-code/k3")
                (root / "config.toml").symlink_to(repo / "config.toml")
                with self.assertRaisesRegex(SystemExit, "user config"):
                    AUTOREVIEW.codex_opencodex_flags(argparse.Namespace(codex_opencodex=True), repo, root, "kimi-code/k3")

    def test_opencodex_uses_same_origin_realtime_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            repo.mkdir()
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps({"models": [{"slug": "xai/grok-4.7"}]}))
            config = {
                "openai_base_url": "http://127.0.0.1:10100/backend-api/codex",
                "experimental_realtime_ws_base_url": "http://127.0.0.1:10100/v1",
                "model_catalog_json": str(catalog),
            }
            with mock.patch.object(AUTOREVIEW, "codex_source_home", return_value=root), mock.patch.object(
                AUTOREVIEW, "load_codex_auth_config", return_value=config
            ):
                flags = AUTOREVIEW.codex_opencodex_flags(argparse.Namespace(codex_opencodex=True), repo, root, "xai/grok-4.7")
                self.assertIn('openai_base_url="http://127.0.0.1:10100/v1"', flags)
                config["experimental_realtime_ws_base_url"] = "http://localhost:10101/v1"
                with self.assertRaisesRegex(SystemExit, "loopback /v1"):
                    AUTOREVIEW.codex_opencodex_flags(argparse.Namespace(codex_opencodex=True), repo, root, "xai/grok-4.7")

    def test_opencodex_missing_model_fails_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            repo.mkdir()
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps({"models": [{"slug": "xai/grok-4.7"}]}))
            config = {"openai_base_url": "http://localhost:10100/v1", "model_catalog_json": str(catalog)}
            with mock.patch.object(AUTOREVIEW, "codex_source_home", return_value=root), mock.patch.object(
                AUTOREVIEW, "load_codex_auth_config", return_value=config
            ), self.assertRaisesRegex(SystemExit, "missing or ambiguous"):
                AUTOREVIEW.codex_opencodex_flags(argparse.Namespace(codex_opencodex=True), repo, root, "kimi-code/k3")
        args = AUTOREVIEW.reviewer_test_args(model=["kimi-code/k3"])
        args.codex_opencodex = True
        reviewer = AUTOREVIEW.reviewer_args(args)[0]
        self.assertEqual(reviewer.model, "kimi-code/k3")
        self.assertIsNone(reviewer.fallback_model)

    def test_linux_runtime_grants_only_the_external_native_executable(self) -> None:
        with tempfile.TemporaryDirectory() as td, mock.patch.object(AUTOREVIEW.sys, "platform", "linux"), mock.patch.object(
            AUTOREVIEW.os, "uname", return_value=argparse.Namespace(machine="x86_64")
        ):
            root = Path(td); repo = root / "repo"; repo.mkdir()
            package = root / "npm"; launcher = package / "bin" / "codex.js"
            launcher.parent.mkdir(parents=True); launcher.write_text("// official launcher fixture")
            (package / "package.json").write_text(json.dumps({"name": "@openai/codex"}))
            binary = package / "node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex"
            binary.parent.mkdir(parents=True); binary.write_bytes(b"\x7fELFfixture"); binary.chmod(0o755)
            flags = AUTOREVIEW.codex_linux_runtime_flags(repo, str(launcher))
            self.assertEqual(flags, ["-c", 'permissions.autoreview.filesystem={":minimal"="read",":workspace_roots"="read",'
                                     + f'{json.dumps(str(binary.resolve()))}="read"' + "}"])
            self.assertEqual(AUTOREVIEW.codex_linux_runtime_flags(repo, str(binary)), flags)
            local = repo / "codex"; local.write_bytes(b"\x7fELFfixture"); local.chmod(0o755)
            binary.unlink(); binary.symlink_to(local)
            self.assertEqual(AUTOREVIEW.codex_linux_runtime_flags(repo, str(launcher)), [])
            wrapper = root / "wrapper"; wrapper.write_text("#!/bin/sh\nexit 0\n"); wrapper.chmod(0o755)
            self.assertEqual(AUTOREVIEW.codex_linux_runtime_flags(repo, str(wrapper)), [])

    def test_broken_repo_sandbox_stops_before_model_request(self) -> None:
        with mock.patch.object(sys, "argv", ["autoreview", "--repo-access"]):
            args = AUTOREVIEW.reviewer_args(AUTOREVIEW.parse_args())[0]
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch.object(
            AUTOREVIEW, "resolve_command", return_value="/usr/bin/codex"
        ), mock.patch.object(AUTOREVIEW, "prepare_codex_runtime_auth", return_value=False), mock.patch.object(
            AUTOREVIEW, "codex_source_home", return_value=None
        ), mock.patch.object(AUTOREVIEW.sys, "platform", "linux"), mock.patch.object(
            AUTOREVIEW, "run", return_value=subprocess.CompletedProcess([], 1, "", "bwrap: Operation not permitted")
        ), mock.patch.object(AUTOREVIEW, "run_with_heartbeat") as request:
            with self.assertRaisesRegex(SystemExit, "sandbox preflight failed"):
                AUTOREVIEW.run_codex(args, Path(tmpdir), "review")
            request.assert_not_called()

    def test_routed_models_use_prompt_schema_while_native_codex_keeps_api_schema(self) -> None:
        with mock.patch.object(sys, "argv", ["autoreview"]):
            args = AUTOREVIEW.reviewer_args(AUTOREVIEW.parse_args())[0]
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch.object(
            AUTOREVIEW, "resolve_command", return_value="/usr/bin/codex"
        ), mock.patch.object(AUTOREVIEW, "codex_auth_config_flags", return_value=[]), mock.patch.object(
            AUTOREVIEW, "codex_opencodex_flags", return_value=[]
        ):
            root = Path(tmpdir)
            for routed, model, schema in [(True, "kimi-code/k3", False), (True, "xai/grok-4.7", False), (False, "gpt-6-astra", True)]:
                args.codex_opencodex = routed
                with self.subTest(model=model):
                    cmd = AUTOREVIEW.codex_command(args, root, root, root, root / "schema.json", root / "out.json", model)
                    self.assertEqual("--output-schema" in cmd, schema)
                    self.assertIn("--ignore-user-config", cmd)
                    self.assertIn("--ignore-rules", cmd)
                    self.assertIn("--json", cmd)

    def test_routed_json_prefix_normalization_stays_strict(self) -> None:
        with mock.patch.object(sys, "argv", ["autoreview", "--codex-opencodex", "--model", "kimi-code/k3"]):
            args = AUTOREVIEW.reviewer_args(AUTOREVIEW.parse_args())[0]
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch.object(
            AUTOREVIEW, "resolve_command", return_value="/usr/bin/codex"
        ), mock.patch.object(AUTOREVIEW, "prepare_codex_runtime_auth", return_value=False), mock.patch.object(
            AUTOREVIEW, "codex_source_home", return_value=None
        ), mock.patch.object(AUTOREVIEW, "codex_opencodex_flags", return_value=[]):
            for text, accepted in [("Inspected the code.\n" + json.dumps(FINAL_REPORT), True),
                                   ("Inspected the code.\n" + json.dumps(FINAL_REPORT) + "\n{}", False),
                                   ("Inspected the code.\n{}", False)]:
                def request(cmd, *_args, **_kwargs):
                    Path(cmd[cmd.index("--output-last-message") + 1]).write_text(text)
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                with self.subTest(text=text), mock.patch.object(AUTOREVIEW, "run_with_heartbeat", side_effect=request):
                    if accepted:
                        report = AUTOREVIEW.run_reviewer(args, Path(tmpdir), "review", set(), [])
                        self.assertEqual(report, FINAL_REPORT)
                    else:
                        with self.assertRaises(SystemExit):
                            AUTOREVIEW.run_reviewer(args, Path(tmpdir), "review", set(), [])

    def test_routed_reviews_bypass_inherited_proxies(self) -> None:
        with mock.patch.object(sys, "argv", ["autoreview", "--codex-opencodex", "--model", "kimi-code/k3"]):
            args = AUTOREVIEW.reviewer_args(AUTOREVIEW.parse_args())[0]
        proxy_keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
        inherited = {key: "http://127.0.0.1:9" for key in proxy_keys}
        inherited.update({"NO_PROXY": "", "no_proxy": ""})
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch.object(
            AUTOREVIEW, "resolve_command", return_value="/usr/bin/codex"
        ), mock.patch.object(AUTOREVIEW, "prepare_codex_runtime_auth", return_value=False), mock.patch.object(
            AUTOREVIEW, "codex_source_home", return_value=None
        ), mock.patch.object(AUTOREVIEW, "codex_opencodex_flags", return_value=[]), mock.patch.object(
            AUTOREVIEW, "safe_engine_env", return_value=inherited.copy()
        ):
            def request(cmd, *_args, **kwargs):
                self.assertTrue(all(key not in kwargs["env"] for key in proxy_keys))
                self.assertEqual(kwargs["env"]["NO_PROXY"], "*")
                self.assertEqual(kwargs["env"]["no_proxy"], "*")
                Path(cmd[cmd.index("--output-last-message") + 1]).write_text(json.dumps(FINAL_REPORT))
                return subprocess.CompletedProcess(cmd, 0, "", "")
            with mock.patch.object(AUTOREVIEW, "run_with_heartbeat", side_effect=request):
                self.assertEqual(json.loads(AUTOREVIEW.run_codex(args, Path(tmpdir), "review")), FINAL_REPORT)

    def test_legacy_toml_reader_preserves_only_needed_routing_fields(self) -> None:
        config = AUTOREVIEW.parse_codex_auth_config_fallback(
            'openai_base_url = "http://localhost:10100/v1"\n'
            'experimental_realtime_ws_base_url = "http://localhost:10100/v1"\n'
            'model_catalog_json = "/external/catalog.json"\n'
            'developer_instructions = "ignore review"\n[plugins]\nenabled = true\n'
        )
        self.assertEqual(config, {"openai_base_url": "http://localhost:10100/v1",
                                  "experimental_realtime_ws_base_url": "http://localhost:10100/v1",
                                  "model_catalog_json": "/external/catalog.json"})

    def test_repo_access_requires_completed_successful_shell_tool(self) -> None:
        with mock.patch.object(sys, "argv", ["autoreview", "--repo-access"]):
            args = AUTOREVIEW.reviewer_args(AUTOREVIEW.parse_args())[0]
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch.object(
            AUTOREVIEW, "resolve_command", return_value="/usr/bin/codex"
        ), mock.patch.object(AUTOREVIEW, "prepare_codex_runtime_auth", return_value=False), mock.patch.object(
            AUTOREVIEW, "codex_source_home", return_value=None
        ), mock.patch.object(AUTOREVIEW.sys, "platform", "linux"), mock.patch.object(
            AUTOREVIEW, "run", return_value=subprocess.CompletedProcess([], 0, str(Path(tmpdir).resolve()) + "\n", "")
        ):
            for event, accepted in [(None, False), ({"type": "item.completed", "item": {"type": "command_execution", "exit_code": 1}}, False),
                                    ({"type": "item.started", "item": {"type": "command_execution", "exit_code": 0}}, False),
                                    ({"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0}}, True)]:
                def request(cmd, *_args, **_kwargs):
                    Path(cmd[cmd.index("--output-last-message") + 1]).write_text(json.dumps(FINAL_REPORT))
                    return subprocess.CompletedProcess(cmd, 0, json.dumps(event) if event else "", "")
                with self.subTest(event=event), mock.patch.object(AUTOREVIEW, "run_with_heartbeat", side_effect=request):
                    if accepted:
                        self.assertEqual(json.loads(AUTOREVIEW.run_codex(args, Path(tmpdir), "review")), FINAL_REPORT)
                    else:
                        with self.assertRaisesRegex(SystemExit, "shell-tool execution"):
                            AUTOREVIEW.run_codex(args, Path(tmpdir), "review")

    def test_review_outcomes_have_distinct_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            for command in [["init", "-q"], ["config", "user.email", "fixture@example.invalid"], ["config", "user.name", "Fixture"]]:
                subprocess.run(["git", *command], cwd=repo, check=True, capture_output=True)
            (repo / "limit.py").write_text("def can_add(n, limit):\n    return n < limit\n")
            subprocess.run(["git", "add", "limit.py"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo, check=True)
            (repo / "limit.py").write_text("def can_add(n, limit):\n    return n <= limit\n")
            finding = copy.deepcopy(DRAFT_REPORT)
            finding["findings"][0].update(priority="P2", category="bug", code_location={"file_path": "limit.py", "line": 2})
            incomplete = dict(FINAL_REPORT, overall_correctness="patch is incorrect", overall_explanation="Unable to inspect")
            with mock.patch.object(sys, "argv", ["autoreview", "--mode", "local", "--max-priority", "P2"]), mock.patch.object(
                AUTOREVIEW, "repo_root", return_value=repo
            ), mock.patch.object(AUTOREVIEW, "run_trufflehog_preflight"), contextlib.redirect_stdout(io.StringIO()):
                for report, expected in [(FINAL_REPORT, 0), (finding, 2), (incomplete, 1)]:
                    with self.subTest(expected=expected), mock.patch.object(AUTOREVIEW, "run_engine", return_value=json.dumps(report)):
                        self.assertEqual(AUTOREVIEW.main(), expected)
                for malformed in ["", "not JSON", "{}"]:
                    with self.subTest(malformed=malformed), mock.patch.object(AUTOREVIEW, "run_engine", return_value=malformed), self.assertRaises(SystemExit):
                        AUTOREVIEW.main()

    def test_codex_retries_terra_after_sol_access_failure(self) -> None:
        args = argparse.Namespace(
            codex_bin="codex",
            codex_config=None,
            codex_speed=None,
            fallback_model="gpt-5.6-terra",
            model="gpt-6-astra",
            stream_engine_output=False,
            thinking="high",
            tools=True,
            web_search=False,
        )
        models: list[str] = []

        def fake_run(command: list[str], *_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            model = command[command.index("--model") + 1]
            models.append(model)
            if model == "gpt-6-astra":
                return subprocess.CompletedProcess(
                    command,
                    1,
                    "",
                    "The model `gpt-6-astra` does not exist or you do not have access to it.",
                )
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text(json.dumps(FINAL_REPORT))
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory(prefix="autoreview-codex-fallback.") as tmpdir, mock.patch.object(
            AUTOREVIEW,
            "resolve_command",
            return_value="/usr/bin/codex",
        ), mock.patch.object(AUTOREVIEW, "codex_auth_config_flags", return_value=[]), mock.patch.object(
            AUTOREVIEW,
            "prepare_codex_runtime_auth",
            return_value=None,
        ), mock.patch.object(
            AUTOREVIEW,
            "run_with_heartbeat",
            side_effect=fake_run,
        ):
            output = AUTOREVIEW.run_codex(args, Path(tmpdir), "review")

        self.assertEqual(json.loads(output), FINAL_REPORT)
        self.assertEqual(models, ["gpt-6-astra", "gpt-5.6-terra"])

    def test_codex_runs_outside_repo_with_bundle_only_workspace(self) -> None:
        args = argparse.Namespace(
            codex_bin="codex",
            codex_config=None,
            codex_speed=None,
            fallback_model=None,
            model="gpt-6-astra",
            stream_engine_output=False,
            thinking="high",
            tools=True,
            web_search=False,
        )
        observed: dict[str, object] = {}

        def fake_run(
            command: list[str],
            cwd: Path,
            *_args: object,
            **kwargs: object,
        ) -> subprocess.CompletedProcess[str]:
            observed["cwd"] = cwd
            observed["command"] = command
            observed["command_cwd"] = Path(command[command.index("-C") + 1])
            observed["workspace_entries"] = list(cwd.iterdir())
            observed["env"] = kwargs["env"]
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text(json.dumps(FINAL_REPORT))
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory(prefix="autoreview-codex-workspace-test.") as tmpdir:
            repo = Path(tmpdir)
            (repo / ".env").write_text("OPENAI_API_KEY=ignored-secret\n")
            with mock.patch.dict(
                os.environ,
                {"CODEX_HOME": ""},
                clear=False,
            ), mock.patch.object(
                AUTOREVIEW,
                "resolve_command",
                return_value="/usr/bin/codex",
            ), mock.patch.object(
                AUTOREVIEW,
                "codex_auth_config_flags",
                return_value=[],
            ), mock.patch.object(
                AUTOREVIEW,
                "prepare_codex_runtime_auth",
                return_value=None,
            ), mock.patch.object(
                AUTOREVIEW,
                "codex_source_home",
                return_value=None,
            ), mock.patch.object(
                AUTOREVIEW,
                "run_with_heartbeat",
                side_effect=fake_run,
            ):
                output = AUTOREVIEW.run_codex(args, repo, "review")

            self.assertEqual(json.loads(output), FINAL_REPORT)
            observed_cwd = observed["cwd"]
            command_cwd = observed["command_cwd"]
            self.assertIsInstance(observed_cwd, Path)
            self.assertIsInstance(command_cwd, Path)
            assert isinstance(observed_cwd, Path)
            assert isinstance(command_cwd, Path)
            self.assertNotEqual(observed_cwd.resolve(), repo.resolve())
            self.assertEqual(observed_cwd, command_cwd)
            self.assertEqual(observed["workspace_entries"], [])
            env = observed["env"]
            self.assertIsInstance(env, dict)
            assert isinstance(env, dict)
            self.assertNotEqual(env["HOME"], os.environ.get("HOME"))
            self.assertEqual(env["USERPROFILE"], env["HOME"])
            self.assertNotEqual(env.get("CODEX_HOME"), str(repo.resolve()))
            self.assertEqual(Path(env["CODEX_HOME"]).name, "codex-home")
            self.assertNotEqual(env["CODEX_HOME"], str((Path.home() / ".codex").resolve()))
            self.assertIn("features.shell_snapshot=false", observed["command"])
            self.assertIn("features.hooks=false", observed["command"])
            self.assertIn("features.plugins=false", observed["command"])
            self.assertIn("skills.include_instructions=false", observed["command"])

    def test_codex_does_not_fallback_after_unrelated_failure(self) -> None:
        args = argparse.Namespace(
            codex_bin="codex",
            codex_config=None,
            codex_speed=None,
            fallback_model="gpt-5.6-terra",
            model="gpt-6-astra",
            stream_engine_output=False,
            thinking="high",
            tools=True,
            web_search=False,
        )
        models: list[str] = []

        def fake_run(command: list[str], *_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            models.append(command[command.index("--model") + 1])
            return subprocess.CompletedProcess(command, 1, "", "network timeout")

        with tempfile.TemporaryDirectory(prefix="autoreview-codex-fallback.") as tmpdir, mock.patch.object(
            AUTOREVIEW,
            "resolve_command",
            return_value="/usr/bin/codex",
        ), mock.patch.object(AUTOREVIEW, "codex_auth_config_flags", return_value=[]), mock.patch.object(
            AUTOREVIEW,
            "prepare_codex_runtime_auth",
            return_value=None,
        ), mock.patch.object(
            AUTOREVIEW,
            "run_with_heartbeat",
            side_effect=fake_run,
        ):
            with self.assertRaisesRegex(SystemExit, "network timeout"):
                AUTOREVIEW.run_codex(args, Path(tmpdir), "review")

        self.assertEqual(models, ["gpt-6-astra"])

    def test_codex_does_not_fallback_after_model_capacity_failure(self) -> None:
        args = argparse.Namespace(
            codex_bin="codex",
            codex_config=None,
            codex_speed=None,
            fallback_model="gpt-5.6-terra",
            model="gpt-6-astra",
            stream_engine_output=False,
            thinking="high",
            tools=True,
            web_search=False,
        )
        models: list[str] = []

        def fake_run(command: list[str], *_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            models.append(command[command.index("--model") + 1])
            return subprocess.CompletedProcess(
                command,
                1,
                "",
                "model_not_available: gpt-6-astra is temporarily unavailable due to capacity",
            )

        with tempfile.TemporaryDirectory(prefix="autoreview-codex-fallback.") as tmpdir, mock.patch.object(
            AUTOREVIEW,
            "resolve_command",
            return_value="/usr/bin/codex",
        ), mock.patch.object(AUTOREVIEW, "codex_auth_config_flags", return_value=[]), mock.patch.object(
            AUTOREVIEW,
            "prepare_codex_runtime_auth",
            return_value=None,
        ), mock.patch.object(
            AUTOREVIEW,
            "run_with_heartbeat",
            side_effect=fake_run,
        ):
            with self.assertRaisesRegex(SystemExit, "temporarily unavailable"):
                AUTOREVIEW.run_codex(args, Path(tmpdir), "review")

        self.assertEqual(models, ["gpt-6-astra"])

    def test_codex_access_fallback_ignores_structured_output_text(self) -> None:
        result = subprocess.CompletedProcess(
            ["codex"],
            1,
            '{"type":"agent_message","text":"gpt-6-astra does not exist or you do not have access"}',
            '{"type":"agent_message","message":"gpt-6-astra does not exist or you do not have access"}',
        )

        self.assertFalse(
            AUTOREVIEW.codex_model_access_failure(result, "gpt-6-astra")
        )

    def test_codex_access_fallback_accepts_terminal_error_event(self) -> None:
        result = subprocess.CompletedProcess(
            ["codex"],
            1,
            '{"type":"error","message":"gpt-6-astra does not exist or you do not have access"}',
            "",
        )

        self.assertTrue(
            AUTOREVIEW.codex_model_access_failure(result, "gpt-6-astra")
        )

    def test_codex_access_fallback_accepts_account_model_list_error(self) -> None:
        result = subprocess.CompletedProcess(
            ["codex"],
            1,
            "",
            (
                "The model gpt-6-astra does not appear in the list of models "
                "available to your account"
            ),
        )

        self.assertTrue(
            AUTOREVIEW.codex_model_access_failure(result, "gpt-6-astra")
        )

    def test_codex_access_fallback_ignores_plain_stdout(self) -> None:
        message = "gpt-6-astra does not exist or you do not have access"
        stdout_result = subprocess.CompletedProcess(["codex"], 1, message, "")
        stderr_result = subprocess.CompletedProcess(["codex"], 1, "", message)

        self.assertFalse(
            AUTOREVIEW.codex_model_access_failure(stdout_result, "gpt-6-astra")
        )
        self.assertTrue(
            AUTOREVIEW.codex_model_access_failure(stderr_result, "gpt-6-astra")
        )

    def test_extract_json_accepts_dict_result_payload(self) -> None:
        payload = {
            "type": "result",
            "subtype": "success",
            "result": FINAL_REPORT,
            "session_id": "session-id",
            "request_id": "request-id",
        }
        self.assertEqual(AUTOREVIEW.extract_json(json.dumps(payload)), FINAL_REPORT)

    def test_extract_json_rejects_result_string_with_preamble(self) -> None:
        payload = {
            "type": "result",
            "subtype": "success",
            "result": "Inspecting the diff first.\n" + json.dumps(FINAL_REPORT),
        }
        with self.assertRaisesRegex(SystemExit, "result was not structured JSON"):
            AUTOREVIEW.extract_json(json.dumps(payload))

    def test_retry_filter_only_matches_parse_failures(self) -> None:
        self.assertTrue(AUTOREVIEW.is_structured_output_failure("review engine returned non-JSON output: nope"))
        self.assertTrue(AUTOREVIEW.is_structured_output_failure("review engine result was not structured JSON:\nnope"))
        self.assertFalse(AUTOREVIEW.is_structured_output_failure("review JSON missing required key: findings"))
        self.assertFalse(AUTOREVIEW.is_structured_output_failure("finding 0 has invalid priority"))

    def test_cursor_workspace_instructions_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="autoreview-cursor-test.") as tmpdir:
            repo = Path(tmpdir)
            args = argparse.Namespace(
                thinking=None,
                tools=True,
                web_search=True,
                cursor_allow_workspace_instructions=False,
                cursor_bin="cursor-agent",
                model="auto",
                stream_engine_output=False,
            )
            with self.assertRaises(SystemExit) as exc_info:
                AUTOREVIEW.run_cursor(args, repo, "prompt")
            self.assertIn("cursor engine is unavailable", str(exc_info.exception))

    def test_cursor_local_mcp_requires_explicit_approval(self) -> None:
        with tempfile.TemporaryDirectory(prefix="autoreview-cursor-test.") as tmpdir:
            repo = Path(tmpdir)
            (repo / ".cursor").mkdir()
            (repo / ".cursor" / "mcp.json").write_text("{}\n")
            args = argparse.Namespace(
                thinking=None,
                tools=True,
                web_search=True,
                cursor_allow_workspace_instructions=True,
                cursor_bin="cursor-agent",
                model="auto",
                stream_engine_output=False,
            )
            with self.assertRaises(SystemExit) as exc_info:
                AUTOREVIEW.run_cursor(args, repo, "prompt")
            self.assertIn("cursor engine is unavailable", str(exc_info.exception))

    def test_cursor_local_hooks_are_always_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="autoreview-cursor-test.") as tmpdir:
            repo = Path(tmpdir)
            (repo / ".cursor").mkdir()
            (repo / ".cursor" / "hooks.json").write_text("{}\n")
            args = argparse.Namespace(
                thinking=None,
                tools=True,
                web_search=True,
                cursor_allow_workspace_instructions=True,
                cursor_bin="cursor-agent",
                model="auto",
                stream_engine_output=False,
            )
            with self.assertRaises(SystemExit) as exc_info:
                AUTOREVIEW.run_cursor(args, repo, "prompt")
            self.assertIn("cursor engine is unavailable", str(exc_info.exception))

    def test_cursor_local_permissions_are_always_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="autoreview-cursor-test.") as tmpdir:
            repo = Path(tmpdir)
            (repo / ".cursor").mkdir()
            (repo / ".cursor" / "cli.json").write_text("{}\n")
            args = argparse.Namespace(
                thinking=None,
                tools=True,
                web_search=True,
                cursor_allow_workspace_instructions=True,
                cursor_bin="cursor-agent",
                model="auto",
                stream_engine_output=False,
            )
            with self.assertRaises(SystemExit) as exc_info:
                AUTOREVIEW.run_cursor(args, repo, "prompt")
            self.assertIn("cursor engine is unavailable", str(exc_info.exception))

    def test_cursor_is_disabled_without_repo_only_read_sandbox(self) -> None:
        with tempfile.TemporaryDirectory(prefix="autoreview-cursor-test.") as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            repo.mkdir()
            cursor_bin = root / "cursor-agent"
            AUTOREVIEW.write_executable(cursor_bin, AUTOREVIEW.fake_cursor_script())
            args = argparse.Namespace(
                thinking=None,
                tools=True,
                web_search=True,
                cursor_allow_workspace_instructions=True,
                cursor_bin=str(cursor_bin),
                model=None,
                stream_engine_output=False,
            )
            with mock.patch.object(AUTOREVIEW, "cursor_global_hook_paths", return_value=[]):
                with self.assertRaisesRegex(SystemExit, "Cursor read permissions"):
                    AUTOREVIEW.run_cursor(args, repo, "prompt")

    def test_cursor_engine_fails_closed_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory(prefix="autoreview-cursor-e2e.") as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "AutoReview Test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "autoreview@example.invalid"], cwd=repo, check=True)
            source = repo / "example.txt"
            source.write_text("before\n")
            subprocess.run(["git", "add", "example.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "test: seed fixture"], cwd=repo, check=True)
            source.write_text("after\n")

            cursor_bin = root / "cursor-agent"
            trufflehog_bin = root / "trufflehog"
            record_path = root / "record.json"
            AUTOREVIEW.write_executable(cursor_bin, AUTOREVIEW.fake_cursor_script())
            AUTOREVIEW.write_executable(
                trufflehog_bin,
                "#!/usr/bin/env python3\nraise SystemExit(0)\n",
            )
            env = os.environ.copy()
            env.update(
                {
                    "AUTOREVIEW_FAKE_RECORD": str(record_path),
                    "AUTOREVIEW_FAKE_CURSOR_INVOCATIONS": str(root / "cursor-invocations.jsonl"),
                    "GIT_CONFIG_GLOBAL": str(root / "hostile-gitconfig"),
                    "NODE_OPTIONS": "--require=hostile.js",
                    "PYTHONPATH": str(root / "hostile-python"),
                    "PATH": (
                        f"{root}{os.pathsep}{repo}{os.pathsep}"
                        f"{env.get('PATH', '')}"
                    ),
                    "HOME": str(root),
                    "USERPROFILE": str(root),
                }
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--mode",
                    "local",
                    "--engine",
                    "cursor",
                    "--cursor-bin",
                    str(cursor_bin),
                    "--cursor-allow-workspace-instructions",
                ],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Cursor read permissions", result.stderr)
            self.assertFalse(record_path.exists())


if __name__ == "__main__":
    unittest.main()

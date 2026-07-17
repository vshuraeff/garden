from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any, TextIO


class HarnessSmokeTestCase(unittest.TestCase):
    cli_timeout = 120

    def setUp(self) -> None:
        self.claude = shutil.which("claude")
        self.codex = shutil.which("codex")
        self.repo_root = Path(__file__).resolve().parents[3]
        self.plugin_root = self.repo_root / "plugins" / "garden"

    def _temporary_directory(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name).resolve()

    def _minimal_env(self) -> dict[str, str]:
        path = os.environ.get("PATH")
        home = os.environ.get("HOME")
        if not path or not home:
            self.fail("PATH and HOME are required to construct an isolated CLI env")
        environment = {"PATH": path, "HOME": home}
        for name in ("LANG", "LC_ALL", "TERM"):
            value = os.environ.get(name)
            if value:
                environment[name] = value
        return environment

    def isolated_env(self, cli: str, config_dir: Path) -> dict[str, str]:
        environment = self._minimal_env()
        isolation_variable = {
            "claude": "CLAUDE_CONFIG_DIR",
            "codex": "CODEX_HOME",
        }[cli]
        environment[isolation_variable] = str(config_dir)
        return environment

    def run_cli(
        self,
        args: list[str],
        cwd: Path | None = None,
        input: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int = cli_timeout,
    ) -> tuple[int, str, str]:
        environment = self._minimal_env() if env is None else dict(env)
        executable = Path(args[0]).name
        if executable == "claude" and "CLAUDE_CONFIG_DIR" not in environment:
            self.fail("claude invocation is missing CLAUDE_CONFIG_DIR isolation")
        if executable == "codex" and "CODEX_HOME" not in environment:
            self.fail("codex invocation is missing CODEX_HOME isolation")
        completed = subprocess.run(
            args,
            cwd=cwd,
            input=input,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
            check=False,
        )
        return completed.returncode, completed.stdout, completed.stderr

    def _require_claude(self) -> str:
        if self.claude is None:
            self.skipTest("claude CLI is not available on PATH")
        return self.claude

    def _require_codex(self) -> str:
        if self.codex is None:
            self.skipTest("codex CLI is not available on PATH")
        return self.codex

    def _assert_success(
        self, result: tuple[int, str, str], description: str
    ) -> tuple[str, str]:
        returncode, stdout, stderr = result
        self.assertEqual(
            0,
            returncode,
            f"{description} failed\nstdout:\n{stdout}\nstderr:\n{stderr}",
        )
        return stdout, stderr

    def _json_output(self, stdout: str, description: str) -> object:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as error:
            self.fail(f"{description} returned invalid JSON: {error}\n{stdout}")

    def _plugin_entries(self, payload: object) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in (
                "plugins",
                "installedPlugins",
                "installed_plugins",
                "installed",
                "items",
            ):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            if any(key in payload for key in ("name", "pluginId", "plugin_id", "id")):
                return [payload]
        self.fail(f"plugin list has an unsupported JSON shape: {payload!r}")

    @staticmethod
    def _entry_name(entry: dict[str, Any]) -> str | None:
        for key in ("name", "pluginId", "plugin_id", "id"):
            value = entry.get(key)
            if isinstance(value, str):
                return value.split("@", maxsplit=1)[0]
        return None

    def _find_plugin(self, entries: list[dict[str, Any]], name: str) -> dict[str, Any]:
        for entry in entries:
            if self._entry_name(entry) == name:
                return entry
        self.fail(f"plugin {name!r} is absent from: {entries!r}")

    @staticmethod
    def _entry_version(entry: dict[str, Any]) -> str | None:
        for key in ("version", "pluginVersion", "plugin_version"):
            value = entry.get(key)
            if isinstance(value, str):
                return value
        return None

    def _version(self) -> str:
        manifest = json.loads(
            (self.plugin_root / ".claude-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        version = manifest.get("version")
        self.assertIsInstance(version, str)
        return version

    def _assert_package_surfaces(self, installed_root: Path) -> None:
        expected_references = {
            path.name for path in (self.plugin_root / "references").glob("*.md")
        }
        self.assertEqual(8, len(expected_references))
        actual_references = {
            path.name for path in (installed_root / "references").glob("*.md")
        }
        self.assertTrue(expected_references <= actual_references)

        for relative in (
            Path("rules/garden-rules.toml"),
            Path("hooks/hooks.json"),
            Path(".mcp.json"),
            Path("agents/garden-reviewer.md"),
        ):
            self.assertTrue(
                (installed_root / relative).is_file(),
                f"installed package is missing {relative}",
            )

        skill_names = {
            path.name
            for path in (self.plugin_root / "skills").iterdir()
            if path.is_dir()
        }
        self.assertTrue(skill_names)
        for skill_name in skill_names:
            relative = Path("skills") / skill_name / "SKILL.md"
            self.assertTrue(
                (installed_root / relative).is_file(),
                f"installed package is missing {relative}",
            )

    def _claude_install(
        self, config_dir: Path
    ) -> tuple[dict[str, str], list[dict[str, Any]]]:
        claude = self._require_claude()
        environment = self.isolated_env("claude", config_dir)
        self._assert_success(
            self.run_cli(
                [claude, "plugin", "marketplace", "add", str(self.repo_root)],
                cwd=config_dir,
                env=environment,
            ),
            "claude marketplace add",
        )
        self._assert_success(
            self.run_cli(
                [claude, "plugin", "install", "garden@garden"],
                cwd=config_dir,
                env=environment,
            ),
            "claude plugin install",
        )
        stdout, _ = self._assert_success(
            self.run_cli(
                [claude, "plugin", "list", "--json"],
                cwd=config_dir,
                env=environment,
            ),
            "claude plugin list",
        )
        payload = self._json_output(stdout, "claude plugin list")
        return environment, self._plugin_entries(payload)

    def _codex_install(
        self, config_dir: Path, *, check_marketplace: bool = False
    ) -> tuple[dict[str, str], list[dict[str, Any]]]:
        codex = self._require_codex()
        environment = self.isolated_env("codex", config_dir)
        add_stdout, add_stderr = self._assert_success(
            self.run_cli(
                [codex, "plugin", "marketplace", "add", str(self.repo_root)],
                cwd=config_dir,
                env=environment,
            ),
            "codex marketplace add",
        )
        if check_marketplace:
            returncode, stdout, stderr = self.run_cli(
                [codex, "plugin", "marketplace", "list"],
                cwd=config_dir,
                env=environment,
            )
            combined = stdout + stderr
            if returncode == 0:
                self.assertTrue(
                    "garden" in combined.lower() or str(self.repo_root) in combined,
                    f"codex marketplace list omitted garden:\n{combined}",
                )
            else:
                unavailable_tokens = (
                    "unrecognized subcommand",
                    "unknown subcommand",
                    "invalid subcommand",
                    "unexpected argument 'list'",
                )
                self.assertTrue(
                    any(token in combined.lower() for token in unavailable_tokens),
                    "codex marketplace list failed unexpectedly\n"
                    f"stdout:\n{stdout}\nstderr:\n{stderr}\n"
                    f"marketplace add stdout:\n{add_stdout}\n"
                    f"marketplace add stderr:\n{add_stderr}",
                )
        self._assert_success(
            self.run_cli(
                [codex, "plugin", "add", "garden@garden"],
                cwd=config_dir,
                env=environment,
            ),
            "codex plugin add",
        )
        stdout, _ = self._assert_success(
            self.run_cli(
                [codex, "plugin", "list", "--json"],
                cwd=config_dir,
                env=environment,
            ),
            "codex plugin list",
        )
        payload = self._json_output(stdout, "codex plugin list")
        return environment, self._plugin_entries(payload)

    def _installed_copy_path(self) -> Path:
        destination = self._temporary_directory() / "garden"
        shutil.copytree(self.plugin_root, destination)
        return destination

    def _runtime_env(self, **extra: str) -> dict[str, str]:
        environment = self._minimal_env()
        environment.update(extra)
        return environment

    @staticmethod
    def _send_json(stream: TextIO, message: object) -> None:
        stream.write(json.dumps(message, separators=(",", ":")) + "\n")
        stream.flush()

    def _read_json_line(
        self, process: subprocess.Popen[str], timeout: int = cli_timeout
    ) -> dict[str, Any]:
        if process.stdout is None:
            self.fail("MCP server stdout is unavailable")
        ready, _, _ = select.select([process.stdout], [], [], timeout)
        if not ready:
            self.fail("timed out waiting for an MCP server response")
        line = process.stdout.readline()
        if not line:
            stderr = ""
            if process.poll() is not None and process.stderr is not None:
                stderr = process.stderr.read()
            self.fail(f"MCP server closed stdout unexpectedly\nstderr:\n{stderr}")
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            self.fail(f"MCP server returned invalid JSON: {error}\n{line}")
        self.assertIsInstance(payload, dict)
        return payload


class ClaudeHarnessSmokeTests(HarnessSmokeTestCase):
    def test_claude_plugin_validate(self) -> None:
        claude = self._require_claude()
        config_dir = self._temporary_directory()
        environment = self.isolated_env("claude", config_dir)
        self._assert_success(
            self.run_cli(
                [claude, "plugin", "validate", str(self.plugin_root)],
                cwd=config_dir,
                env=environment,
            ),
            "claude plugin validate",
        )

    def test_claude_plugin_install_surfaces(self) -> None:
        config_dir = self._temporary_directory()
        _, entries = self._claude_install(config_dir)
        entry = self._find_plugin(entries, "garden")
        self.assertEqual(self._version(), self._entry_version(entry))

        install_path = entry.get("installPath")
        self.assertIsInstance(install_path, str)
        installed_root = Path(install_path).resolve()
        self.assertTrue(installed_root.is_relative_to(config_dir))
        self.assertNotEqual(self.plugin_root.resolve(), installed_root)
        self._assert_package_surfaces(installed_root)

    def test_claude_mcp_list_mentions_installed_garden(self) -> None:
        claude = self._require_claude()
        config_dir = self._temporary_directory()
        environment, _ = self._claude_install(config_dir)
        stdout, stderr = self._assert_success(
            self.run_cli([claude, "mcp", "list"], cwd=config_dir, env=environment),
            "claude mcp list",
        )
        combined = stdout + stderr
        self.assertIn("garden", combined.lower())
        self.assertTrue(
            any(
                token in combined.lower()
                for token in ("connected", "healthy", "running")
            )
        )

    def test_claude_plugin_uninstall_removes_garden(self) -> None:
        claude = self._require_claude()
        config_dir = self._temporary_directory()
        environment, _ = self._claude_install(config_dir)
        self._assert_success(
            self.run_cli(
                [claude, "plugin", "uninstall", "garden@garden"],
                cwd=config_dir,
                env=environment,
            ),
            "claude plugin uninstall",
        )
        stdout, _ = self._assert_success(
            self.run_cli(
                [claude, "plugin", "list", "--json"],
                cwd=config_dir,
                env=environment,
            ),
            "claude plugin list after uninstall",
        )
        entries = self._plugin_entries(
            self._json_output(stdout, "claude plugin list after uninstall")
        )
        self.assertFalse(
            any(self._entry_name(entry) == "garden" for entry in entries),
            entries,
        )


class CodexHarnessSmokeTests(HarnessSmokeTestCase):
    def test_codex_plugin_install_surfaces(self) -> None:
        config_dir = self._temporary_directory()
        _, entries = self._codex_install(config_dir, check_marketplace=True)
        entry = self._find_plugin(entries, "garden")
        version = self._version()
        self.assertEqual(version, self._entry_version(entry))

        installed_root = (
            config_dir / "plugins" / "cache" / "garden" / "garden" / version
        )
        self.assertTrue(installed_root.is_dir())
        self._assert_package_surfaces(installed_root)

    def test_codex_mcp_list_mentions_installed_garden(self) -> None:
        codex = self._require_codex()
        config_dir = self._temporary_directory()
        environment, _ = self._codex_install(config_dir)
        stdout, stderr = self._assert_success(
            self.run_cli([codex, "mcp", "list"], cwd=config_dir, env=environment),
            "codex mcp list",
        )
        self.assertIn("garden", (stdout + stderr).lower())

    def test_codex_plugin_remove_removes_garden(self) -> None:
        codex = self._require_codex()
        config_dir = self._temporary_directory()
        environment, _ = self._codex_install(config_dir)
        self._assert_success(
            self.run_cli(
                [codex, "plugin", "remove", "garden@garden"],
                cwd=config_dir,
                env=environment,
            ),
            "codex plugin remove",
        )
        stdout, _ = self._assert_success(
            self.run_cli(
                [codex, "plugin", "list", "--json"],
                cwd=config_dir,
                env=environment,
            ),
            "codex plugin list after remove",
        )
        entries = self._plugin_entries(
            self._json_output(stdout, "codex plugin list after remove")
        )
        self.assertFalse(
            any(self._entry_name(entry) == "garden" for entry in entries),
            entries,
        )


class InstalledPackageBehaviorSmokeTests(HarnessSmokeTestCase):
    def test_installed_hook_round_trip(self) -> None:
        installed_root = self._installed_copy_path()
        project = self._temporary_directory() / "project"
        source = project / "pkg" / "payload.py"
        contract = project / "orders" / "CONTRACT.md"
        source.parent.mkdir(parents=True)
        contract.parent.mkdir(parents=True)
        source.write_text("pass\n", encoding="utf-8")
        contract.write_text("bad\n", encoding="utf-8")
        (project / "naming-registry.txt").write_text(
            "orders: orders\n", encoding="utf-8"
        )
        environment = self._runtime_env(CLAUDE_PLUGIN_ROOT=str(installed_root))
        hook = installed_root / "hooks" / "garden-check.sh"

        source_event = {
            "cwd": str(project),
            "tool_input": {"file_path": str(source)},
        }
        source_result = self.run_cli(
            ["bash", str(hook)],
            cwd=project,
            input=json.dumps(source_event),
            env=environment,
        )
        self.assertEqual(0, source_result[0], source_result[2])

        contract_event = {
            "cwd": str(project),
            "tool_input": {"file_path": str(contract)},
        }
        contract_result = self.run_cli(
            ["bash", str(hook)],
            cwd=project,
            input=json.dumps(contract_event),
            env=environment,
        )
        self.assertEqual(2, contract_result[0], contract_result[2])
        self.assertIn("R-contract-version", contract_result[2])

    def test_installed_mcp_handshake(self) -> None:
        installed_root = self._installed_copy_path()
        mcp_config = json.loads(
            (installed_root / ".mcp.json").read_text(encoding="utf-8")
        )
        server = mcp_config["mcpServers"]["garden"]
        command = server["command"]
        arguments = server.get("args", [])
        self.assertIsInstance(command, str)
        self.assertIsInstance(arguments, list)
        self.assertTrue(all(isinstance(argument, str) for argument in arguments))

        process = subprocess.Popen(
            [command, *arguments],
            cwd=installed_root,
            env=self._runtime_env(PLUGIN_ROOT=str(installed_root)),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        try:
            if process.stdin is None:
                self.fail("MCP server stdin is unavailable")
            self._send_json(
                process.stdin,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"roots": {}},
                    },
                },
            )
            initialized = self._read_json_line(process)
            self.assertEqual(1, initialized.get("id"))
            self.assertEqual("garden", initialized["result"]["serverInfo"]["name"])

            self._send_json(
                process.stdin,
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
            )
            roots_request = self._read_json_line(process)
            self.assertEqual("roots/list", roots_request.get("method"))

            project = self._temporary_directory() / "active-project"
            project.mkdir()
            (project / ".garden.toml").write_text(
                "schema_version = 1\n[documentation]\nroot_context_required = false\n",
                encoding="utf-8",
            )
            self._send_json(
                process.stdin,
                {
                    "jsonrpc": "2.0",
                    "id": roots_request["id"],
                    "result": {"roots": [{"uri": project.as_uri()}]},
                },
            )

            self._send_json(
                process.stdin,
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            )
            tools_response = self._read_json_line(process)
            tool_names = {tool["name"] for tool in tools_response["result"]["tools"]}
            self.assertTrue(
                {"garden_inspect_project", "garden_check_file"} <= tool_names
            )

            self._send_json(
                process.stdin,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "garden_inspect_project",
                        "arguments": {"root": str(project)},
                    },
                },
            )
            call_response = self._read_json_line(process)
            result = call_response["result"]
            self.assertNotIn("isError", result)
            content = result["content"]
            self.assertEqual("text", content[0]["type"])
            report = json.loads(content[0]["text"])
            self.assertEqual(2, report["schema_version"])
            self.assertIs(report["active"], True)
        finally:
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            for stream in (process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()

    def test_installed_project_surface_round_trip(self) -> None:
        installed_root = self._installed_copy_path()
        project = self._temporary_directory() / "project"
        project.mkdir()
        agents = project / "AGENTS.md"
        original = "# My Project\n\nSome existing docs.\n"
        agents.write_text(original, encoding="utf-8")
        uv = shutil.which("uv")
        if uv is None:
            self.fail("uv is required for installed-package behavioral tests")
        tool = installed_root / "tools" / "garden_project.py"
        environment = self._runtime_env()

        self._assert_success(
            self.run_cli(
                [
                    uv,
                    "run",
                    "--no-project",
                    str(tool),
                    "install",
                    "--root",
                    str(project),
                    "--harness",
                    "both",
                ],
                cwd=project,
                env=environment,
            ),
            "garden project install",
        )
        self.assertTrue((project / ".claude/rules/garden.md").is_file())
        self.assertTrue((project / ".codex/agents/garden-reviewer.toml").is_file())
        installed_agents = agents.read_text(encoding="utf-8")
        self.assertIn("# My Project", installed_agents)
        self.assertIn("Some existing docs.", installed_agents)
        self.assertIn("<!-- garden:managed-instructions:v1 sha256=", installed_agents)
        self.assertIn("<!-- /garden:managed-instructions:v1 -->", installed_agents)

        self._assert_success(
            self.run_cli(
                [
                    uv,
                    "run",
                    "--no-project",
                    str(tool),
                    "remove",
                    "--root",
                    str(project),
                    "--harness",
                    "both",
                ],
                cwd=project,
                env=environment,
            ),
            "garden project remove",
        )
        self.assertFalse((project / ".claude/rules/garden.md").exists())
        self.assertFalse((project / ".codex/agents/garden-reviewer.toml").exists())
        self.assertEqual(original, agents.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from garden_mcp import (  # noqa: E402
    ROOTS_REQUEST_ID,
    SUPPORTED_PROTOCOL_VERSIONS,
    GardenServer,
)
import garden_scanner  # noqa: E402
from plugin_version import current_version  # noqa: E402
from test_garden_core import ActiveProjectTestCase  # noqa: E402


class GardenMcpTests(ActiveProjectTestCase):
    def initialized_server(self) -> GardenServer:
        server = GardenServer()
        initialize = server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": SUPPORTED_PROTOCOL_VERSIONS[0],
                    "capabilities": {"roots": {"listChanged": False}},
                },
            }
        )
        server_info = initialize[0]["result"]["serverInfo"]
        self.assertEqual("garden", server_info["name"])
        self.assertEqual(str(current_version()), server_info["version"])
        root_request = server.handle(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        self.assertEqual(ROOTS_REQUEST_ID, root_request[0]["id"])
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": ROOTS_REQUEST_ID,
                "result": {"roots": [{"uri": self.root.as_uri()}]},
            }
        )
        return server

    def call_tool(
        self,
        server: GardenServer,
        name: str,
        arguments: dict[str, object],
        request_id: int,
    ) -> tuple[dict[str, object], object]:
        response = server.handle(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        result = response[0]["result"]
        self.assertIsInstance(result, dict)
        content = result["content"]
        self.assertIsInstance(content, list)
        self.assertEqual("text", content[0]["type"])
        self.assertIsInstance(content[0]["text"], str)
        return result, json.loads(content[0]["text"])

    def test_inspect_project_returns_report_v2_schema(self) -> None:
        result, body = self.call_tool(
            self.initialized_server(),
            "garden_inspect_project",
            {"root": str(self.root)},
            request_id=2,
        )
        self.assertNotIn("isError", result)
        self.assertIsInstance(body, dict)
        self.assertEqual(2, body["schema_version"])
        self.assertEqual("deterministic-structural-inspection", body["scope"])
        self.assertIsInstance(body["active"], bool)
        self.assertIsInstance(body["complete"], bool)

        summary = body["summary"]
        self.assertIsInstance(summary, dict)
        self.assertEqual(
            {"errors", "warnings", "advisories", "unknown", "suppressed"},
            set(summary),
        )
        for counter in summary.values():
            self.assertIsInstance(counter, int)

        coverage = body["coverage"]
        self.assertIsInstance(coverage, dict)
        for key in (
            "implemented_rules",
            "manual_rules",
            "planned_rules",
            "not_applicable_rules",
        ):
            self.assertIn(key, coverage)
            self.assertIsInstance(coverage[key], list)

        configuration = body["configuration"]
        self.assertIsInstance(configuration, dict)
        self.assertEqual({"path", "schema_version", "valid"}, set(configuration))
        self.assertIsInstance(body["findings"], list)
        self.assertIsInstance(body["exceptions"], list)

    def test_check_file_retains_v2_finding_fields(self) -> None:
        contract = self.root / "orders" / "CONTRACT.md"
        contract.parent.mkdir()
        contract.write_text("# Missing version\n", encoding="utf-8")

        result, body = self.call_tool(
            self.initialized_server(),
            "garden_check_file",
            {"root": str(self.root), "path": str(contract)},
            request_id=3,
        )
        self.assertNotIn("isError", result)
        self.assertIsInstance(body, dict)
        self.assertIsInstance(body["path"], str)
        self.assertIsInstance(body["findings"], list)
        self.assertTrue(body["findings"])
        for finding in body["findings"]:
            self.assertIsInstance(finding, dict)
            self.assertEqual("R-REPL-002", finding["rule_id"])
            self.assertEqual("R-contract-version", finding["rule"])
            self.assertIsInstance(finding["rule_id"], str)
            self.assertIsInstance(finding["rule"], str)
            for key in (
                "runtime_alias",
                "level",
                "severity",
                "state",
                "path",
                "message",
                "evidence",
                "remediation",
                "confidence",
            ):
                self.assertIn(key, finding)
            self.assertIsInstance(finding["evidence"], list)

    def test_check_file_builds_one_project_index(self) -> None:
        (self.root / ".garden.toml").write_text(
            "schema_version = 1\n"
            '[scan]\nroots = ["src"]\ninclude = ["**/*.py"]\n'
            "[capabilities]\n"
            'strategy = "children"\nroots = ["src"]\ndepth = 1\n'
            "[documentation]\nroot_context_required = false\n",
            encoding="utf-8",
        )
        capability = self.root / "src" / "orders"
        capability.mkdir(parents=True)
        source = capability / "handler.py"
        source.write_text("pass\n", encoding="utf-8")
        (capability / "CONTRACT.md").write_text("Version: 1.0.0\n", encoding="utf-8")

        with patch.object(
            garden_scanner,
            "_walk_files",
            wraps=garden_scanner._walk_files,
        ) as walk:
            result, _ = self.call_tool(
                self.initialized_server(),
                "garden_check_file",
                {"root": str(self.root), "path": str(source)},
                request_id=6,
            )

        self.assertNotIn("isError", result)
        self.assertEqual(1, walk.call_count)

    def test_legacy_check_file_does_not_build_project_index(self) -> None:
        registry = self.root / "naming-registry.txt"

        with patch.object(
            garden_scanner,
            "_walk_files",
            side_effect=garden_scanner.ScanLimitExceeded(
                "forced legacy project limit", budget="entries"
            ),
        ) as walk:
            result, _ = self.call_tool(
                self.initialized_server(),
                "garden_check_file",
                {"root": str(self.root), "path": str(registry)},
                request_id=7,
            )

        self.assertNotIn("isError", result)
        walk.assert_not_called()

    def test_unregistered_root_is_a_tool_error(self) -> None:
        result, _ = self.call_tool(
            self.initialized_server(),
            "garden_inspect_project",
            {"root": "/"},
            request_id=4,
        )
        self.assertIs(result["isError"], True)

    def test_domain_findings_are_structured_content(self) -> None:
        contract = self.root / "orders" / "CONTRACT.md"
        contract.parent.mkdir()
        contract.write_text("# Missing version\n", encoding="utf-8")

        result, body = self.call_tool(
            self.initialized_server(),
            "garden_inspect_project",
            {"root": str(self.root)},
            request_id=5,
        )
        self.assertNotIn("isError", result)
        self.assertIsInstance(body, dict)
        self.assertTrue(body["active"])
        self.assertGreater(body["summary"]["errors"], 0)

    def test_unregistered_root_and_escape_are_rejected(self) -> None:
        server = self.initialized_server()
        for arguments in (
            {"root": "/", "path": "/etc/passwd"},
            {"root": str(self.root), "path": "../../etc/passwd"},
        ):
            response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "garden_check_file", "arguments": arguments},
                }
            )
            self.assertTrue(response[0]["result"]["isError"])

    def test_unknown_method_and_invalid_arguments_return_errors(self) -> None:
        server = self.initialized_server()
        unknown = server.handle({"jsonrpc": "2.0", "id": 4, "method": "unknown"})
        self.assertEqual(-32601, unknown[0]["error"]["code"])
        invalid = server.handle(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "garden_check_file", "arguments": []},
            }
        )
        self.assertTrue(invalid[0]["result"]["isError"])

    def test_process_reports_parse_and_invalid_request_errors(self) -> None:
        completed = subprocess.run(
            ["uv", "run", "--no-project", str(TOOLS_DIR / "garden_mcp.py")],
            input=b"not-json\n[]\n",
            capture_output=True,
            check=True,
        )
        responses = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(
            [-32700, -32600], [item["error"]["code"] for item in responses]
        )


if __name__ == "__main__":
    unittest.main()

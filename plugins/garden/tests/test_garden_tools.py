from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "tools"))

from garden_core import inspect_file, inspect_project, route_prompt  # noqa: E402
from garden_hook import affected_paths  # noqa: E402


class GardenCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "naming-registry.txt").write_text(
            "orders: orders\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_contract_version_is_an_error(self) -> None:
        contract = self.root / "orders" / "CONTRACT.md"
        contract.parent.mkdir()
        contract.write_text("# Missing version\n", encoding="utf-8")

        findings = inspect_file(contract)

        self.assertEqual(["R-contract-version"], [finding.rule for finding in findings])

    def test_project_inspection_reports_missing_contract_and_tests(self) -> None:
        source = self.root / "orders" / "handler.py"
        source.parent.mkdir()
        source.write_text("pass\n", encoding="utf-8")

        report = inspect_project(self.root)

        self.assertTrue(report["active"])
        self.assertEqual(2, report["summary"]["advisories"])

    def test_prompt_routing_requires_active_project(self) -> None:
        self.assertEqual(
            ["garden:audit"], route_prompt("audit this project", self.root)
        )

    def test_codex_apply_patch_paths_are_resolved_from_event_cwd(self) -> None:
        event = {
            "cwd": str(self.root),
            "tool_input": {
                "command": "*** Begin Patch\n*** Update File: orders/handler.py\n*** End Patch"
            },
        }

        self.assertEqual(
            [(self.root / "orders" / "handler.py").resolve()], affected_paths(event)
        )


class GardenMcpTests(unittest.TestCase):
    def test_mcp_initialize_and_tool_list(self) -> None:
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ]
        completed = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "tools" / "garden_mcp.py")],
            input="".join(json.dumps(request) + "\n" for request in requests),
            text=True,
            capture_output=True,
            check=True,
        )
        responses = [json.loads(line) for line in completed.stdout.splitlines()]

        self.assertEqual("garden", responses[0]["result"]["serverInfo"]["name"])
        self.assertEqual(2, len(responses[1]["result"]["tools"]))


if __name__ == "__main__":
    unittest.main()

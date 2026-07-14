from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from garden_mcp import (  # noqa: E402
    ROOTS_REQUEST_ID,
    SUPPORTED_PROTOCOL_VERSIONS,
    GardenServer,
)
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

    def test_registered_root_allows_project_inspection(self) -> None:
        server = self.initialized_server()
        response = server.handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "garden_inspect_project",
                    "arguments": {"root": str(self.root)},
                },
            }
        )
        self.assertNotIn("isError", response[0]["result"])

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

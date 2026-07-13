#!/usr/bin/env -S uv run --no-project
"""Dependency-free stdio MCP server for confined GARDEN inspection tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from garden_core import find_project_root, inspect_file, inspect_project, is_within


MAX_MCP_MESSAGE_BYTES = 1_048_576
MAX_REGISTERED_ROOTS = 32
ROOTS_REQUEST_ID = "garden-roots-1"
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
TOOLS = [
    {
        "name": "garden_inspect_project",
        "description": "Inspect deterministic GARDEN structure rules inside a client-registered workspace root.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {
                    "type": "string",
                    "description": "A workspace root previously registered by the MCP client.",
                }
            },
            "required": ["root"],
            "additionalProperties": False,
        },
    },
    {
        "name": "garden_check_file",
        "description": "Check one file confined to a client-registered GARDEN workspace root.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {
                    "type": "string",
                    "description": "A workspace root previously registered by the MCP client.",
                },
                "path": {
                    "type": "string",
                    "description": "Absolute path or path relative to root.",
                },
            },
            "required": ["root", "path"],
            "additionalProperties": False,
        },
    },
]


def result_text(value: object, *, is_error: bool = False) -> dict[str, object]:
    text = json.dumps(value, ensure_ascii=False, indent=2)
    result: dict[str, object] = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return result


def jsonrpc_error(request_id: object, code: int, message: str) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _file_uri_path(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        return None
    return Path(unquote(parsed.path)).resolve()


class GardenServer:
    def __init__(self) -> None:
        self.client_supports_roots = False
        self.roots: tuple[Path, ...] = ()

    def _select_root(self, value: object) -> Path | None:
        if not isinstance(value, str):
            return None
        candidate = Path(value).resolve()
        return next((root for root in self.roots if candidate == root), None)

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, object]:
        root = self._select_root(arguments.get("root"))
        if root is None:
            return result_text(
                {"error": "root is not registered by the MCP client"}, is_error=True
            )
        if find_project_root(root) != root:
            return result_text(
                {"error": "registered root is not an active GARDEN project"},
                is_error=True,
            )

        if name == "garden_inspect_project":
            return result_text(inspect_project(root))

        if name == "garden_check_file":
            value = arguments.get("path")
            if not isinstance(value, str):
                return result_text({"error": "path must be a string"}, is_error=True)
            candidate = Path(value)
            path = candidate if candidate.is_absolute() else root / candidate
            path = path.resolve()
            if not is_within(path, root):
                return result_text(
                    {"error": "path escapes the registered workspace root"},
                    is_error=True,
                )
            findings = [finding.__dict__ for finding in inspect_file(path, root)]
            return result_text({"path": str(path), "findings": findings})

        return result_text({"error": f"unknown tool: {name}"}, is_error=True)

    def handle(self, message: dict[str, Any]) -> list[dict[str, object]]:
        if message.get("id") == ROOTS_REQUEST_ID and "method" not in message:
            result = message.get("result")
            roots = result.get("roots") if isinstance(result, dict) else None
            registered: list[Path] = []
            if isinstance(roots, list):
                for item in roots[:MAX_REGISTERED_ROOTS]:
                    uri = item.get("uri") if isinstance(item, dict) else None
                    path = _file_uri_path(uri) if isinstance(uri, str) else None
                    if path is not None and path.is_dir():
                        registered.append(path)
            self.roots = tuple(dict.fromkeys(registered))
            return []

        method = message.get("method")
        has_id = "id" in message
        request_id = message.get("id")

        if method == "notifications/initialized":
            if self.client_supports_roots:
                return [
                    {
                        "jsonrpc": "2.0",
                        "id": ROOTS_REQUEST_ID,
                        "method": "roots/list",
                        "params": {},
                    }
                ]
            return []
        if not isinstance(method, str):
            return [jsonrpc_error(request_id, -32600, "Invalid Request")]
        if not has_id:
            return []

        if method == "initialize":
            params = message.get("params")
            capabilities = (
                params.get("capabilities") if isinstance(params, dict) else None
            )
            self.client_supports_roots = isinstance(capabilities, dict) and isinstance(
                capabilities.get("roots"), dict
            )
            requested = (
                params.get("protocolVersion") if isinstance(params, dict) else None
            )
            selected = (
                requested
                if requested in SUPPORTED_PROTOCOL_VERSIONS
                else SUPPORTED_PROTOCOL_VERSIONS[0]
            )
            result: object = {
                "protocolVersion": selected,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "garden", "version": "0.2.0"},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = message.get("params")
            if not isinstance(params, dict) or not isinstance(params.get("name"), str):
                result = result_text(
                    {"error": "tools/call requires params.name"}, is_error=True
                )
            else:
                arguments = params.get("arguments", {})
                result = (
                    self._call_tool(params["name"], arguments)
                    if isinstance(arguments, dict)
                    else result_text(
                        {"error": "params.arguments must be an object"},
                        is_error=True,
                    )
                )
        elif method == "ping":
            result = {}
        else:
            return [jsonrpc_error(request_id, -32601, f"Method not found: {method}")]

        return [{"jsonrpc": "2.0", "id": request_id, "result": result}]


def _read_message() -> bytes | None:
    line = sys.stdin.buffer.readline(MAX_MCP_MESSAGE_BYTES + 1)
    if not line:
        return None
    if len(line) <= MAX_MCP_MESSAGE_BYTES and line.endswith(b"\n"):
        return line
    if len(line) <= MAX_MCP_MESSAGE_BYTES:
        return line

    while line and not line.endswith(b"\n"):
        line = sys.stdin.buffer.readline(MAX_MCP_MESSAGE_BYTES + 1)
    raise ValueError("MCP message exceeds size limit")


def _send(message: dict[str, object]) -> bool:
    try:
        print(json.dumps(message, separators=(",", ":")), flush=True)
    except BrokenPipeError:
        return False
    return True


def main() -> int:
    server = GardenServer()
    while True:
        try:
            line = _read_message()
            if line is None:
                return 0
            message = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            if not _send(jsonrpc_error(None, -32700, "Parse error")):
                return 0
            continue
        if not isinstance(message, dict):
            responses = [jsonrpc_error(None, -32600, "Invalid Request")]
        else:
            try:
                responses = server.handle(message)
            except Exception:
                responses = [jsonrpc_error(message.get("id"), -32603, "Internal error")]
        for response in responses:
            if not _send(response):
                return 0


if __name__ == "__main__":
    raise SystemExit(main())

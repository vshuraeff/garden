#!/usr/bin/env python3
"""Dependency-free stdio MCP server for deterministic GARDEN inspection tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from garden_core import inspect_file, inspect_project


TOOLS = [
    {
        "name": "garden_inspect_project",
        "description": "Inspect deterministic GARDEN structure rules in a project without changing files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {
                    "type": "string",
                    "description": "Absolute path to the project to inspect.",
                }
            },
            "required": ["root"],
            "additionalProperties": False,
        },
    },
    {
        "name": "garden_check_file",
        "description": "Check the deterministic GARDEN rules affected by one file without changing it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or working-directory-relative file path.",
                }
            },
            "required": ["path"],
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


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, object]:
    if name == "garden_inspect_project":
        root = arguments.get("root")
        if not isinstance(root, str):
            return result_text({"error": "root must be a string"}, is_error=True)
        return result_text(inspect_project(Path(root)))

    if name == "garden_check_file":
        path = arguments.get("path")
        if not isinstance(path, str):
            return result_text({"error": "path must be a string"}, is_error=True)
        findings = [finding.__dict__ for finding in inspect_file(Path(path))]
        return result_text({"path": str(Path(path).resolve()), "findings": findings})

    return result_text({"error": f"unknown tool: {name}"}, is_error=True)


def handle(request: dict[str, Any]) -> dict[str, object] | None:
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None:
        return None

    if method == "initialize":
        params = request.get("params")
        requested_version = (
            params.get("protocolVersion") if isinstance(params, dict) else None
        )
        result: object = {
            "protocolVersion": requested_version
            if isinstance(requested_version, str)
            else "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "garden", "version": "0.2.0"},
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params")
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            result = result_text(
                {"error": "tools/call requires params.name"}, is_error=True
            )
        else:
            arguments = params.get("arguments", {})
            if not isinstance(arguments, dict):
                result = result_text(
                    {"error": "params.arguments must be an object"}, is_error=True
                )
            else:
                result = call_tool(params["name"], arguments)
    elif method == "ping":
        result = {}
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main() -> int:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                continue
            response = handle(request)
            if response is not None:
                print(json.dumps(response, separators=(",", ":")), flush=True)
        except json.JSONDecodeError:
            continue
        except Exception as exc:  # Keep the server alive and return a JSON-RPC error.
            request_id = request.get("id") if isinstance(request, dict) else None
            if request_id is not None:
                print(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {"code": -32603, "message": str(exc)},
                        },
                        separators=(",", ":"),
                    ),
                    flush=True,
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

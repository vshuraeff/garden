#!/usr/bin/env python3
"""PostToolUse adapter for Claude Code Write/Edit and Codex apply_patch events."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from garden_core import inspect_file


PATCH_PATH = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


def affected_paths(event: dict[str, object]) -> list[Path]:
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return []

    cwd_value = event.get("cwd")
    cwd = Path(cwd_value) if isinstance(cwd_value, str) else Path.cwd()
    paths: list[Path] = []

    file_path = tool_input.get("file_path")
    if isinstance(file_path, str):
        paths.append(Path(file_path))

    command = tool_input.get("command")
    if isinstance(command, str):
        for match in PATCH_PATH.findall(command):
            candidate = Path(match.strip())
            paths.append(candidate if candidate.is_absolute() else cwd / candidate)

    return list(dict.fromkeys(path.resolve() for path in paths))


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    findings = [
        finding for path in affected_paths(event) for finding in inspect_file(path)
    ]
    errors = [finding for finding in findings if finding.severity == "error"]
    if errors:
        for finding in errors:
            print(
                f"garden: {finding.path}: {finding.message} ({finding.rule})",
                file=sys.stderr,
            )
        return 2

    advisories = [finding for finding in findings if finding.severity == "advisory"]
    if advisories:
        message = "; ".join(
            f"{finding.path}: {finding.message}" for finding in advisories
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": f"garden: {message}",
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

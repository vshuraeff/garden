#!/usr/bin/env -S uv run --no-project
"""Fail-open PostToolUse adapter for Claude Write/Edit and Codex apply_patch."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from garden_core import find_project_root, inspect_file, is_within


MAX_HOOK_INPUT_BYTES = 1_048_576
MAX_PATCH_PATHS = 100
PATCH_PATH = re.compile(
    r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)$", re.MULTILINE
)


def read_event() -> dict[str, object] | None:
    data = sys.stdin.buffer.read(MAX_HOOK_INPUT_BYTES + 1)
    if len(data) > MAX_HOOK_INPUT_BYTES:
        return None
    event = json.loads(data)
    return event if isinstance(event, dict) else None


def affected_paths(event: dict[str, object]) -> list[Path]:
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return []

    cwd_value = event.get("cwd")
    cwd = Path(cwd_value) if isinstance(cwd_value, str) else Path.cwd()
    paths: list[Path] = []

    file_path = tool_input.get("file_path")
    if isinstance(file_path, str):
        candidate = Path(file_path)
        paths.append(candidate if candidate.is_absolute() else cwd / candidate)

    command = tool_input.get("command")
    if isinstance(command, str):
        for match in PATCH_PATH.finditer(command):
            if len(paths) >= MAX_PATCH_PATHS:
                break
            candidate = Path(match.group(1).strip())
            paths.append(candidate if candidate.is_absolute() else cwd / candidate)

    return list(dict.fromkeys(path.resolve() for path in paths[:MAX_PATCH_PATHS]))


def main() -> int:
    try:
        event = read_event()
        if event is None:
            return 0

        cwd_value = event.get("cwd")
        if not isinstance(cwd_value, str):
            return 0
        project_root = find_project_root(Path(cwd_value))
        if project_root is None:
            return 0

        test_cache: dict[Path | str, bool | None] = {}
        findings = [
            finding
            for path in affected_paths(event)
            if is_within(path, project_root)
            for finding in inspect_file(path, project_root, test_cache)
        ]
        errors = list(
            dict.fromkeys(item.rule for item in findings if item.severity == "error")
        )
        if errors:
            print(
                "garden: deterministic checks failed: "
                + ", ".join(errors)
                + "; run garden check-file for details",
                file=sys.stderr,
            )
            return 2

        advisories = list(
            dict.fromkeys(item.rule for item in findings if item.severity == "advisory")
        )
        if advisories:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PostToolUse",
                            "additionalContext": (
                                f"garden: {len(advisories)} advisory rule(s) triggered: "
                                + ", ".join(advisories)
                                + ". Use garden_check_file for evidence."
                            ),
                        }
                    }
                )
            )
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

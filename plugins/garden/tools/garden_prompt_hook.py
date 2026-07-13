#!/usr/bin/env -S uv run --no-project
"""Fail-open UserPromptSubmit adapter shared by Claude Code and Codex."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from garden_core import route_prompt


MAX_HOOK_INPUT_BYTES = 1_048_576


def main() -> int:
    try:
        data = sys.stdin.buffer.read(MAX_HOOK_INPUT_BYTES + 1)
        if len(data) > MAX_HOOK_INPUT_BYTES:
            return 0
        event = json.loads(data)
        if not isinstance(event, dict):
            return 0

        prompt = event.get("prompt")
        cwd = event.get("cwd")
        if not isinstance(prompt, str) or not isinstance(cwd, str):
            return 0

        skills = route_prompt(prompt, Path(cwd))
        if not skills:
            return 0

        message = (
            "garden: naming-registry.txt marks this as a GARDEN project; use "
            + " or ".join(skills)
            + ". Deterministic gates decide merges; never self-certify."
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": message,
                    }
                }
            )
        )
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

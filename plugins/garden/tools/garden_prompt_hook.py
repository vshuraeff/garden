#!/usr/bin/env python3
"""UserPromptSubmit adapter shared by Claude Code and Codex."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from garden_core import route_prompt


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
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


if __name__ == "__main__":
    raise SystemExit(main())

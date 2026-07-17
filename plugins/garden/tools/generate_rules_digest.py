#!/usr/bin/env -S uv run --no-project
"""Render the generated GARDEN rules digest from the canonical registry."""

from __future__ import annotations

import argparse
import os
import stat
import sys
import tempfile
from pathlib import Path

from garden_registry import RegistryError, load_registry


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_SOURCE = Path("plugins/garden/rules/garden-rules.toml")
DIGEST_PATH = PLUGIN_ROOT / "assets" / "garden-rules.md"
PRINCIPLE_ORDER = ("G", "A", "R", "D", "E", "N")
GENERATED_HEADER = (
    f"<!-- Generated from {REGISTRY_SOURCE.as_posix()}. "
    "Do not edit directly. Run generate_rules_digest.py --write to update. -->"
)
PREAMBLE_LINES = (
    "# GARDEN project rules",
    "",
    "Use `REQUIRED` for rules whose violation creates a demonstrable correctness,",
    "compatibility, or security risk. Use `DEFAULT` for configurable recommendations",
    "with a documented reason. Use `EXPERIMENTAL` only for measured hypotheses. Cite",
    "the stable rule ID in reviews, exceptions, and risk records.",
    "",
)
CLOSING_LINES = (
    "Record DEFAULT overrides and deferred EXPERIMENTAL measurements with the rule",
    "ID, owner, reason, evidence, and review trigger. Record a missing REQUIRED check",
    "as residual risk under `D-VER-004`, never as a pass.",
)


def render() -> str:
    """Render the rules digest from the canonical registry."""

    registry = load_registry()
    lines = [GENERATED_HEADER, *PREAMBLE_LINES]
    for letter in PRINCIPLE_ORDER:
        principle = registry.principle(letter)
        if principle is None:
            raise RegistryError(f"registry lacks principle metadata for {letter}")
        lines.extend((f"## {letter} — {principle.name}", ""))
        rules = sorted(
            (
                rule
                for rule in registry.rules
                if rule.principle == letter and rule.level != "EXPERIMENTAL"
            ),
            key=lambda rule: rule.id,
        )
        for rule in rules:
            if rule.digest is None:
                raise RegistryError(f"registry rule {rule.id} lacks a digest")
            lines.append(f"- `{rule.id} [{rule.level}]` {rule.digest}")
        lines.extend(f"- {note}" for note in principle.digest_notes)
        lines.append("")
    lines.extend(CLOSING_LINES)
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, content: str) -> None:
    original_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if original_mode is not None:
            os.chmod(temporary, original_mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="generate_rules_digest.py")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args(arguments)

    content = render()
    if args.write:
        _atomic_write(DIGEST_PATH, content)
        print("rules digest updated")
        return 0

    try:
        current = DIGEST_PATH.read_bytes()
    except OSError:
        current = None
    if current != content.encode("utf-8"):
        sys.stderr.write(f"{DIGEST_PATH}\n")
        return 1
    print("rules digest is in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

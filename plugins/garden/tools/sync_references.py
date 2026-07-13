#!/usr/bin/env -S uv run --no-project
"""Render canonical documentation into the GARDEN plugin references."""

from __future__ import annotations

import argparse
import os
import stat
import sys
import tempfile
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PLUGIN_ROOT.parent.parent
REFERENCE_PAIRS = {
    REPOSITORY_ROOT / "docs" / "reference" / "principles.md": PLUGIN_ROOT
    / "references"
    / "principles.md",
    REPOSITORY_ROOT / "docs" / "reference" / "checklist.md": PLUGIN_ROOT
    / "references"
    / "checklist.md",
    REPOSITORY_ROOT / "docs" / "reference" / "glossary.md": PLUGIN_ROOT
    / "references"
    / "glossary.md",
    REPOSITORY_ROOT / "docs" / "how-to" / "review-code-as-agent.md": PLUGIN_ROOT
    / "references"
    / "review-procedure.md",
}


def render(source_path: Path) -> str:
    with source_path.open(encoding="utf-8", newline="") as source:
        content = source.read()
    header = (
        "<!-- Generated from "
        f"{source_path.relative_to(REPOSITORY_ROOT).as_posix()}. "
        "Do not edit directly. Run sync_references.py --write to update. -->\n"
    )
    lines = content.splitlines(keepends=True)
    if lines and lines[0].rstrip("\r\n") == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line.rstrip("\r\n") == "---":
                return (
                    "".join(lines[: index + 1]) + header + "".join(lines[index + 1 :])
                )
    return header + content


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


def reference_drift() -> list[Path]:
    drifted = []
    for source, copy in REFERENCE_PAIRS.items():
        try:
            copy_content = copy.read_bytes()
        except OSError:
            drifted.append(copy)
            continue
        if copy_content != render(source).encode("utf-8"):
            drifted.append(copy)
    return drifted


def write_references() -> None:
    for source, copy in REFERENCE_PAIRS.items():
        _atomic_write(copy, render(source))


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sync_references.py")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args(arguments)

    if args.write:
        write_references()
        print("reference copies updated")
        return 0

    drifted = reference_drift()
    if drifted:
        for copy in drifted:
            sys.stderr.write(f"{copy}\n")
        return 1
    print("reference copies are in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

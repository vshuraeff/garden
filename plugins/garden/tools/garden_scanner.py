"""Bounded filesystem traversal and checked-file reading helpers."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterator


# runtime limits are read through garden_core so facade monkeypatches remain effective.
MAX_SCAN_DEPTH = 20
MAX_SCAN_ENTRIES = 10_000
MAX_SCAN_SECONDS = 2.0
MAX_CHECKED_FILE_BYTES = 1_048_576
IGNORED_PARTS = {"node_modules", "vendor", "build", "dist", "target"}


class ScanLimitExceeded(RuntimeError):
    """Raised when a bounded project scan reaches its deterministic budget."""


def _walk_files(root: Path) -> Iterator[Path]:
    import garden_core

    root = root.resolve()
    seen = 0
    started = time.monotonic()
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        if time.monotonic() - started > garden_core.MAX_SCAN_SECONDS:
            raise ScanLimitExceeded(
                f"project scan exceeds {garden_core.MAX_SCAN_SECONDS:g} seconds"
            )
        current_path = Path(current)
        depth = len(current_path.relative_to(root).parts)
        dirs[:] = sorted(
            name
            for name in dirs
            if not name.startswith(".")
            and name not in IGNORED_PARTS
            and not (current_path / name).is_symlink()
        )
        if depth >= garden_core.MAX_SCAN_DEPTH:
            dirs[:] = []

        seen += len(dirs) + len(files)
        if seen > garden_core.MAX_SCAN_ENTRIES:
            raise ScanLimitExceeded(
                f"project scan exceeds {garden_core.MAX_SCAN_ENTRIES} entries"
            )
        for name in sorted(files):
            yield current_path / name


def _has_colocated_test(capability: Path) -> bool | None:
    try:
        for candidate in _walk_files(capability):
            name = candidate.name.lower()
            if "test" in name or "spec" in name:
                return True
    except (OSError, ScanLimitExceeded):
        return None
    return False


def _bounded_binary_lines(path: Path) -> Iterator[bytes]:
    import garden_core

    total = 0
    with path.open("rb") as handle:
        while total <= garden_core.MAX_CHECKED_FILE_BYTES:
            remaining = garden_core.MAX_CHECKED_FILE_BYTES - total + 1
            line = handle.readline(remaining)
            if not line:
                return
            total += len(line)
            if total > garden_core.MAX_CHECKED_FILE_BYTES:
                raise ScanLimitExceeded(
                    f"file exceeds {garden_core.MAX_CHECKED_FILE_BYTES} checked bytes"
                )
            yield line


def _decode_line(line: bytes) -> str:
    return line.decode("utf-8-sig", errors="replace").rstrip("\r\n")

"""Bounded filesystem traversal and checked-file reading helpers."""

from __future__ import annotations

import os
import time
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator

from garden_paths import is_within


# runtime limits are read through garden_core so facade monkeypatches remain effective.
MAX_SCAN_DEPTH = 20
MAX_SCAN_ENTRIES = 10_000
MAX_SCAN_SECONDS = 2.0
MAX_CHECKED_FILE_BYTES = 1_048_576
IGNORED_PARTS = {"node_modules", "vendor", "build", "dist", "target"}


class ScanLimitExceeded(RuntimeError):
    """Raised when a bounded project scan reaches its deterministic budget."""

    def __init__(
        self,
        message: str,
        *,
        budget: str | None = None,
        limit: int | float | None = None,
    ) -> None:
        super().__init__(message)
        self.budget = budget
        self.limit = limit


def _glob_matches_relative_path(relative: Path, patterns: tuple[str, ...]) -> bool:
    def matches_recursive(pattern: str) -> bool:
        pattern_parts = PurePosixPath(pattern).parts
        pending = [(0, 0)]
        seen: set[tuple[int, int]] = set()
        while pending:
            path_index, pattern_index = pending.pop()
            state = (path_index, pattern_index)
            if state in seen:
                continue
            seen.add(state)
            if pattern_index == len(pattern_parts):
                if path_index == len(relative.parts):
                    return True
                continue
            if pattern_parts[pattern_index] == "**":
                pending.append((path_index, pattern_index + 1))
                if path_index < len(relative.parts):
                    pending.append((path_index + 1, pattern_index))
                continue
            if path_index < len(relative.parts) and fnmatchcase(
                relative.parts[path_index], pattern_parts[pattern_index]
            ):
                pending.append((path_index + 1, pattern_index + 1))
        return False

    candidate = PurePosixPath("/", *relative.parts)
    for pattern in patterns:
        rooted = f"/{pattern}"
        if candidate.match(rooted):
            return True
        if pattern.startswith("**/") and candidate.match(f"/{pattern[3:]}"):
            return True
        if matches_recursive(pattern):
            return True
    return False


def _walk_files(
    root: Path,
    *,
    roots: tuple[str, ...] = (".",),
    exclude: tuple[str, ...] = (),
    on_missing_root: Callable[[str], None] | None = None,
) -> Iterator[Path]:
    root = root.resolve()
    seen = 0
    started = time.monotonic()
    configured_roots = sorted(
        ((PurePosixPath(value), value) for value in roots),
        key=lambda item: (item[0].as_posix(), item[1]),
    )
    candidates: list[tuple[PurePosixPath, str, Path]] = []
    for normalized, original in configured_roots:
        try:
            candidate = (root / Path(normalized.as_posix())).resolve()
            confined = is_within(candidate, root)
        except (OSError, RuntimeError):
            confined = False
            candidate = root
        if not confined or not candidate.is_dir():
            # missing and unsafe roots share one advisory callback for caller reporting.
            if on_missing_root is not None:
                on_missing_root(original)
            continue
        relative = PurePosixPath(candidate.relative_to(root).as_posix())
        candidates.append((relative, original, candidate))

    walk_roots: list[Path] = []
    for _, _, candidate in sorted(
        candidates, key=lambda item: (item[0].parts, item[1])
    ):
        if any(candidate.is_relative_to(accepted) for accepted in walk_roots):
            continue
        walk_roots.append(candidate)

    def walk_one(scan_root: Path) -> Iterator[Path]:
        nonlocal seen

        for current, dirs, files in os.walk(scan_root, topdown=True, followlinks=False):
            import garden_core

            if time.monotonic() - started > garden_core.MAX_SCAN_SECONDS:
                raise ScanLimitExceeded(
                    f"project scan exceeds {garden_core.MAX_SCAN_SECONDS:g} seconds",
                    budget="seconds",
                    limit=garden_core.MAX_SCAN_SECONDS,
                )
            current_path = Path(current)
            depth = len(current_path.relative_to(root).parts)
            dirs[:] = sorted(
                name
                for name in dirs
                if not name.startswith(".")
                and name not in IGNORED_PARTS
                and not (current_path / name).is_symlink()
                and not _glob_matches_relative_path(
                    (current_path / name).relative_to(root), exclude
                )
            )
            if depth >= garden_core.MAX_SCAN_DEPTH:
                dirs[:] = []

            files = sorted(
                name
                for name in files
                if not _glob_matches_relative_path(
                    (current_path / name).relative_to(root), exclude
                )
            )
            seen += len(dirs) + len(files)
            if seen > garden_core.MAX_SCAN_ENTRIES:
                raise ScanLimitExceeded(
                    f"project scan exceeds {garden_core.MAX_SCAN_ENTRIES} entries",
                    budget="entries",
                    limit=garden_core.MAX_SCAN_ENTRIES,
                )
            for name in files:
                yield current_path / name

    for scan_root in walk_roots:
        relative = scan_root.relative_to(root)
        if _glob_matches_relative_path(relative, exclude):
            continue
        yield from walk_one(scan_root)


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
                    f"file exceeds {garden_core.MAX_CHECKED_FILE_BYTES} checked bytes",
                    budget="bytes",
                    limit=garden_core.MAX_CHECKED_FILE_BYTES,
                )
            yield line


def _decode_line(line: bytes) -> str:
    return line.decode("utf-8-sig", errors="replace").rstrip("\r\n")

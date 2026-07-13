#!/usr/bin/env -S uv run --no-project
"""Atomic, provenance-aware installer for project-scoped GARDEN surfaces."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
import re
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


BLOCK_VERSION = "v1"
BLOCK_PREFIX = f"<!-- garden:managed-instructions:{BLOCK_VERSION} sha256="
BLOCK_END = f"<!-- /garden:managed-instructions:{BLOCK_VERSION} -->"
MARKDOWN_FILE_PREFIX = f"<!-- garden:managed-file:{BLOCK_VERSION} sha256="
TOML_FILE_PREFIX = f"# garden:managed-file:{BLOCK_VERSION} sha256="
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
LOCK_TIMEOUT_SECONDS = 10.0


class ManagedSurfaceError(RuntimeError):
    pass


@contextmanager
def _project_lock(root: Path):
    key = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"garden-project-{key}.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ManagedSurfaceError("timed out waiting for the project lock")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _managed_file(content: str, prefix: str) -> str:
    body = content.rstrip() + "\n"
    return f"{prefix}{_digest(body)} -->\n{body}"


def _parse_managed_file(current: str, prefix: str) -> tuple[str, bool]:
    first, separator, body = current.partition("\n")
    match = re.fullmatch(re.escape(prefix) + r"([0-9a-f]{64}) -->", first)
    if not separator or match is None:
        raise ManagedSurfaceError("destination exists but is not owned by garden:start")
    claimed = match.group(1)
    return body, claimed == _digest(body)


def install_managed_file(
    path: Path, content: str, prefix: str, *, force: bool = False
) -> None:
    desired = _managed_file(content, prefix)
    if path.exists():
        current = path.read_text(encoding="utf-8")
        _, intact = _parse_managed_file(current, prefix)
        if current == desired:
            return
        if not intact and not force:
            raise ManagedSurfaceError(f"managed file was edited: {path}")
    _atomic_write(path, desired)


def remove_managed_file(path: Path, prefix: str, *, force: bool = False) -> None:
    if not path.exists():
        return
    current = path.read_text(encoding="utf-8")
    _, intact = _parse_managed_file(current, prefix)
    if not intact and not force:
        raise ManagedSurfaceError(f"managed file was edited: {path}")
    path.unlink()


def _block(content: str, *, separator_added: bool) -> str:
    body = content.rstrip() + "\n"
    separator = int(separator_added)
    return f"{BLOCK_PREFIX}{_digest(body)} sep={separator} -->\n{body}{BLOCK_END}\n"


def _block_span(content: str) -> tuple[int, int, str, bool, bool] | None:
    lines = content.splitlines(keepends=True)
    starts = [
        index for index, line in enumerate(lines) if line.startswith(BLOCK_PREFIX)
    ]
    ends = [
        index for index, line in enumerate(lines) if line.rstrip("\r\n") == BLOCK_END
    ]
    marker_mentions = sum("garden:managed-instructions" in line for line in lines)
    if not starts and not ends and marker_mentions == 0:
        return None
    if (
        len(starts) != 1
        or len(ends) != 1
        or marker_mentions != 2
        or starts[0] >= ends[0]
    ):
        raise ManagedSurfaceError("AGENTS.md has malformed or duplicate GARDEN markers")

    start, end = starts[0], ends[0]
    start_line = lines[start].rstrip("\r\n")
    match = re.fullmatch(
        re.escape(BLOCK_PREFIX) + r"([0-9a-f]{64}) sep=([01]) -->", start_line
    )
    if match is None:
        raise ManagedSurfaceError("AGENTS.md has a malformed GARDEN start marker")
    claimed = match.group(1)
    separator_added = match.group(2) == "1"
    body = "".join(lines[start + 1 : end])
    return (
        sum(len(line) for line in lines[:start]),
        sum(len(line) for line in lines[: end + 1]),
        body,
        claimed == _digest(body),
        separator_added,
    )


def install_agents_block(path: Path, content: str, *, force: bool = False) -> None:
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    span = _block_span(current)
    if span is None:
        separator_added = bool(current and not current.endswith("\n"))
        separator = "\n" if separator_added else ""
        _atomic_write(
            path,
            current + separator + _block(content, separator_added=separator_added),
        )
        return
    start, end, _, intact, separator_added = span
    if not intact and not force:
        raise ManagedSurfaceError("managed AGENTS.md block was edited")
    desired = _block(content, separator_added=separator_added)
    replacement = current[:start] + desired + current[end:]
    if replacement != current:
        _atomic_write(path, replacement)


def remove_agents_block(path: Path, *, force: bool = False) -> None:
    if not path.exists():
        return
    current = path.read_text(encoding="utf-8")
    span = _block_span(current)
    if span is None:
        return
    start, end, _, intact, separator_added = span
    if not intact and not force:
        raise ManagedSurfaceError("managed AGENTS.md block was edited")
    if separator_added:
        if start == 0 or current[start - 1] != "\n":
            raise ManagedSurfaceError("AGENTS.md managed separator is malformed")
        start -= 1
    remaining = current[:start] + current[end:]
    if remaining.strip():
        _atomic_write(path, remaining)
    else:
        path.unlink()


def install(root: Path, harness: str, *, force: bool = False) -> None:
    with _project_lock(root):
        rules = (PLUGIN_ROOT / "assets" / "garden-rules.md").read_text(encoding="utf-8")
        if harness in ("claude", "both"):
            install_managed_file(
                root / ".claude" / "rules" / "garden.md",
                rules,
                MARKDOWN_FILE_PREFIX,
                force=force,
            )
        if harness in ("codex", "both"):
            install_agents_block(root / "AGENTS.md", rules, force=force)
            agent = (PLUGIN_ROOT / "agents" / "garden-reviewer.toml").read_text(
                encoding="utf-8"
            )
            install_managed_file(
                root / ".codex" / "agents" / "garden-reviewer.toml",
                agent,
                TOML_FILE_PREFIX,
                force=force,
            )


def remove(root: Path, harness: str, *, force: bool = False) -> None:
    with _project_lock(root):
        if harness in ("claude", "both"):
            remove_managed_file(
                root / ".claude" / "rules" / "garden.md",
                MARKDOWN_FILE_PREFIX,
                force=force,
            )
        if harness in ("codex", "both"):
            remove_agents_block(root / "AGENTS.md", force=force)
            remove_managed_file(
                root / ".codex" / "agents" / "garden-reviewer.toml",
                TOML_FILE_PREFIX,
                force=force,
            )


def main() -> int:
    parser = argparse.ArgumentParser(prog="garden-project")
    parser.add_argument("action", choices=("install", "remove"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--harness", choices=("claude", "codex", "both"), required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "install":
            install(Path(args.root).resolve(), args.harness, force=args.force)
        else:
            remove(Path(args.root).resolve(), args.harness, force=args.force)
    except (ManagedSurfaceError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

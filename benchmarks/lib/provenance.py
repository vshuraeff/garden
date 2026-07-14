"""Deterministic toolchain and provenance helpers."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def repository_root() -> Path:
    """Return the repository root resolved from this module's location."""

    return Path(__file__).resolve().parents[2]


def load_toolchain(path: Path | None = None) -> dict[str, Any]:
    """Load the checked-in toolchain pin file."""

    source = path or repository_root() / "benchmarks" / "toolchain.toml"
    with source.open("rb") as handle:
        return tomllib.load(handle)


def git_commit(root: Path | None = None) -> str:
    """Return the current commit SHA for a Git worktree."""

    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root or repository_root(),
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def plugin_tree_hash(root: Path | None = None) -> str:
    """Return the Git tree hash for the current plugins subtree."""

    completed = subprocess.run(
        ["git", "rev-parse", "HEAD:plugins"],
        cwd=root or repository_root(),
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def plugin_version(root: Path | None = None) -> str:
    """Read the Claude plugin manifest version."""

    base = root or repository_root()
    manifest = base / "plugins" / "garden" / ".claude-plugin" / "plugin.json"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    version = value.get("version")
    if not isinstance(version, str):
        raise ValueError(f"plugin manifest has no string version: {manifest}")
    return version


def platform_string() -> str:
    """Return the normalized benchmark platform name."""

    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "linux":
        try:
            identifier = platform.freedesktop_os_release().get("ID", "")
        except OSError:
            identifier = ""
        return identifier or system
    return system


def python_version_string() -> str:
    """Return the running Python version without implementation metadata."""

    return platform.python_version()


def sha256_bytes(content: bytes) -> str:
    """Return the lowercase SHA-256 digest of bytes."""

    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_path_bytes(content: bytes, paths: Iterable[Path]) -> bytes:
    """Replace environment-specific absolute paths with one stable token."""

    variants = {
        rendered.encode()
        for path in paths
        for rendered in {str(path), str(path.resolve())}
        if rendered
    }
    normalized = content
    for variant in sorted(variants, key=len, reverse=True):
        normalized = normalized.replace(variant, b"<benchmark-temp-root>")
    return normalized

"""Canonical project-root discovery and path confinement helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


MAX_ROOT_SEARCH_DEPTH = 31


@dataclass(frozen=True)
class ProjectActivation:
    root: Path
    kind: str


def find_project_activation(start: Path) -> ProjectActivation | None:
    """Find the nearest config or legacy activation marker."""

    import garden_core

    current = start.resolve()
    if not current.is_dir():
        current = current.parent

    for _ in range(garden_core.MAX_ROOT_SEARCH_DEPTH):
        if (current / ".garden.toml").is_file():
            return ProjectActivation(current, "config")
        if (current / "naming-registry.txt").is_file():
            return ProjectActivation(current, "legacy")
        if current.parent == current:
            return None
        current = current.parent
    return None


def find_project_root(start: Path) -> Path | None:
    """Find the nearest ancestor activated by config or a naming registry."""

    activation = find_project_activation(start)
    return activation.root if activation else None


def is_within(path: Path, root: Path) -> bool:
    """Return whether a canonical path stays inside a canonical project root."""

    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _relative_path(path: Path, root: Path) -> Path | None:
    try:
        return path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return None

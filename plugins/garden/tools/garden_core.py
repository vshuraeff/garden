"""Shared deterministic checks used by GARDEN hooks, CLI, and MCP tools."""

from __future__ import annotations

import re
from pathlib import Path

from garden_config import (
    CONFIG_NAME,
    CapabilityResolution,
    ConfigResult,
    EffectiveConfig,
    load_config,
    resolve_capability,
    resolve_effective,
    resolve_test_association,
)
from garden_paths import (
    MAX_ROOT_SEARCH_DEPTH,
    ProjectActivation,
    find_project_activation,
    find_project_root,
    is_within,
)
from garden_report import Finding
from garden_rules import (
    CONTEXT_LINE_BUDGET,
    NON_SOURCE_NAMES,
    NON_SOURCE_SUFFIXES,
    inspect_file,
    inspect_project,
)
from garden_scanner import (
    IGNORED_PARTS,
    MAX_CHECKED_FILE_BYTES,
    MAX_SCAN_DEPTH,
    MAX_SCAN_ENTRIES,
    MAX_SCAN_SECONDS,
    ScanLimitExceeded,
)


__all__ = [
    "CONFIG_NAME",
    "CONTEXT_LINE_BUDGET",
    "IGNORED_PARTS",
    "MAX_CHECKED_FILE_BYTES",
    "MAX_ROOT_SEARCH_DEPTH",
    "MAX_SCAN_DEPTH",
    "MAX_SCAN_ENTRIES",
    "MAX_SCAN_SECONDS",
    "NON_SOURCE_NAMES",
    "NON_SOURCE_SUFFIXES",
    "CapabilityResolution",
    "ConfigResult",
    "EffectiveConfig",
    "Finding",
    "ProjectActivation",
    "ScanLimitExceeded",
    "find_project_activation",
    "find_project_root",
    "inspect_file",
    "inspect_project",
    "is_within",
    "load_config",
    "resolve_capability",
    "resolve_effective",
    "resolve_test_association",
    "route_prompt",
]


def route_prompt(prompt: str, cwd: Path) -> list[str]:
    """Return relevant GARDEN skills for an active project prompt."""

    if find_project_root(cwd) is None:
        return []

    lowered = prompt.lower()
    skills: list[str] = []

    def add(skill: str) -> None:
        if skill not in skills:
            skills.append(skill)

    if any(
        token in lowered
        for token in (
            "new project",
            "bootstrap",
            "scaffold",
            "новый проект",
            "заведи слайс",
            "new slice",
        )
    ):
        add("garden:bootstrap")
    if any(
        token in lowered
        for token in (
            "retrofit",
            "legacy",
            "внедрить garden",
            "инкрементально",
            "strangler",
        )
    ):
        add("garden:retrofit")
    if any(
        token in lowered
        for token in ("audit", "аудит", "compliance", "checklist", "зрелость")
    ):
        add("garden:audit")

    review = (
        any(
            token in lowered
            for token in ("review", "ревью", "diff", "commit", "pull request")
        )
        or re.search(r"\bpr\b", lowered) is not None
    )
    garden = any(
        token in lowered for token in ("garden", "principles", "slice", "contract")
    )
    if review and garden:
        add("garden:review")
    return skills

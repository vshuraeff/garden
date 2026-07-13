"""Shared deterministic checks used by GARDEN hooks, CLI, and MCP tools."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path


IGNORED_PARTS = {"node_modules", "vendor", "build", "dist", "target"}
NON_SOURCE_NAMES = {
    "Dockerfile",
    "Makefile",
    "LICENSE",
    "NOTICE",
    "CHANGELOG",
    "Gemfile",
    "Gemfile.lock",
    "Pipfile",
    "Pipfile.lock",
    "Rakefile",
    "Procfile",
}
NON_SOURCE_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".lock",
}


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    path: str
    message: str


def find_project_root(start: Path) -> Path | None:
    """Find the nearest ancestor activated by a naming registry."""

    current = start.resolve()
    if current.is_file():
        current = current.parent

    for _ in range(31):
        if (current / "naming-registry.txt").is_file():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


def _relative_path(path: Path, root: Path) -> Path | None:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return None


def _is_source_file(relative: Path) -> bool:
    if relative.name.startswith("."):
        return False
    if (
        relative.name in NON_SOURCE_NAMES
        or relative.suffix.lower() in NON_SOURCE_SUFFIXES
    ):
        return False
    return not any(
        part.startswith(".") or part in IGNORED_PARTS for part in relative.parts
    )


def _has_colocated_test(capability: Path) -> bool:
    for candidate in capability.rglob("*"):
        relative = candidate.relative_to(capability)
        if any(
            part.startswith(".") or part in IGNORED_PARTS for part in relative.parts
        ):
            continue
        name = candidate.name.lower()
        if candidate.is_dir() and name == "tests":
            return True
        if candidate.is_file() and ("test" in name or "spec" in name):
            return True
    return False


def inspect_file(path: Path, root: Path | None = None) -> list[Finding]:
    """Check the deterministic GARDEN rules affected by one file."""

    resolved = path.resolve()
    project_root = root.resolve() if root else find_project_root(resolved)
    if project_root is None:
        return []

    relative = _relative_path(resolved, project_root)
    if relative is None:
        return []

    findings: list[Finding] = []
    display_path = relative.as_posix()

    if relative == Path("CONTEXT.md") and resolved.is_file():
        line_count = len(
            resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        )
        if line_count > 200:
            findings.append(
                Finding(
                    "error",
                    "N-context-budget",
                    display_path,
                    f"CONTEXT.md has {line_count} lines; the GARDEN MUST budget is 200",
                )
            )

    if relative.name == "CONTRACT.md":
        first_nonempty = ""
        if resolved.is_file():
            for line in resolved.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                if line:
                    first_nonempty = line.rstrip("\r")
                    break
        if re.fullmatch(r"Version: [0-9]+\.[0-9]+\.[0-9]+", first_nonempty) is None:
            findings.append(
                Finding(
                    "error",
                    "R-contract-version",
                    display_path,
                    "CONTRACT.md must start with 'Version: MAJOR.MINOR.PATCH'",
                )
            )

    if len(relative.parts) < 2 or not _is_source_file(relative):
        return findings

    capability = project_root / relative.parts[0]
    if not capability.is_dir():
        return findings

    if not (capability / "CONTRACT.md").is_file():
        findings.append(
            Finding(
                "advisory",
                "R-component-contract",
                display_path,
                f"capability '{relative.parts[0]}' has no CONTRACT.md",
            )
        )

    if not _has_colocated_test(capability):
        findings.append(
            Finding(
                "advisory",
                "A-colocated-tests",
                display_path,
                f"capability '{relative.parts[0]}' has no colocated tests",
            )
        )

    return findings


def inspect_project(root: Path) -> dict[str, object]:
    """Return a bounded structural snapshot of one GARDEN project."""

    resolved = root.resolve()
    project_root = find_project_root(resolved)
    if project_root is None:
        return {
            "active": False,
            "root": str(resolved),
            "findings": [],
            "summary": {"errors": 0, "advisories": 0},
        }

    candidates: set[Path] = {project_root / "CONTEXT.md"}
    candidates.update(project_root.glob("*/CONTRACT.md"))
    for capability in project_root.iterdir():
        if (
            not capability.is_dir()
            or capability.name.startswith(".")
            or capability.name in IGNORED_PARTS
        ):
            continue
        source = next(
            (
                path
                for path in capability.rglob("*")
                if path.is_file() and _is_source_file(path.relative_to(project_root))
            ),
            None,
        )
        if source:
            candidates.add(source)

    findings = [
        finding
        for path in sorted(candidates)
        for finding in inspect_file(path, project_root)
    ]
    unique = list(
        {
            (item.severity, item.rule, item.path, item.message): item
            for item in findings
        }.values()
    )
    return {
        "active": True,
        "root": str(project_root),
        "findings": [asdict(item) for item in unique],
        "summary": {
            "errors": sum(item.severity == "error" for item in unique),
            "advisories": sum(item.severity == "advisory" for item in unique),
        },
    }


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

    review = any(
        token in lowered
        for token in ("review", "ревью", "diff", "commit", "pull request")
    )
    garden = any(
        token in lowered for token in ("garden", "principles", "slice", "contract")
    )
    if review and garden:
        add("garden:review")
    return skills

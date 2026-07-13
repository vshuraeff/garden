"""Shared deterministic checks used by GARDEN hooks, CLI, and MCP tools."""

from __future__ import annotations

import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator


CONTEXT_LINE_BUDGET = 200
MAX_ROOT_SEARCH_DEPTH = 31
MAX_SCAN_DEPTH = 20
MAX_SCAN_ENTRIES = 10_000
MAX_SCAN_SECONDS = 2.0
MAX_CHECKED_FILE_BYTES = 1_048_576
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


class ScanLimitExceeded(RuntimeError):
    """Raised when a bounded project scan reaches its deterministic budget."""


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    path: str
    message: str


def find_project_root(start: Path) -> Path | None:
    """Find the nearest ancestor activated by a naming registry."""

    current = start.resolve()
    if not current.is_dir():
        current = current.parent

    for _ in range(MAX_ROOT_SEARCH_DEPTH):
        if (current / "naming-registry.txt").is_file():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


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


def _walk_files(root: Path) -> Iterator[Path]:
    root = root.resolve()
    seen = 0
    started = time.monotonic()
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        if time.monotonic() - started > MAX_SCAN_SECONDS:
            raise ScanLimitExceeded(
                f"project scan exceeds {MAX_SCAN_SECONDS:g} seconds"
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
        if depth >= MAX_SCAN_DEPTH:
            dirs[:] = []

        seen += len(dirs) + len(files)
        if seen > MAX_SCAN_ENTRIES:
            raise ScanLimitExceeded(f"project scan exceeds {MAX_SCAN_ENTRIES} entries")
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
    total = 0
    with path.open("rb") as handle:
        while total <= MAX_CHECKED_FILE_BYTES:
            remaining = MAX_CHECKED_FILE_BYTES - total + 1
            line = handle.readline(remaining)
            if not line:
                return
            total += len(line)
            if total > MAX_CHECKED_FILE_BYTES:
                raise ScanLimitExceeded(
                    f"file exceeds {MAX_CHECKED_FILE_BYTES} checked bytes"
                )
            yield line


def _decode_line(line: bytes) -> str:
    return line.decode("utf-8-sig", errors="replace").rstrip("\r\n")


def inspect_file(
    path: Path,
    root: Path | None = None,
    test_cache: dict[Path, bool | None] | None = None,
) -> list[Finding]:
    """Check the deterministic GARDEN rules affected by one confined file."""

    resolved = path.resolve()
    project_root = root.resolve() if root else find_project_root(resolved)
    if project_root is None or not is_within(resolved, project_root):
        return []
    if not (project_root / "naming-registry.txt").is_file():
        return []

    relative = _relative_path(resolved, project_root)
    if relative is None:
        return []

    findings: list[Finding] = []
    display_path = relative.as_posix()

    if relative == Path("CONTEXT.md") and resolved.is_file():
        try:
            line_count = 0
            for _ in _bounded_binary_lines(resolved):
                line_count += 1
                if line_count > CONTEXT_LINE_BUDGET:
                    findings.append(
                        Finding(
                            "error",
                            "N-context-budget",
                            display_path,
                            f"CONTEXT.md exceeds {CONTEXT_LINE_BUDGET} lines; trim it or move detail into capability READMEs",
                        )
                    )
                    break
        except ScanLimitExceeded as error:
            findings.append(
                Finding("error", "N-context-scan-limit", display_path, str(error))
            )

    if relative.name == "CONTRACT.md":
        first_nonempty = ""
        try:
            if resolved.is_file():
                for line in _bounded_binary_lines(resolved):
                    decoded = _decode_line(line)
                    if decoded:
                        first_nonempty = decoded
                        break
        except ScanLimitExceeded as error:
            findings.append(
                Finding("error", "R-contract-scan-limit", display_path, str(error))
            )
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
    if not capability.is_dir() or capability.is_symlink():
        return findings

    if not (capability / "CONTRACT.md").is_file():
        findings.append(
            Finding(
                "advisory",
                "R-component-contract",
                display_path,
                "capability has no CONTRACT.md",
            )
        )

    cache = test_cache if test_cache is not None else {}
    capability_key = capability.resolve()
    if capability_key not in cache:
        cache[capability_key] = _has_colocated_test(capability)
    has_test = cache[capability_key]
    if has_test is False:
        findings.append(
            Finding(
                "advisory",
                "A-colocated-tests",
                display_path,
                "capability has no colocated tests",
            )
        )
    return findings


def inspect_project(root: Path) -> dict[str, object]:
    """Return a bounded structural snapshot of one trusted GARDEN root."""

    resolved = root.resolve()
    if find_project_root(resolved) != resolved:
        return {
            "active": False,
            "root": str(resolved),
            "findings": [],
            "summary": {"errors": 0, "advisories": 0},
        }

    candidates: set[Path] = {resolved / "CONTEXT.md"}
    candidates.update(resolved.glob("*/CONTRACT.md"))
    scan_error: str | None = None
    try:
        sources: dict[str, Path] = {}
        for path in _walk_files(resolved):
            relative = path.relative_to(resolved)
            if len(relative.parts) >= 2 and _is_source_file(relative):
                sources.setdefault(relative.parts[0], path)
        candidates.update(sources.values())
    except (OSError, ScanLimitExceeded) as error:
        scan_error = str(error)

    test_cache: dict[Path, bool | None] = {}
    findings = [
        finding
        for path in sorted(candidates)
        for finding in inspect_file(path, resolved, test_cache)
    ]
    if scan_error:
        findings.append(Finding("error", "D-project-scan-limit", ".", scan_error))
    unique = list(
        {
            (item.severity, item.rule, item.path, item.message): item
            for item in findings
        }.values()
    )
    return {
        "active": True,
        "root": str(resolved),
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

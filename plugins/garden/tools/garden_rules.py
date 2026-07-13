"""Deterministic GARDEN file and project rule checks."""

from __future__ import annotations

import re
from pathlib import Path

from garden_paths import _relative_path, find_project_root, is_within
from garden_report import Finding, build_project_report
from garden_scanner import (
    IGNORED_PARTS,
    ScanLimitExceeded,
    _bounded_binary_lines,
    _decode_line,
    _has_colocated_test,
    _walk_files,
)


CONTEXT_LINE_BUDGET = 200
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
        return build_project_report(resolved, False, [])

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
    return build_project_report(resolved, True, findings)

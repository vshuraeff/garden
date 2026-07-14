"""Deterministic GARDEN file and project rule checks."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from garden_config import ConfigResult, EffectiveConfig, load_config, resolve_effective
from garden_paths import (
    _relative_path,
    find_project_activation,
    find_project_root,
    is_within,
)
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


def _config_findings(result: ConfigResult) -> list[Finding]:
    return [
        Finding("error", "N-CONFIG-INVALID", ".garden.toml", str(error))
        for error in result.errors
    ]


def _matches_test_pattern(relative: Path, patterns: tuple[str, ...]) -> bool:
    candidate = PurePosixPath("/", *relative.parts)
    for pattern in patterns:
        rooted = f"/{pattern}"
        if candidate.match(rooted):
            return True
        if pattern.startswith("**/") and candidate.match(f"/{pattern[3:]}"):
            return True
    return False


def _has_configured_test(
    capability: Path, root: Path, patterns: tuple[str, ...]
) -> bool | None:
    try:
        for candidate in _walk_files(capability):
            if _matches_test_pattern(candidate.relative_to(root), patterns):
                return True
    except (OSError, ScanLimitExceeded, ValueError):
        return None
    return False


def _context_missing(root: Path, config: EffectiveConfig) -> Finding | None:
    documentation = config.documentation
    if not documentation.root_context_required.value:
        return None
    any_of = config.project.context_files.any_of.value
    all_of = config.project.context_files.all_of.value
    if not any_of and not all_of:
        any_satisfied = False
    else:
        any_satisfied = not any_of or any((root / path).is_file() for path in any_of)
    all_satisfied = all((root / path).is_file() for path in all_of)
    if any_satisfied and all_satisfied:
        return None
    required = sorted(set(any_of) | set(all_of))
    names = ", ".join(required) if required else "a configured root context file"
    return Finding(
        "error",
        "N-CONTEXT-MISSING",
        ".",
        f"required root context is missing; expected {names}",
    )


def inspect_file(
    path: Path,
    root: Path | None = None,
    test_cache: dict[Path, bool | None] | None = None,
    config_result: ConfigResult | None = None,
) -> list[Finding]:
    """Check the deterministic GARDEN rules affected by one confined file."""

    resolved = path.resolve()
    project_root = root.resolve() if root else find_project_root(resolved)
    if project_root is None or not is_within(resolved, project_root):
        return []
    activation = find_project_activation(project_root)
    if activation is None or activation.root != project_root:
        return []

    loaded = config_result or load_config(project_root)
    if loaded.present and loaded.errors:
        return _config_findings(loaded)
    configured = loaded.present and loaded.config is not None
    effective = resolve_effective(loaded.config) if configured else None

    relative = _relative_path(resolved, project_root)
    if relative is None:
        return []

    findings: list[Finding] = []
    display_path = relative.as_posix()

    if not configured and relative == Path("naming-registry.txt"):
        findings.append(
            Finding(
                "advisory",
                "N-LEGACY-NAMING-REGISTRY",
                display_path,
                "legacy project activation is deprecated; run garden migrate-config",
            )
        )

    context_paths = (
        set(effective.project.context_files.any_of.value)
        | set(effective.project.context_files.all_of.value)
        if effective
        else {"CONTEXT.md"}
    )
    context_budget = (
        effective.documentation.max_context_lines.value
        if effective
        else CONTEXT_LINE_BUDGET
    )
    if display_path in context_paths and resolved.is_file():
        try:
            line_count = 0
            for _ in _bounded_binary_lines(resolved):
                line_count += 1
                if line_count > context_budget:
                    message = (
                        f"context file exceeds {context_budget} lines; trim it or move detail into capability READMEs"
                        if effective
                        else f"CONTEXT.md exceeds {CONTEXT_LINE_BUDGET} lines; trim it or move detail into capability READMEs"
                    )
                    findings.append(
                        Finding(
                            "error",
                            "N-context-budget",
                            display_path,
                            message,
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
        cache[capability_key] = (
            _has_configured_test(
                capability, project_root, effective.tests.patterns.value
            )
            if effective
            else _has_colocated_test(capability)
        )
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
    activation = find_project_activation(resolved)
    if activation is None or activation.root != resolved:
        return build_project_report(resolved, False, [])

    loaded = load_config(resolved)
    if loaded.present and loaded.errors:
        return build_project_report(resolved, True, _config_findings(loaded))
    configured = loaded.present and loaded.config is not None
    effective = resolve_effective(loaded.config) if configured else None

    context_paths = (
        set(effective.project.context_files.any_of.value)
        | set(effective.project.context_files.all_of.value)
        if effective
        else {"CONTEXT.md"}
    )
    candidates: set[Path] = {resolved / path for path in context_paths}
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
    findings = []
    if effective:
        missing = _context_missing(resolved, effective)
        if missing:
            findings.append(missing)
    findings.extend(
        finding
        for path in sorted(candidates)
        for finding in inspect_file(path, resolved, test_cache, loaded)
    )
    if scan_error:
        findings.append(Finding("error", "D-project-scan-limit", ".", scan_error))
    return build_project_report(resolved, True, findings)

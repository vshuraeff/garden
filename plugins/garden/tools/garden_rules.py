"""Deterministic GARDEN file and project rule checks."""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Callable

from garden_config import (
    ConfigResult,
    EffectiveConfig,
    load_config,
    resolve_capability,
    resolve_effective,
    resolve_test_association,
)
from garden_paths import (
    _relative_path,
    find_project_activation,
    find_project_root,
    is_within,
)
from garden_report import Finding, build_project_report
from garden_rule_metadata import resolve_alias
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


def make_finding(
    runtime_id: str,
    severity: str,
    path: str,
    message: str,
    *,
    state: str = "fail",
) -> Finding:
    rule_id, runtime_alias, level = resolve_alias(runtime_id)
    return Finding(
        severity=severity,
        rule=runtime_id,
        path=path,
        message=message,
        rule_id=rule_id,
        runtime_alias=runtime_alias,
        level=level,
        state=state,
    )


def _serialized_exceptions(config: EffectiveConfig | None) -> list[dict[str, object]]:
    if config is None:
        return []
    return [
        {
            "rule_id": item.rule_id.value,
            "paths": list(item.paths.value),
            "reason": item.reason.value,
            "owner": item.owner.value,
            "review_after": item.review_after.value,
        }
        for item in config.exceptions.value
    ]


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
        make_finding("N-CONFIG-INVALID", "error", ".garden.toml", str(error))
        for error in result.errors
    ]


def _matches_path_pattern(relative: Path, patterns: tuple[str, ...]) -> bool:
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


def _is_configured_source_file(relative: Path, config: EffectiveConfig) -> bool:
    if relative.name.startswith(".") or any(
        part.startswith(".") or part in IGNORED_PARTS for part in relative.parts
    ):
        return False
    if _matches_path_pattern(relative, config.scan.exclude.value):
        return False
    patterns = config.scan.include.value
    if not patterns:
        return _is_source_file(relative)
    return _matches_path_pattern(relative, patterns)


def _relative_parts(value: str) -> tuple[str, ...]:
    if value == ".":
        return ()
    return PurePosixPath(value).parts


def _under(relative: Path, prefix: str) -> tuple[str, ...] | None:
    prefix_parts = _relative_parts(prefix)
    if relative.parts[: len(prefix_parts)] != prefix_parts:
        return None
    return relative.parts[len(prefix_parts) :]


def _no_capability_directory(
    relative: Path, root: Path, config: EffectiveConfig
) -> Path | None:
    return None


def _children_capability_directory(
    relative: Path, root: Path, config: EffectiveConfig
) -> Path | None:
    depth = config.capabilities.depth.value
    for capability_root in config.capabilities.roots.value:
        remainder = _under(relative, capability_root)
        if remainder is not None and len(remainder) > depth:
            return root.joinpath(*_relative_parts(capability_root), *remainder[:depth])
    return None


def _explicit_capability_directory(
    relative: Path, root: Path, config: EffectiveConfig
) -> Path | None:
    mappings = sorted(
        config.capabilities.map.value,
        key=lambda item: len(_relative_parts(item[0])),
        reverse=True,
    )
    for prefix, _ in mappings:
        if _under(relative, prefix) is not None:
            # explicit names are logical; the matched source prefix owns the contract.
            return root.joinpath(*_relative_parts(prefix))
    return None


_CAPABILITY_DIRECTORY_RESOLVERS: dict[
    str, Callable[[Path, Path, EffectiveConfig], Path | None]
] = {
    "none": _no_capability_directory,
    "children": _children_capability_directory,
    "explicit": _explicit_capability_directory,
    "markers": _no_capability_directory,
}


def _capability_directory(
    relative: Path, root: Path, config: EffectiveConfig
) -> Path | None:
    strategy = config.capabilities.strategy.value
    return _CAPABILITY_DIRECTORY_RESOLVERS[strategy](relative, root, config)


def _capability_identity(relative_path: str, config: EffectiveConfig) -> str | None:
    resolution = resolve_capability(relative_path, config)
    if resolution.status != "capability":
        return None
    return resolution.capability


def _same_capability_test_identity(
    relative: Path, config: EffectiveConfig
) -> str | None:
    return _capability_identity(relative.as_posix(), config)


def _test_roots_test_identity(relative: Path, config: EffectiveConfig) -> str | None:
    association = resolve_test_association(relative.as_posix(), config)
    if association.status != "mapped" or association.source_prefix is None:
        return None
    # mapped source paths reuse capability resolution so logical names stay canonical.
    return _capability_identity(association.source_prefix, config)


_TEST_IDENTITY_RESOLVERS: dict[str, Callable[[Path, EffectiveConfig], str | None]] = {
    "same-capability": _same_capability_test_identity,
    "test-roots": _test_roots_test_identity,
}


def _configured_test_identity(relative: Path, config: EffectiveConfig) -> str | None:
    if not _matches_path_pattern(relative, config.tests.patterns.value):
        return None
    association = config.tests.association.value
    return _TEST_IDENTITY_RESOLVERS[association](relative, config)


def _configured_test_capabilities(
    root: Path, config: EffectiveConfig
) -> tuple[set[str], str | None]:
    capabilities: set[str] = set()
    try:
        for candidate in _walk_files(root):
            identity = _configured_test_identity(candidate.relative_to(root), config)
            if identity is not None:
                capabilities.add(identity)
    except (OSError, ScanLimitExceeded) as error:
        return capabilities, str(error)
    return capabilities, None


def _naming_findings(
    root: Path, result: ConfigResult, config: EffectiveConfig
) -> list[Finding]:
    raw = result.config
    if raw is None:
        return []
    required = config.naming.required.value
    if not required and raw.naming is None:
        return []

    registry_name = config.naming.registry.value
    registry = root / registry_name
    if not registry.is_file():
        if not required:
            return []
        return [
            make_finding(
                "N-NAMING-MISSING",
                "error",
                registry_name,
                f"required naming registry was not found; expected {registry_name}",
            )
        ]

    findings: list[Finding] = []
    concepts: set[str] = set()
    canonical_names: set[str] = set()
    entry_count = 0
    try:
        for line_number, encoded in enumerate(_bounded_binary_lines(registry), 1):
            content = _decode_line(encoded).strip()
            if not content or content.startswith("#"):
                continue
            entry_count += 1
            if ":" not in content:
                findings.append(
                    make_finding(
                        "N-NAMING-INVALID-ENTRY",
                        "error",
                        registry_name,
                        f"naming registry line {line_number} is invalid: "
                        f"{content!r}; expected 'concept: canonical_name'",
                    )
                )
                continue
            concept, canonical = (part.strip() for part in content.split(":", 1))
            if not concept or not canonical:
                findings.append(
                    make_finding(
                        "N-NAMING-INVALID-ENTRY",
                        "error",
                        registry_name,
                        f"naming registry line {line_number} is invalid: "
                        f"{content!r}; concept and canonical name must both be "
                        "non-empty",
                    )
                )
                continue
            if concept in concepts:
                findings.append(
                    make_finding(
                        "N-NAMING-DUPLICATE-CONCEPT",
                        "error",
                        registry_name,
                        f"naming registry repeats concept {concept!r}; each concept "
                        "must be unique",
                    )
                )
            else:
                concepts.add(concept)
            if canonical in canonical_names:
                findings.append(
                    make_finding(
                        "N-NAMING-DUPLICATE-CANONICAL",
                        "error",
                        registry_name,
                        f"naming registry repeats canonical name {canonical!r}; "
                        "each canonical name must be unique",
                    )
                )
            else:
                canonical_names.add(canonical)
    except (OSError, ScanLimitExceeded) as error:
        findings.append(
            make_finding(
                "N-NAMING-INVALID-ENTRY",
                "error",
                registry_name,
                f"naming registry could not be validated: {error}",
            )
        )
        return findings

    if required and entry_count == 0:
        findings.append(
            make_finding(
                "N-NAMING-EMPTY-REGISTRY",
                "error",
                registry_name,
                "required naming registry has no entries; expected "
                "'concept: canonical_name' on each non-comment line",
            )
        )
    return findings


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
    return make_finding(
        "N-CONTEXT-MISSING",
        "error",
        ".",
        f"required root context is missing; expected {names}",
    )


def inspect_file(
    path: Path,
    root: Path | None = None,
    test_cache: dict[Path | str, bool | None] | None = None,
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
            make_finding(
                "N-LEGACY-NAMING-REGISTRY",
                "advisory",
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
                        make_finding(
                            "N-context-budget",
                            "error",
                            display_path,
                            message,
                        )
                    )
                    break
        except ScanLimitExceeded as error:
            findings.append(
                make_finding(
                    "N-context-scan-limit",
                    "error",
                    display_path,
                    str(error),
                    state="unknown",
                )
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
                make_finding(
                    "R-contract-scan-limit",
                    "error",
                    display_path,
                    str(error),
                    state="unknown",
                )
            )
        if re.fullmatch(r"Version: [0-9]+\.[0-9]+\.[0-9]+", first_nonempty) is None:
            findings.append(
                make_finding(
                    "R-contract-version",
                    "error",
                    display_path,
                    "CONTRACT.md must start with 'Version: MAJOR.MINOR.PATCH'",
                )
            )

    if not configured:
        if len(relative.parts) < 2 or not _is_source_file(relative):
            return findings

        capability = project_root / relative.parts[0]
        if not capability.is_dir() or capability.is_symlink():
            return findings

        if not (capability / "CONTRACT.md").is_file():
            findings.append(
                make_finding(
                    "R-component-contract",
                    "advisory",
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
                make_finding(
                    "A-colocated-tests",
                    "advisory",
                    display_path,
                    "capability has no colocated tests",
                )
            )
        return findings

    if effective is None or not _is_configured_source_file(relative, effective):
        return findings
    if _matches_path_pattern(relative, effective.tests.patterns.value):
        return findings
    resolution = resolve_capability(relative.as_posix(), effective)
    if resolution.status != "capability" or resolution.capability is None:
        return findings
    capability = _capability_directory(relative, project_root, effective)
    if capability is None or not capability.is_dir() or capability.is_symlink():
        return findings

    if not (capability / "CONTRACT.md").is_file():
        findings.append(
            make_finding(
                "R-component-contract",
                "advisory",
                display_path,
                "capability has no CONTRACT.md",
            )
        )

    cache = test_cache if test_cache is not None else {}
    capability_key = resolution.capability
    scan_error: str | None = None
    if capability_key not in cache:
        tested_capabilities, scan_error = _configured_test_capabilities(
            project_root, effective
        )
        cache[capability_key] = (
            capability_key in tested_capabilities if scan_error is None else None
        )
    if cache[capability_key] is False:
        findings.append(
            make_finding(
                "A-colocated-tests",
                "advisory",
                display_path,
                "capability has no colocated tests",
            )
        )
    if scan_error:
        findings.append(
            make_finding(
                "D-project-scan-limit",
                "error",
                ".",
                scan_error,
                state="unknown",
            )
        )
    return findings


def inspect_project(root: Path) -> dict[str, object]:
    """Return a bounded structural snapshot of one trusted GARDEN root."""

    resolved = root.resolve()
    activation = find_project_activation(resolved)
    if activation is None or activation.root != resolved:
        return build_project_report(resolved, False, [], complete=False)

    loaded = load_config(resolved)
    if loaded.present and loaded.errors:
        return build_project_report(
            resolved,
            True,
            _config_findings(loaded),
            complete=False,
            config_path=loaded.path.relative_to(resolved).as_posix(),
            config_valid=loaded.valid,
        )
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
    sources: dict[str, Path] = {}
    tested_capabilities: set[str] = set()
    try:
        for path in _walk_files(resolved):
            relative = path.relative_to(resolved)
            if effective:
                test_identity = _configured_test_identity(relative, effective)
                if test_identity is not None:
                    tested_capabilities.add(test_identity)
                is_test = _matches_path_pattern(
                    relative, effective.tests.patterns.value
                )
                if not is_test and _is_configured_source_file(relative, effective):
                    capability_identity = _capability_identity(
                        relative.as_posix(), effective
                    )
                    if capability_identity is not None:
                        sources.setdefault(capability_identity, path)
            elif len(relative.parts) >= 2 and _is_source_file(relative):
                sources.setdefault(relative.parts[0], path)
        candidates.update(sources.values())
    except (OSError, ScanLimitExceeded) as error:
        scan_error = str(error)

    test_cache: dict[Path | str, bool | None] = {}
    if effective:
        test_cache.update(
            {
                capability: (
                    capability in tested_capabilities if scan_error is None else None
                )
                for capability in sources
            }
        )
        for candidate in candidates:
            relative = candidate.relative_to(resolved)
            capability = _capability_identity(relative.as_posix(), effective)
            if capability is not None:
                test_cache.setdefault(
                    capability,
                    capability in tested_capabilities if scan_error is None else None,
                )
    findings = []
    if effective:
        missing = _context_missing(resolved, effective)
        if missing:
            findings.append(missing)
        findings.extend(_naming_findings(resolved, loaded, effective))
    findings.extend(
        finding
        for path in sorted(candidates)
        for finding in inspect_file(path, resolved, test_cache, loaded)
    )
    if scan_error:
        findings.append(
            make_finding(
                "D-project-scan-limit",
                "error",
                ".",
                scan_error,
                state="unknown",
            )
        )
    return build_project_report(
        resolved,
        True,
        findings,
        config_path=(
            loaded.path.relative_to(resolved).as_posix() if loaded.present else None
        ),
        config_schema_version=(effective.schema_version.value if effective else None),
        config_valid=loaded.valid,
        exceptions=_serialized_exceptions(effective),
    )

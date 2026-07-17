#!/usr/bin/env -S uv run --no-project
"""Validate the canonical GARDEN rule registry against its source documents."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from garden_registry import (
    DEFAULT_REGISTRY_PATH,
    Registry,
    RegistryError,
    load_registry,
)
from garden_rule_metadata import EXCEPTION_ELIGIBLE_RULES, RUNTIME_ALIAS_TABLE
from validate_docs import RULE_DEFINITION, RULE_ID, line_number


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PLUGIN_ROOT.parent.parent
LEVEL = r"REQUIRED|DEFAULT|EXPERIMENTAL"
PRINCIPLE_LEVEL = re.compile(
    rf"^- \*\*(?P<rule_id>{RULE_ID}) \[(?P<level>{LEVEL})\]",
    re.MULTILINE,
)
CHECKLIST_ENTRY = re.compile(
    rf"^- \[ \] `(?P<rule_id>{RULE_ID})` \[(?P<level>{LEVEL})\].*?"
    r"Mechanization: (?P<mechanization>.*?)\. Configuration key:",
    re.MULTILINE,
)
RUNTIME_CORRESPONDENCE_HEADER = (
    "| New normative rule ID | Existing runtime rule ID | Correspondence |"
)
RUNTIME_CORRESPONDENCE_DIVIDER = "| --- | --- | --- |"
RUNTIME_CORRESPONDENCE_ROW = re.compile(
    rf"\| `(?P<canonical_id>{RULE_ID})` \| `(?P<runtime_id>[^`]+)` \| .+ \|"
)
IMPLEMENTATION_BY_PREFIX = {
    "automated": frozenset({"automated", "partial"}),
    "planned": frozenset({"planned", "partial"}),
    "manual-with-owner": frozenset({"manual-with-owner", "partial", "experimental"}),
}


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    reason: str

    def format(self, repository_root: Path) -> str:
        try:
            path = self.path.relative_to(repository_root).as_posix()
        except ValueError:
            path = str(self.path)
        return f"{path}:{self.line}: {self.reason}"


@dataclass(frozen=True)
class ChecklistEntry:
    level: str
    mechanization: str
    line: int


@dataclass(frozen=True)
class RuntimeCorrespondenceEntry:
    canonical_id: str
    line: int


def _read(path: Path, purpose: str) -> tuple[str | None, list[Finding]]:
    try:
        return path.read_text(encoding="utf-8"), []
    except OSError as error:
        return None, [Finding(path, 1, f"cannot read {purpose}: {error}")]


def _principle_levels(
    path: Path,
) -> tuple[dict[str, tuple[str, int]], list[Finding]]:
    content, findings = _read(path, "principle definitions")
    if content is None:
        return {}, findings

    definitions: dict[str, int] = {}
    for match in RULE_DEFINITION.finditer(content):
        identifier = match.group(1)
        line = line_number(content, match.start(1))
        if identifier in definitions:
            findings.append(
                Finding(path, line, f"duplicate principle rule ID {identifier}")
            )
        else:
            definitions[identifier] = line

    levels = {
        match.group("rule_id"): (
            match.group("level"),
            line_number(content, match.start("rule_id")),
        )
        for match in PRINCIPLE_LEVEL.finditer(content)
    }
    for identifier, line in definitions.items():
        if identifier not in levels:
            findings.append(
                Finding(path, line, f"principle rule {identifier} has no valid level")
            )
    return {key: value for key, value in levels.items() if key in definitions}, findings


def _checklist_entries(
    path: Path,
) -> tuple[dict[str, ChecklistEntry], list[Finding]]:
    content, findings = _read(path, "checklist")
    if content is None:
        return {}, findings

    entries: dict[str, ChecklistEntry] = {}
    for match in CHECKLIST_ENTRY.finditer(content):
        identifier = match.group("rule_id")
        line = line_number(content, match.start("rule_id"))
        if identifier in entries:
            findings.append(
                Finding(path, line, f"duplicate checklist rule ID {identifier}")
            )
            continue
        entries[identifier] = ChecklistEntry(
            level=match.group("level"),
            mechanization=match.group("mechanization"),
            line=line,
        )
    return entries, findings


def _runtime_correspondence_entries(
    path: Path,
) -> tuple[dict[str, RuntimeCorrespondenceEntry], list[Finding]]:
    content, findings = _read(path, "runtime rule-ID correspondence table")
    if content is None:
        return {}, findings

    heading = content.find("## Runtime rule-ID correspondence")
    if heading < 0:
        return {}, [Finding(path, 1, "Runtime rule-ID correspondence table is missing")]
    table = f"{RUNTIME_CORRESPONDENCE_HEADER}\n{RUNTIME_CORRESPONDENCE_DIVIDER}\n"
    rows_start = content.find(table, heading)
    if rows_start < 0:
        return {}, [
            Finding(
                path,
                line_number(content, heading),
                "runtime correspondence table is missing",
            )
        ]
    rows_start += len(table)
    rows_end = content.find("\n\n", rows_start)
    if rows_end < 0:
        rows_end = len(content)

    entries: dict[str, RuntimeCorrespondenceEntry] = {}
    offset = rows_start
    for raw_line in content[rows_start:rows_end].splitlines(keepends=True):
        line = raw_line.rstrip("\n")
        row_line = line_number(content, offset)
        offset += len(raw_line)
        match = RUNTIME_CORRESPONDENCE_ROW.fullmatch(line)
        if match is None:
            findings.append(
                Finding(path, row_line, "invalid runtime correspondence table row")
            )
            continue
        runtime_id = match.group("runtime_id")
        if runtime_id in entries:
            findings.append(
                Finding(
                    path, row_line, f"duplicate runtime correspondence ID {runtime_id}"
                )
            )
            continue
        entries[runtime_id] = RuntimeCorrespondenceEntry(
            canonical_id=match.group("canonical_id"),
            line=row_line,
        )
    return entries, findings


def _mechanization_prefix(mechanization: str) -> str | None:
    return next(
        (
            prefix
            for prefix in IMPLEMENTATION_BY_PREFIX
            if mechanization.startswith(prefix)
        ),
        None,
    )


def _benchmark_map_findings(
    registry: Registry,
    registry_path: Path,
    benchmark_map_path: Path,
) -> list[Finding]:
    content, findings = _read(benchmark_map_path, "benchmark principle-rule map")
    if content is None:
        return findings
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        return [
            Finding(
                benchmark_map_path,
                error.lineno,
                f"invalid benchmark principle-rule map: {error.msg}",
            )
        ]
    if not isinstance(payload, dict) or not isinstance(payload.get("rules"), dict):
        return [
            Finding(
                benchmark_map_path,
                1,
                'benchmark principle-rule map must contain a "rules" object',
            )
        ]

    alias_owners = {
        alias: rule for rule in registry.rules for alias in rule.runtime_aliases
    }
    map_source = benchmark_map_path.as_posix()
    registry_source = registry_path.as_posix()
    for runtime_id, recorded_principle in sorted(payload["rules"].items()):
        if not isinstance(recorded_principle, str):
            findings.append(
                Finding(
                    benchmark_map_path,
                    1,
                    f"{map_source} records a non-string principle for "
                    f"runtime ID {runtime_id}",
                )
            )
            continue
        runtime_check = registry.runtime_check(runtime_id)
        if runtime_check is not None:
            resolved_principle = runtime_check.principle
        else:
            rule = alias_owners.get(runtime_id) or registry.rule(runtime_id)
            if rule is None:
                findings.append(
                    Finding(
                        benchmark_map_path,
                        1,
                        f"runtime ID {runtime_id} in {map_source} is missing from "
                        f"registry {registry_source}",
                    )
                )
                continue
            resolved_principle = rule.principle
        if recorded_principle != resolved_principle:
            findings.append(
                Finding(
                    benchmark_map_path,
                    1,
                    f"runtime ID {runtime_id} maps to principle "
                    f"{recorded_principle} in {map_source}, but resolves to "
                    f"{resolved_principle} in {registry_source}",
                )
            )
    return findings


def validate(
    repository_root: Path = REPOSITORY_ROOT,
    registry_path: Path | None = None,
) -> list[Finding]:
    """Return registry drift and consistency findings."""

    repository_root = repository_root.resolve()
    registry_file = (registry_path or DEFAULT_REGISTRY_PATH).resolve()
    principles_path = repository_root / "docs" / "reference" / "principles.md"
    checklist_path = repository_root / "docs" / "reference" / "checklist.md"
    benchmark_map_path = repository_root / "benchmarks" / "principle-rule-map.json"

    try:
        registry = load_registry(registry_file)
    except RegistryError as error:
        return [Finding(registry_file, 1, f"invalid rule registry: {error}")]

    principles, findings = _principle_levels(principles_path)
    checklist, checklist_findings = _checklist_entries(checklist_path)
    correspondence, correspondence_findings = _runtime_correspondence_entries(
        principles_path
    )
    findings.extend(checklist_findings)
    findings.extend(correspondence_findings)
    findings.extend(
        _benchmark_map_findings(registry, registry_file, benchmark_map_path)
    )

    registry_rules = {rule.id: rule for rule in registry.rules}
    principle_ids = set(principles)
    registry_ids = set(registry_rules)
    for identifier in sorted(principle_ids - registry_ids):
        findings.append(
            Finding(
                principles_path,
                principles[identifier][1],
                f"principle rule {identifier} is missing from the registry",
            )
        )
    for identifier in sorted(registry_ids - principle_ids):
        findings.append(
            Finding(
                registry_file,
                1,
                f"registry rule {identifier} is undefined in principles.md",
            )
        )

    for identifier in sorted(registry_ids & principle_ids):
        rule = registry_rules[identifier]
        principle_level, principle_line = principles[identifier]
        if rule.level != principle_level:
            findings.append(
                Finding(
                    principles_path,
                    principle_line,
                    f"registry level for {identifier} is {rule.level}; "
                    f"principles.md declares {principle_level}",
                )
            )
        checklist_entry = checklist.get(identifier)
        if checklist_entry is None:
            findings.append(
                Finding(
                    checklist_path,
                    1,
                    f"registry rule {identifier} is missing from checklist.md",
                )
            )
            continue
        if rule.level != checklist_entry.level:
            findings.append(
                Finding(
                    checklist_path,
                    checklist_entry.line,
                    f"registry level for {identifier} is {rule.level}; "
                    f"checklist.md declares {checklist_entry.level}",
                )
            )
        prefix = _mechanization_prefix(checklist_entry.mechanization)
        if prefix is None:
            findings.append(
                Finding(
                    checklist_path,
                    checklist_entry.line,
                    f"checklist rule {identifier} has unknown Mechanization prefix",
                )
            )
        elif rule.implementation not in IMPLEMENTATION_BY_PREFIX[prefix]:
            allowed = ", ".join(sorted(IMPLEMENTATION_BY_PREFIX[prefix]))
            findings.append(
                Finding(
                    checklist_path,
                    checklist_entry.line,
                    f"registry implementation for {identifier} is "
                    f"{rule.implementation}; Mechanization prefix {prefix} "
                    f"allows {allowed}",
                )
            )

    alias_owners: dict[str, list[str]] = {}
    for rule in registry.rules:
        for alias in rule.runtime_aliases:
            alias_owners.setdefault(alias, []).append(rule.id)
    for alias, owners in sorted(alias_owners.items()):
        if len(owners) > 1:
            findings.append(
                Finding(
                    registry_file,
                    1,
                    f"runtime alias {alias} is assigned to multiple rules: "
                    + ", ".join(owners),
                )
            )

    # this legacy-table cross-check can be reversed once runtime metadata derives here.
    legacy_aliases = {
        runtime_id: (canonical_id, level)
        for runtime_id, (canonical_id, level) in RUNTIME_ALIAS_TABLE.items()
        if runtime_id != canonical_id
    }
    for alias in sorted(set(legacy_aliases) - set(alias_owners)):
        findings.append(
            Finding(
                registry_file,
                1,
                f"legacy runtime alias {alias} is missing from the registry",
            )
        )
    for alias, owners in sorted(alias_owners.items()):
        legacy = legacy_aliases.get(alias)
        if legacy is None:
            findings.append(
                Finding(
                    registry_file,
                    1,
                    f"registry runtime alias {alias} is absent from RUNTIME_ALIAS_TABLE",
                )
            )
            continue
        expected_target, expected_level = legacy
        for owner in owners:
            if owner != expected_target:
                findings.append(
                    Finding(
                        registry_file,
                        1,
                        f"runtime alias {alias} targets {owner}; "
                        f"RUNTIME_ALIAS_TABLE targets {expected_target}",
                    )
                )
            rule = registry_rules[owner]
            if rule.level != expected_level:
                findings.append(
                    Finding(
                        registry_file,
                        1,
                        f"runtime alias {alias} has level {rule.level}; "
                        f"RUNTIME_ALIAS_TABLE declares {expected_level}",
                    )
                )

    for runtime_id, correspondence_entry in sorted(correspondence.items()):
        legacy = legacy_aliases.get(runtime_id)
        if legacy is None:
            findings.append(
                Finding(
                    principles_path,
                    correspondence_entry.line,
                    f"runtime correspondence ID {runtime_id} is absent from "
                    "RUNTIME_ALIAS_TABLE",
                )
            )
            continue
        canonical_id, _level = legacy
        if correspondence_entry.canonical_id != canonical_id:
            findings.append(
                Finding(
                    principles_path,
                    correspondence_entry.line,
                    f"runtime correspondence ID {runtime_id} targets "
                    f"{correspondence_entry.canonical_id}; RUNTIME_ALIAS_TABLE "
                    f"targets {canonical_id}",
                )
            )
    for runtime_id in sorted(set(legacy_aliases) - set(correspondence)):
        findings.append(
            Finding(
                principles_path,
                1,
                f"registry runtime alias {runtime_id} is missing from the "
                "Runtime rule-ID correspondence table",
            )
        )

    legacy_runtime_checks = {
        runtime_id: level
        for runtime_id, (canonical_id, level) in RUNTIME_ALIAS_TABLE.items()
        if runtime_id == canonical_id
    }
    registry_runtime_checks = {
        runtime_check.id: runtime_check for runtime_check in registry.runtime_checks
    }
    for identifier in sorted(set(legacy_runtime_checks) - set(registry_runtime_checks)):
        findings.append(
            Finding(
                registry_file,
                1,
                f"runtime-only check {identifier} is missing from the registry",
            )
        )
    for identifier in sorted(set(registry_runtime_checks) - set(legacy_runtime_checks)):
        findings.append(
            Finding(
                registry_file,
                1,
                f"registry runtime-only check {identifier} is absent from "
                "RUNTIME_ALIAS_TABLE",
            )
        )
    for identifier in sorted(set(legacy_runtime_checks) & set(registry_runtime_checks)):
        registry_level = registry_runtime_checks[identifier].level
        legacy_level = legacy_runtime_checks[identifier]
        if registry_level != legacy_level:
            findings.append(
                Finding(
                    registry_file,
                    1,
                    f"runtime-only check {identifier} has level {registry_level}; "
                    f"RUNTIME_ALIAS_TABLE declares {legacy_level}",
                )
            )

    for rule in registry.rules:
        if not rule.exception_allowed and rule.exception_policy != "not-allowed":
            findings.append(
                Finding(
                    registry_file,
                    1,
                    f"rule {rule.id} disallows exceptions but has policy "
                    f"{rule.exception_policy!r}",
                )
            )
    exception_allowed = {rule.id for rule in registry.rules if rule.exception_allowed}
    if exception_allowed != set(EXCEPTION_ELIGIBLE_RULES):
        missing = sorted(set(EXCEPTION_ELIGIBLE_RULES) - exception_allowed)
        extra = sorted(exception_allowed - set(EXCEPTION_ELIGIBLE_RULES))
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("extra " + ", ".join(extra))
        findings.append(
            Finding(
                registry_file,
                1,
                "exception-eligible registry rules differ from "
                "EXCEPTION_ELIGIBLE_RULES: " + "; ".join(details),
            )
        )

    return sorted(findings, key=lambda item: (str(item.path), item.line, item.reason))


def main(
    repository_root: Path = REPOSITORY_ROOT,
    registry_path: Path | None = None,
) -> int:
    findings = validate(repository_root, registry_path)
    for finding in findings:
        print(finding.format(repository_root.resolve()), file=sys.stderr)
    if findings:
        return 1
    print("rule registry validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

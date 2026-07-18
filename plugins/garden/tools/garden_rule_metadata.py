"""Rule aliases, exception policy, and coverage derived from the registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from garden_registry import Registry, RegistryError, load_registry


def _register_runtime_id(
    table: dict[str, tuple[str, str]],
    runtime_id: str,
    target: tuple[str, str],
) -> None:
    existing = table.get(runtime_id)
    if existing is not None and existing != target:
        raise RegistryError(
            f"runtime ID {runtime_id!r} maps to both {existing!r} and {target!r}"
        )
    table[runtime_id] = target


def _build_runtime_alias_table(registry: Registry) -> dict[str, tuple[str, str]]:
    table: dict[str, tuple[str, str]] = {}
    for entry in registry.rules:
        for alias in entry.runtime_aliases:
            _register_runtime_id(table, alias, (entry.id, entry.level))
    for entry in registry.runtime_checks:
        _register_runtime_id(table, entry.id, (entry.id, entry.level))
    return table


_REGISTRY = load_registry()

# unmapped hard failures are required; unmapped advisories are default.
RUNTIME_ALIAS_TABLE: dict[str, tuple[str, str]] = _build_runtime_alias_table(_REGISTRY)

# sourced from the registry's exception_allowed field.
EXCEPTION_ELIGIBLE_RULES: frozenset[str] = frozenset(
    entry.id for entry in _REGISTRY.rules if entry.exception_allowed
)


def resolve_alias(runtime_id: str) -> tuple[str, str | None, str]:
    """Resolve one runtime ID to its canonical ID, alias, and level."""

    rule_id, level = RUNTIME_ALIAS_TABLE.get(runtime_id, (runtime_id, "REQUIRED"))
    runtime_alias = runtime_id if rule_id != runtime_id else None
    return rule_id, runtime_alias, level


def canonical_for(rule_or_alias: str) -> str:
    """Return the canonical rule ID for a runtime ID or canonical rule ID."""

    return resolve_alias(rule_or_alias)[0]


def is_exception_eligible(rule_or_alias: str) -> bool:
    """Return whether a rule permits a configuration exception."""

    return canonical_for(rule_or_alias) in EXCEPTION_ELIGIBLE_RULES


_CHECKLIST_PATTERN = re.compile(
    r"^- \[ \] `(?P<rule_id>[^`]+)`.*?"
    r"Mechanization: (?P<mechanization>.*?)\. Configuration key:",
    re.MULTILINE,
)


def parse_checklist_mechanization(path: Path | None = None) -> dict[str, str]:
    """Return checklist rule IDs and their full mechanization values."""

    if path is None:
        tools_dir = Path(__file__).resolve().parent
        path = tools_dir.parents[2] / "docs" / "reference" / "checklist.md"
    content = path.read_text(encoding="utf-8")
    return {
        match.group("rule_id"): match.group("mechanization")
        for match in _CHECKLIST_PATTERN.finditer(content)
    }


@dataclass(frozen=True)
class Coverage:
    implemented_rules: tuple[str, ...]
    manual_rules: tuple[str, ...]
    planned_rules: tuple[str, ...]
    not_applicable_rules: tuple[str, ...]


# coverage is registry-derived and disjoint. automated rules without runtime aliases
# may live outside garden_rules.py and remain excluded; partial runtime checks count as
# implemented instead of also appearing in the manual or planned lists.
COVERAGE = Coverage(
    implemented_rules=tuple(
        sorted({rule_id for rule_id, _level in RUNTIME_ALIAS_TABLE.values()})
    ),
    manual_rules=tuple(
        sorted(
            entry.id
            for entry in _REGISTRY.rules
            if entry.implementation in ("manual-with-owner", "experimental")
        )
    ),
    planned_rules=tuple(
        sorted(
            entry.id for entry in _REGISTRY.rules if entry.implementation == "planned"
        )
    ),
    not_applicable_rules=(),
)

"""Rule aliases, normative levels, and report coverage metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# unmapped hard failures are required; unmapped advisories are default.
RUNTIME_ALIAS_TABLE: dict[str, tuple[str, str]] = {
    "A-colocated-tests": ("A-LOC-004", "DEFAULT"),
    "D-project-scan-limit": ("D-project-scan-limit", "REQUIRED"),
    "N-CONFIG-INVALID": ("N-CONFIG-INVALID", "REQUIRED"),
    "N-CONTEXT-MISSING": ("N-CONTEXT-MISSING", "REQUIRED"),
    "N-LEGACY-NAMING-REGISTRY": ("N-LEGACY-NAMING-REGISTRY", "DEFAULT"),
    "N-NAMING-DUPLICATE-CANONICAL": (
        "N-NAMING-DUPLICATE-CANONICAL",
        "REQUIRED",
    ),
    "N-NAMING-DUPLICATE-CONCEPT": (
        "N-NAMING-DUPLICATE-CONCEPT",
        "REQUIRED",
    ),
    "N-NAMING-EMPTY-REGISTRY": ("N-NAMING-EMPTY-REGISTRY", "REQUIRED"),
    "N-NAMING-INVALID-ENTRY": ("N-NAMING-INVALID-ENTRY", "REQUIRED"),
    "N-NAMING-MISSING": ("N-NAMING-MISSING", "REQUIRED"),
    "N-context-budget": ("N-KNOW-005", "DEFAULT"),
    "N-context-scan-limit": ("N-context-scan-limit", "REQUIRED"),
    "R-component-contract": ("R-REPL-001", "REQUIRED"),
    "R-contract-scan-limit": ("R-contract-scan-limit", "REQUIRED"),
    "R-contract-version": ("R-REPL-002", "REQUIRED"),
}


def resolve_alias(runtime_id: str) -> tuple[str, str | None, str]:
    """Resolve one runtime ID to its canonical ID, alias, and level."""

    rule_id, level = RUNTIME_ALIAS_TABLE.get(runtime_id, (runtime_id, "REQUIRED"))
    runtime_alias = runtime_id if rule_id != runtime_id else None
    return rule_id, runtime_alias, level


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


# doc-declared automated checks may live outside garden_rules.py and are excluded.
#
# implemented_rules and manual_rules/planned_rules are not disjoint sets.
# R-REPL-001, R-REPL-002, A-LOC-004, and N-KNOW-005 appear in both: the
# checklist still records their full mechanization as manual or planned,
# while RUNTIME_ALIAS_TABLE already runs an approximate legacy heuristic
# check for them (contract presence, contract version, colocated tests,
# context budget) that predates and does not satisfy the checklist's
# mechanization criteria. The overlap marks partial mechanization, not a
# duplicate or an error. A canonical machine-readable rule registry with
# an explicit "partial" implementation status is planned to replace this
# derived-from-two-sources approximation.
COVERAGE = Coverage(
    implemented_rules=tuple(
        sorted({rule_id for rule_id, _level in RUNTIME_ALIAS_TABLE.values()})
    ),
    manual_rules=(
        "A-LOC-001",
        "A-LOC-005",
        "A-LOC-006",
        "D-VER-001",
        "D-VER-004",
        "D-VER-005",
        "D-VER-007",
        "D-VER-008",
        "E-EXPL-002",
        "E-EXPL-004",
        "E-EXPL-006",
        "G-DISC-002",
        "G-DISC-005",
        "G-DISC-006",
        "N-KNOW-001",
        "N-KNOW-002",
        "N-KNOW-004",
        "N-KNOW-007",
        "N-KNOW-008",
        "R-REPL-001",
        "R-REPL-003",
        "R-REPL-004",
        "R-REPL-005",
        "R-REPL-006",
        "R-REPL-007",
        "R-REPL-008",
    ),
    planned_rules=(
        "A-LOC-002",
        "A-LOC-003",
        "A-LOC-004",
        "D-VER-003",
        "D-VER-006",
        "E-EXPL-001",
        "E-EXPL-003",
        "E-EXPL-005",
        "G-DISC-001",
        "G-DISC-003",
        "G-DISC-004",
        "N-KNOW-005",
        "R-REPL-002",
    ),
    not_applicable_rules=(),
)

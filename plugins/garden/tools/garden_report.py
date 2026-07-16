"""Finding definitions and deterministic project report assembly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from garden_rule_metadata import COVERAGE


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    path: str
    message: str
    rule_id: str = ""
    runtime_alias: str | None = None
    level: str = "DEFAULT"
    state: str = "fail"
    evidence: tuple[str, ...] = ()
    remediation: str | None = None
    confidence: str | None = None


def build_project_report(
    root: Path,
    active: bool,
    findings: Iterable[Finding],
    *,
    complete: bool = True,
    config_path: str | None = None,
    config_schema_version: int | None = None,
    config_valid: bool = True,
    exceptions: Iterable[dict[str, object]] = (),
) -> dict[str, object]:
    unique = list(
        {
            (item.severity, item.rule, item.path, item.message): item
            for item in findings
        }.values()
    )
    complete = complete and not any(
        item.state == "unknown" and item.severity == "error" for item in unique
    )
    serialized_findings = [
        {
            "rule_id": item.rule_id or item.rule,
            "runtime_alias": item.runtime_alias,
            "level": item.level,
            "severity": item.severity,
            "state": item.state,
            "path": item.path,
            "message": item.message,
            "evidence": list(item.evidence),
            "remediation": item.remediation,
            "confidence": item.confidence,
            "rule": item.rule,
        }
        for item in unique
    ]
    # suppressed findings stay visible but are excluded from actionable counts.
    active_findings = [item for item in unique if item.state != "suppressed"]
    # absent config context is represented by null path/schema and valid=true.
    return {
        "schema_version": 2,
        "scope": "deterministic-structural-inspection",
        "active": active,
        "complete": complete,
        "root": str(root),
        "configuration": {
            "path": config_path,
            "schema_version": config_schema_version,
            "valid": config_valid,
        },
        "coverage": {
            "implemented_rules": list(COVERAGE.implemented_rules),
            "manual_rules": list(COVERAGE.manual_rules),
            "planned_rules": list(COVERAGE.planned_rules),
            "not_applicable_rules": list(COVERAGE.not_applicable_rules),
        },
        "exceptions": list(exceptions),
        "findings": serialized_findings,
        "summary": {
            "errors": sum(item.severity == "error" for item in active_findings),
            "warnings": sum(item.severity == "warning" for item in active_findings),
            "advisories": sum(item.severity == "advisory" for item in active_findings),
            "unknown": sum(item.state == "unknown" for item in unique),
            "suppressed": sum(item.state == "suppressed" for item in unique),
        },
    }

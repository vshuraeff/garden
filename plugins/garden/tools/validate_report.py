#!/usr/bin/env -S uv run --no-project
"""Validate a deterministic structural inspection report."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


TOP_LEVEL_FIELDS = (
    "schema_version",
    "scope",
    "active",
    "complete",
    "root",
    "configuration",
    "coverage",
    "exceptions",
    "findings",
    "summary",
)
CONFIGURATION_FIELDS = ("path", "schema_version", "valid")
COVERAGE_FIELDS = (
    "implemented_rules",
    "manual_rules",
    "planned_rules",
    "not_applicable_rules",
)
EXCEPTION_FIELDS = ("rule_id", "paths", "reason", "owner", "review_after")
FINDING_FIELDS = (
    "rule_id",
    "runtime_alias",
    "level",
    "severity",
    "state",
    "path",
    "message",
    "evidence",
    "remediation",
    "confidence",
)
SUMMARY_FIELDS = ("errors", "warnings", "advisories", "unknown", "suppressed")
LEVELS = frozenset({"REQUIRED", "DEFAULT", "EXPERIMENTAL"})
SEVERITIES = frozenset({"error", "warning", "advisory", "information"})
STATES = frozenset({"pass", "fail", "not-applicable", "unknown", "suppressed"})


@dataclass(frozen=True)
class Finding:
    path: Path
    field: str
    reason: str

    def format(self) -> str:
        return f"{self.path}: {self.field}: {self.reason}"


def _field_path(parent: str, field: str) -> str:
    return f"{parent}.{field}" if parent else field


def _require_fields(
    report_path: Path,
    value: dict[str, object],
    location: str,
    required: tuple[str, ...],
) -> list[Finding]:
    return [
        Finding(
            report_path,
            _field_path(location, field),
            "missing required field",
        )
        for field in required
        if field not in value
    ]


def _exact_key_findings(
    report_path: Path,
    value: dict[str, object],
    location: str,
    required: tuple[str, ...],
) -> list[Finding]:
    findings = _require_fields(report_path, value, location, required)
    expected = set(required)
    findings.extend(
        Finding(report_path, _field_path(location, field), "unexpected field")
        for field in sorted(set(value) - expected)
    )
    return findings


def _string_list_findings(
    report_path: Path, value: object, location: str
) -> list[Finding]:
    if not isinstance(value, list):
        return [Finding(report_path, location, "must be an array of strings")]
    return [
        Finding(report_path, f"{location}[{index}]", "must be a string")
        for index, item in enumerate(value)
        if not isinstance(item, str)
    ]


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_configuration(report_path: Path, value: object) -> list[Finding]:
    location = "configuration"
    if not isinstance(value, dict):
        return [Finding(report_path, location, "must be an object")]

    findings = _require_fields(report_path, value, location, CONFIGURATION_FIELDS)
    path_value = value.get("path")
    if "path" in value and path_value is not None and not isinstance(path_value, str):
        findings.append(
            Finding(report_path, "configuration.path", "must be a string or null")
        )
    schema_version = value.get("schema_version")
    if (
        "schema_version" in value
        and schema_version is not None
        and not _is_integer(schema_version)
    ):
        findings.append(
            Finding(
                report_path,
                "configuration.schema_version",
                "must be an integer or null",
            )
        )
    if "valid" in value and not isinstance(value.get("valid"), bool):
        findings.append(
            Finding(report_path, "configuration.valid", "must be a boolean")
        )
    return findings


def _validate_coverage(report_path: Path, value: object) -> list[Finding]:
    location = "coverage"
    if not isinstance(value, dict):
        return [Finding(report_path, location, "must be an object")]

    findings = _exact_key_findings(report_path, value, location, COVERAGE_FIELDS)
    for field in COVERAGE_FIELDS:
        if field in value:
            findings.extend(
                _string_list_findings(report_path, value[field], f"coverage.{field}")
            )
    return findings


def _validate_exceptions(report_path: Path, value: object) -> list[Finding]:
    location = "exceptions"
    if not isinstance(value, list):
        return [Finding(report_path, location, "must be an array")]

    findings: list[Finding] = []
    for index, item in enumerate(value):
        item_location = f"exceptions[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding(report_path, item_location, "must be an object"))
            continue
        findings.extend(
            _require_fields(report_path, item, item_location, EXCEPTION_FIELDS)
        )
        for field in ("rule_id", "reason", "owner", "review_after"):
            if field in item and not isinstance(item[field], str):
                findings.append(
                    Finding(
                        report_path,
                        _field_path(item_location, field),
                        "must be a string",
                    )
                )
        if "paths" in item:
            findings.extend(
                _string_list_findings(
                    report_path, item["paths"], f"{item_location}.paths"
                )
            )
    return findings


def _validate_findings(report_path: Path, value: object) -> list[Finding]:
    location = "findings"
    if not isinstance(value, list):
        return [Finding(report_path, location, "must be an array")]

    findings: list[Finding] = []
    for index, item in enumerate(value):
        item_location = f"findings[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding(report_path, item_location, "must be an object"))
            continue
        findings.extend(
            _require_fields(report_path, item, item_location, FINDING_FIELDS)
        )
        for field in ("rule_id", "path", "message"):
            if field in item and not isinstance(item[field], str):
                findings.append(
                    Finding(
                        report_path,
                        _field_path(item_location, field),
                        "must be a string",
                    )
                )
        for field in ("runtime_alias", "remediation", "confidence"):
            if (
                field in item
                and item[field] is not None
                and not isinstance(item[field], str)
            ):
                findings.append(
                    Finding(
                        report_path,
                        _field_path(item_location, field),
                        "must be a string or null",
                    )
                )
        for field, allowed in (
            ("level", LEVELS),
            ("severity", SEVERITIES),
            ("state", STATES),
        ):
            if field in item and (
                not isinstance(item[field], str) or item[field] not in allowed
            ):
                findings.append(
                    Finding(
                        report_path,
                        _field_path(item_location, field),
                        f"must be one of {', '.join(sorted(allowed))}",
                    )
                )
        if "evidence" in item:
            findings.extend(
                _string_list_findings(
                    report_path, item["evidence"], f"{item_location}.evidence"
                )
            )
        if "rule" in item and not isinstance(item["rule"], str):
            findings.append(
                Finding(
                    report_path,
                    f"{item_location}.rule",
                    "must be a string when present",
                )
            )
    return findings


def _validate_summary(report_path: Path, value: object) -> list[Finding]:
    location = "summary"
    if not isinstance(value, dict):
        return [Finding(report_path, location, "must be an object")]

    findings = _exact_key_findings(report_path, value, location, SUMMARY_FIELDS)
    for field in SUMMARY_FIELDS:
        if field not in value:
            continue
        counter = value[field]
        if not _is_integer(counter) or counter < 0:
            findings.append(
                Finding(
                    report_path,
                    f"summary.{field}",
                    "must be a non-negative integer",
                )
            )
    return findings


def validate_report(path: Path) -> list[Finding]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [Finding(path, "$", f"cannot read report: {error}")]

    try:
        report = json.loads(content)
    except json.JSONDecodeError as error:
        return [Finding(path, "$", f"invalid JSON: {error}")]
    if not isinstance(report, dict):
        return [Finding(path, "$", "must be an object")]

    findings = _require_fields(path, report, "", TOP_LEVEL_FIELDS)

    schema_version = report.get("schema_version")
    if "schema_version" in report and (
        not _is_integer(schema_version) or schema_version != 2
    ):
        findings.append(Finding(path, "schema_version", "must be integer 2"))
    if (
        "scope" in report
        and report.get("scope") != "deterministic-structural-inspection"
    ):
        findings.append(
            Finding(
                path,
                "scope",
                "must be 'deterministic-structural-inspection'",
            )
        )
    for field in ("active", "complete"):
        if field in report and not isinstance(report[field], bool):
            findings.append(Finding(path, field, "must be a boolean"))
    if "root" in report and not isinstance(report["root"], str):
        findings.append(Finding(path, "root", "must be a string"))

    if "configuration" in report:
        findings.extend(_validate_configuration(path, report["configuration"]))
    if "coverage" in report:
        findings.extend(_validate_coverage(path, report["coverage"]))
    if "exceptions" in report:
        findings.extend(_validate_exceptions(path, report["exceptions"]))
    if "findings" in report:
        findings.extend(_validate_findings(path, report["findings"]))
    if "summary" in report:
        findings.extend(_validate_summary(path, report["summary"]))
    return findings


def main() -> int:
    arguments = sys.argv[1:]
    if len(arguments) != 1:
        path = Path(arguments[0]) if arguments else Path("<report>")
        finding = Finding(path, "$", "expected exactly one report path")
        print(finding.format(), file=sys.stderr)
        return 1

    findings = validate_report(Path(arguments[0]))
    for finding in findings:
        print(finding.format(), file=sys.stderr)
    if findings:
        return 1
    print("report validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

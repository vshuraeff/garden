from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from validate_report import main, validate_report  # noqa: E402


class ReportValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def valid_report(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "scope": "deterministic-structural-inspection",
            "active": True,
            "complete": True,
            "root": ".",
            "configuration": {
                "path": ".garden.toml",
                "schema_version": 1,
                "valid": True,
            },
            "coverage": {
                "implemented_rules": ["R-REPL-002"],
                "manual_rules": ["D-VER-005"],
                "planned_rules": ["G-DISC-001"],
                "not_applicable_rules": [],
            },
            "exceptions": [
                {
                    "rule_id": "R-REPL-002",
                    "paths": ["example/CONTRACT.md"],
                    "reason": "migration",
                    "owner": "platform",
                    "review_after": "2099-01-01",
                }
            ],
            "findings": [
                {
                    "rule_id": "R-REPL-002",
                    "runtime_alias": "R-contract-version",
                    "level": "REQUIRED",
                    "severity": "error",
                    "state": "fail",
                    "path": "example/CONTRACT.md",
                    "message": "contract misses version",
                    "evidence": ["first non-empty line is not a version"],
                    "remediation": "add a version line",
                    "confidence": "high",
                    "rule": "R-contract-version",
                }
            ],
            "summary": {
                "errors": 1,
                "warnings": 0,
                "advisories": 0,
                "unknown": 0,
                "suppressed": 0,
            },
        }

    def write_report(self, report: object) -> Path:
        path = self.root / "report.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def assert_invalid(self, report: object, field: str) -> None:
        findings = validate_report(self.write_report(report))

        self.assertNotEqual([], findings)
        self.assertIn(field, [finding.field for finding in findings])

    def test_valid_report_passes_validation_and_cli(self) -> None:
        path = self.write_report(self.valid_report())

        self.assertEqual([], validate_report(path))
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(sys, "argv", ["validate_report.py", str(path)]),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = main()

        self.assertEqual(0, code)
        self.assertEqual("report validation passed\n", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_missing_required_top_level_key_is_rejected(self) -> None:
        report = self.valid_report()
        del report["complete"]

        self.assert_invalid(report, "complete")

    def test_invalid_finding_state_is_rejected(self) -> None:
        report = self.valid_report()
        report["findings"][0]["state"] = "incomplete"

        self.assert_invalid(report, "findings[0].state")

    def test_invalid_finding_severity_is_rejected(self) -> None:
        report = self.valid_report()
        report["findings"][0]["severity"] = "critical"

        self.assert_invalid(report, "findings[0].severity")

    def test_negative_summary_counter_is_rejected(self) -> None:
        report = self.valid_report()
        report["summary"]["errors"] = -1

        self.assert_invalid(report, "summary.errors")

    def test_schema_version_one_is_rejected(self) -> None:
        report = self.valid_report()
        report["schema_version"] = 1

        self.assert_invalid(report, "schema_version")


if __name__ == "__main__":
    unittest.main()

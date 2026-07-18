from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from garden_core import inspect_file, inspect_project  # noqa: E402
from garden_registry import load_registry  # noqa: E402
from garden_report import Finding, build_project_report  # noqa: E402
from garden_rule_metadata import COVERAGE, EXCEPTION_ELIGIBLE_RULES  # noqa: E402
from garden_scanner import ScanLimitExceeded  # noqa: E402


class GardenReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        (self.root / "naming-registry.txt").write_text(
            "orders: orders\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_report_has_v2_shape_and_legacy_finding_identity(self) -> None:
        contract = self.root / "orders" / "CONTRACT.md"
        contract.parent.mkdir()
        contract.write_text("# Missing version\n", encoding="utf-8")

        finding = inspect_file(contract)[0]
        self.assertEqual("R-contract-version", finding.rule)
        self.assertEqual("R-REPL-002", finding.rule_id)
        self.assertEqual("R-contract-version", finding.runtime_alias)
        self.assertEqual("REQUIRED", finding.level)
        self.assertEqual("fail", finding.state)

        exception = {
            "rule_id": "R-REPL-002",
            "paths": ["orders/CONTRACT.md"],
            "reason": "migration",
            "owner": "platform",
            "review_after": "2026-08-01",
        }
        report = build_project_report(
            self.root,
            True,
            [finding],
            config_path=".garden.toml",
            config_schema_version=2,
            config_valid=True,
            exceptions=[exception],
        )

        self.assertEqual(2, report["schema_version"])
        self.assertEqual("deterministic-structural-inspection", report["scope"])
        self.assertEqual(
            {"path", "schema_version", "valid"}, set(report["configuration"])
        )
        self.assertEqual(
            {"roots", "exceeded_budget", "missing_roots", "errors"},
            set(report["scan"]),
        )
        self.assertEqual(
            {
                "implemented_rules",
                "manual_rules",
                "planned_rules",
                "not_applicable_rules",
            },
            set(report["coverage"]),
        )
        self.assertEqual(1, len(report["exceptions"]))
        self.assertEqual(
            exception,
            {key: report["exceptions"][0][key] for key in exception},
        )
        self.assertEqual(
            {"errors", "warnings", "advisories", "unknown", "suppressed"},
            set(report["summary"]),
        )

        serialized = report["findings"][0]
        self.assertEqual(
            {
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
                "rule",
            },
            set(serialized),
        )
        self.assertEqual("R-contract-version", serialized["rule"])
        self.assertEqual("R-REPL-002", serialized["rule_id"])
        self.assertEqual("R-contract-version", serialized["runtime_alias"])
        self.assertEqual("REQUIRED", serialized["level"])
        self.assertEqual("fail", serialized["state"])

    def test_configured_exception_suppresses_only_matching_finding(self) -> None:
        (self.root / ".garden.toml").write_text(
            "schema_version = 2\n"
            "\n"
            "[scan]\n"
            'include = ["**/*.py"]\n'
            "\n"
            "[capabilities]\n"
            'strategy = "children"\n'
            'roots = ["src"]\n'
            "depth = 1\n"
            "\n"
            "[tests]\n"
            'patterns = ["**/test_*.py"]\n'
            'association = "same-capability"\n'
            "\n"
            "[documentation]\n"
            "root_context_required = false\n"
            "\n"
            "[[exceptions]]\n"
            'rule_id = "A-LOC-004"\n'
            'paths = ["src/matched/**"]\n'
            'reason = "fixture exception"\n'
            'owner = "tests"\n'
            'review_after = "on-rule-change"\n',
            encoding="utf-8",
        )
        for capability in ("matched", "active"):
            capability_root = self.root / "src" / capability
            capability_root.mkdir(parents=True)
            (capability_root / "CONTRACT.md").write_text(
                "# Contract\n", encoding="utf-8"
            )
            (capability_root / "handler.py").write_text(
                "def handle() -> None:\n    pass\n", encoding="utf-8"
            )

        file_findings = inspect_file(self.root / "src" / "matched" / "handler.py")
        report = inspect_project(self.root)
        findings = {finding["path"]: finding for finding in report["findings"]}

        self.assertEqual(["suppressed"], [finding.state for finding in file_findings])
        self.assertEqual("suppressed", findings["src/matched/handler.py"]["state"])
        self.assertEqual("fail", findings["src/active/handler.py"]["state"])
        self.assertEqual("advisory", findings["src/matched/handler.py"]["severity"])
        self.assertEqual("A-LOC-004", findings["src/matched/handler.py"]["rule_id"])
        self.assertEqual(
            "A-colocated-tests",
            findings["src/matched/handler.py"]["runtime_alias"],
        )
        self.assertEqual(
            {
                "rule_id": "A-LOC-004",
                "paths": ["src/matched/**"],
                "reason": "fixture exception",
                "owner": "tests",
                "review_after": "on-rule-change",
                "applied": True,
                "matched_findings": 1,
                "expired": False,
            },
            report["exceptions"][0],
        )
        self.assertEqual(1, report["summary"]["advisories"])
        self.assertEqual(1, report["summary"]["suppressed"])

    def test_configured_exception_does_not_suppress_unknown_finding(self) -> None:
        (self.root / ".garden.toml").write_text(
            "schema_version = 2\n"
            "\n"
            "[documentation]\n"
            "root_context_required = false\n"
            "\n"
            "[[boundaries]]\n"
            'path = "src/api"\n'
            'kind = "public-api"\n'
            'owner = "api-team"\n'
            'required_evidence = ["contract-tests"]\n'
            "\n"
            "[[exceptions]]\n"
            'rule_id = "R-REPL-001"\n'
            'paths = ["src/api"]\n'
            'reason = "manual review"\n'
            'owner = "tests"\n'
            'review_after = "on-rule-change"\n',
            encoding="utf-8",
        )

        report = inspect_project(self.root)

        self.assertEqual("unknown", report["findings"][0]["state"])
        self.assertEqual(0, report["summary"]["suppressed"])
        self.assertEqual(1, report["summary"]["unknown"])
        self.assertEqual(1, report["exceptions"][0]["matched_findings"])
        self.assertIs(report["exceptions"][0]["applied"], False)

    def test_real_report_uses_default_config_context_and_exact_coverage(self) -> None:
        report = inspect_project(self.root)
        expected_coverage = {
            "implemented_rules": list(COVERAGE.implemented_rules),
            "manual_rules": list(COVERAGE.manual_rules),
            "planned_rules": list(COVERAGE.planned_rules),
            "not_applicable_rules": list(COVERAGE.not_applicable_rules),
        }

        self.assertEqual(
            {"path": None, "schema_version": None, "valid": True},
            report["configuration"],
        )
        self.assertEqual(expected_coverage, report["coverage"])
        self.assertEqual([], report["exceptions"])

    def test_unknown_state_and_explicit_incompleteness_are_preserved(self) -> None:
        unknown = Finding(
            severity="error",
            rule="D-project-scan-limit",
            path=".",
            message="scan stopped",
            state="unknown",
        )
        unknown_report = build_project_report(self.root, True, [unknown])
        forced_incomplete = build_project_report(
            self.root,
            True,
            [Finding("advisory", "legacy", ".", "advice")],
            complete=False,
        )

        self.assertFalse(unknown_report["complete"])
        self.assertEqual(1, unknown_report["summary"]["unknown"])
        self.assertFalse(forced_incomplete["complete"])

    def test_advisory_unknown_does_not_make_report_incomplete(self) -> None:
        unknown = Finding(
            severity="advisory",
            rule="R-boundary-evidence-review",
            path=".",
            message="manual verification is required",
            state="unknown",
        )

        report = build_project_report(self.root, True, [unknown])

        self.assertTrue(report["complete"])
        self.assertEqual(1, report["summary"]["unknown"])

    def test_scan_limit_severity_tracks_budget_and_always_marks_incomplete(
        self,
    ) -> None:
        (self.root / ".garden.toml").write_text(
            "schema_version = 1\n[documentation]\nroot_context_required = false\n",
            encoding="utf-8",
        )
        cases = (
            ("seconds", "advisory"),
            ("entries", "error"),
            (None, "error"),
        )
        for budget, severity in cases:
            with self.subTest(budget=budget):
                error = ScanLimitExceeded("forced project limit", budget=budget)
                with patch("garden_scanner._walk_files", side_effect=error):
                    report = inspect_project(self.root)

                finding = next(
                    item
                    for item in report["findings"]
                    if item["rule"] == "D-project-scan-limit"
                )
                self.assertEqual(severity, finding["severity"])
                self.assertEqual("unknown", finding["state"])
                self.assertFalse(report["complete"])
                self.assertEqual(budget, report["scan"]["exceeded_budget"])
                self.assertEqual(["forced project limit"], report["scan"]["errors"])

    def test_missing_configured_scan_root_is_one_error_finding(self) -> None:
        (self.root / ".garden.toml").write_text(
            "schema_version = 1\n"
            '[scan]\nroots = ["src", "missing"]\n'
            "[documentation]\nroot_context_required = false\n",
            encoding="utf-8",
        )
        (self.root / "src").mkdir()

        report = inspect_project(self.root)

        findings = [
            item for item in report["findings"] if item["rule"] == "D-scan-root-missing"
        ]
        self.assertEqual(1, len(findings))
        self.assertEqual("error", findings[0]["severity"])
        self.assertEqual("unknown", findings[0]["state"])
        self.assertEqual("missing", findings[0]["path"])
        self.assertEqual("D-scan-root-missing", findings[0]["rule_id"])
        self.assertIsNone(findings[0]["runtime_alias"])
        self.assertEqual("REQUIRED", findings[0]["level"])
        self.assertEqual(["missing"], report["scan"]["missing_roots"])

    def test_project_and_file_findings_agree_for_nested_contract(self) -> None:
        (self.root / ".garden.toml").write_text(
            "schema_version = 2\n"
            '[scan]\nroots = ["src"]\ninclude = ["**/*.py"]\n'
            "[capabilities]\n"
            'strategy = "children"\nroots = ["src"]\ndepth = 1\n'
            "[[boundaries]]\n"
            'path = "src/orders"\n'
            'kind = "public-api"\n'
            'owner = "orders-team"\n'
            'versioning = "semver"\n'
            "[documentation]\nroot_context_required = false\n",
            encoding="utf-8",
        )
        artifact = self.root / "src" / "orders" / "nested" / "CONTRACT.md"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("# missing version\n", encoding="utf-8")
        source = self.root / "src" / "orders" / "handler.py"
        source.write_text("pass\n", encoding="utf-8")

        file_pairs = {
            (finding.rule, finding.severity)
            for finding in inspect_file(artifact, self.root)
        }
        report = inspect_project(self.root)
        project_pairs = {
            (finding["rule"], finding["severity"])
            for finding in report["findings"]
            if finding["path"] == "src/orders/nested/CONTRACT.md"
        }

        self.assertTrue(file_pairs)
        self.assertIn("R-contract-version", {rule for rule, _ in file_pairs})
        self.assertEqual(file_pairs, project_pairs)

    def test_inactive_project_is_incomplete(self) -> None:
        inactive = self.root / "inactive"
        inactive.mkdir()

        report = inspect_project(inactive)

        self.assertFalse(report["active"])
        self.assertFalse(report["complete"])

    def test_dedupe_uses_legacy_finding_identity(self) -> None:
        first = Finding("error", "runtime", "path", "message", rule_id="first")
        second = Finding("error", "runtime", "path", "message", rule_id="second")
        report = build_project_report(self.root, True, [first, second])

        self.assertEqual(1, len(report["findings"]))

    def test_coverage_matches_registry_implementation_status(self) -> None:
        registry = load_registry()
        partial_rules = {
            entry.id for entry in registry.rules if entry.implementation == "partial"
        }
        implemented_rules = set(COVERAGE.implemented_rules)
        manual_rules = set(COVERAGE.manual_rules)
        planned_rules = set(COVERAGE.planned_rules)

        self.assertEqual(
            manual_rules,
            {
                entry.id
                for entry in registry.rules
                if entry.implementation in ("manual-with-owner", "experimental")
            },
        )
        self.assertEqual(
            planned_rules,
            {entry.id for entry in registry.rules if entry.implementation == "planned"},
        )
        self.assertEqual(
            {"A-LOC-004", "N-KNOW-005", "R-REPL-001", "R-REPL-002"},
            partial_rules,
        )
        self.assertTrue(partial_rules <= implemented_rules)
        self.assertTrue(partial_rules.isdisjoint(manual_rules | planned_rules))
        self.assertTrue(manual_rules.isdisjoint(planned_rules))
        self.assertTrue((manual_rules | planned_rules).isdisjoint(implemented_rules))

    def test_exception_eligible_rules_match_registry(self) -> None:
        registry = load_registry()

        self.assertEqual(
            frozenset({"A-LOC-004", "N-KNOW-005", "R-REPL-001", "R-REPL-002"}),
            EXCEPTION_ELIGIBLE_RULES,
        )
        self.assertEqual(
            frozenset(entry.id for entry in registry.rules if entry.exception_allowed),
            EXCEPTION_ELIGIBLE_RULES,
        )


if __name__ == "__main__":
    unittest.main()

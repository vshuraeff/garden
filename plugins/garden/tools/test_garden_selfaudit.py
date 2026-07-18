from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = TOOLS_DIR.parents[2]
sys.path.insert(0, str(TOOLS_DIR))

from garden_cli import main as garden_cli_main  # noqa: E402
from garden_core import find_project_activation, inspect_project  # noqa: E402
from garden_rule_metadata import COVERAGE  # noqa: E402


class GardenSelfAuditTests(unittest.TestCase):
    def run_cli(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = garden_cli_main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def write_exception_config(self, root: Path, review_after: str) -> None:
        (root / ".garden.toml").write_text(
            "schema_version = 1\n"
            "\n"
            "[project]\n"
            'type = "other"\n'
            "\n"
            "[documentation]\n"
            "root_context_required = false\n"
            "\n"
            "[[exceptions]]\n"
            'rule_id = "R-REPL-001"\n'
            'paths = ["."]\n'
            'reason = "test exception"\n'
            'owner = "tests"\n'
            f'review_after = "{review_after}"\n',
            encoding="utf-8",
        )

    def test_repository_root_is_active_from_its_config(self) -> None:
        activation = find_project_activation(REPOSITORY_ROOT)

        self.assertIsNotNone(activation)
        self.assertEqual(REPOSITORY_ROOT, activation.root)
        self.assertEqual("config", activation.kind)

    def test_repository_self_audit_meets_schema_v2_expectations(self) -> None:
        report = inspect_project(REPOSITORY_ROOT)

        self.assertEqual(2, report["schema_version"])
        self.assertEqual(
            "deterministic-structural-inspection",
            report["scope"],
        )
        self.assertIs(report["active"], True)
        self.assertIs(report["complete"], True)
        self.assertEqual(0, report["summary"]["errors"])
        self.assertEqual(0, report["summary"]["advisories"])
        self.assertGreater(report["summary"]["suppressed"], 0)

        today = date.today()
        expired_exceptions = []
        for exception in report["exceptions"]:
            try:
                review_after = date.fromisoformat(exception["review_after"])
            except (KeyError, TypeError, ValueError):
                continue
            if review_after < today:
                expired_exceptions.append(exception)
        self.assertEqual([], expired_exceptions)

        implemented_rules = report["coverage"]["implemented_rules"]
        self.assertTrue(implemented_rules)
        self.assertEqual(set(COVERAGE.implemented_rules), set(implemented_rules))
        self.assertTrue(report["coverage"]["manual_rules"])
        self.assertTrue(report["coverage"]["planned_rules"])

    def test_repository_strict_self_audit_passes(self) -> None:
        code, _, error = self.run_cli(["inspect", "--strict", str(REPOSITORY_ROOT)])

        self.assertEqual((0, ""), (code, error))

    def test_plain_inspect_reports_an_inactive_project_without_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = inspect_project(Path(directory))

        self.assertFalse(report["active"])
        self.assertFalse(report["complete"])
        self.assertEqual(0, report["summary"]["errors"])

    def test_strict_inspect_rejects_an_inactive_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plain_code, plain_output, plain_error = self.run_cli(["inspect", str(root)])
            strict_code, strict_output, strict_error = self.run_cli(
                ["inspect", "--strict", str(root)]
            )

        self.assertEqual((0, ""), (plain_code, plain_error))
        self.assertIn('"active": false', plain_output)
        self.assertIn('"complete": false', plain_output)
        self.assertEqual((1, ""), (strict_code, strict_error))
        self.assertIn('"active": false', strict_output)
        self.assertIn('"complete": false', strict_output)

    def test_strict_inspect_rejects_invalid_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".garden.toml").write_text(
                "schema_version = 1\nunknown = true\n", encoding="utf-8"
            )
            code, output, error = self.run_cli(["inspect", "--strict", str(root)])

        self.assertEqual((1, ""), (code, error))
        self.assertIn('"valid": false', output)

    def test_strict_inspect_rejects_incomplete_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "naming-registry.txt").write_text(
                "orders: orders\n", encoding="utf-8"
            )
            capability = root / "orders"
            capability.mkdir()
            for index in range(4):
                (capability / f"empty-{index}").mkdir()
            with patch("garden_core.MAX_SCAN_ENTRIES", 2):
                code, _, error = self.run_cli(["inspect", "--strict", str(root)])

        self.assertEqual((1, ""), (code, error))

    def test_strict_inspect_rejects_expired_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_exception_config(root, "2020-01-01")
            code, _, error = self.run_cli(["inspect", "--strict", str(root)])

        self.assertEqual((1, ""), (code, error))

    def test_strict_inspect_accepts_future_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_exception_config(root, "2099-01-01")
            code, _, error = self.run_cli(["inspect", "--strict", str(root)])

        self.assertEqual((0, ""), (code, error))

    def test_strict_inspect_rejects_invalid_review_after_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_exception_config(root, "not-a-date")
            code, output, error = self.run_cli(["inspect", "--strict", str(root)])

        self.assertEqual((1, ""), (code, error))
        self.assertIn('"valid": false', output)

    def test_strict_inspect_accepts_review_marker_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_exception_config(root, "on-rule-change")
            code, _, error = self.run_cli(["inspect", "--strict", str(root)])

        self.assertEqual((0, ""), (code, error))


if __name__ == "__main__":
    unittest.main()

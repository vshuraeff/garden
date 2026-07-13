from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TOOLS_DIR / "fixtures"
EXPECTED_ROOT = "<FIXTURE_ROOT>"
sys.path.insert(0, str(TOOLS_DIR))

from garden_core import (  # noqa: E402
    MAX_SCAN_ENTRIES,
    Finding,
    ScanLimitExceeded,
    inspect_file,
    inspect_project,
    route_prompt,
)


class ActiveProjectTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        (self.root / "naming-registry.txt").write_text(
            "orders: orders\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()


class FixtureRegressionTests(unittest.TestCase):
    def assert_fixture_report(self, name: str) -> None:
        fixture_dir = FIXTURES_DIR / name
        report = inspect_project(fixture_dir)
        expected = json.loads(
            (fixture_dir / "expected.json").read_text(encoding="utf-8")
        )
        if expected["active"]:
            self.assertEqual(fixture_dir.resolve(), Path(report["root"]))
        report["root"] = EXPECTED_ROOT
        self.assertEqual(expected, report)

    def test_flat_capabilities(self) -> None:
        self.assert_fixture_report("flat-capabilities")

    def test_src_layout(self) -> None:
        # known false positive, documented in docs/development/baseline.md, to be fixed in a later pr
        self.assert_fixture_report("src-layout")

    def test_monorepo(self) -> None:
        # known false positive, documented in docs/development/baseline.md, to be fixed in a later pr
        self.assert_fixture_report("monorepo")

    def test_library(self) -> None:
        # known false negative, documented in docs/development/baseline.md, to be fixed in a later pr
        self.assert_fixture_report("library")

    def test_config_heavy_project(self) -> None:
        # known false negative, documented in docs/development/baseline.md, to be fixed in a later pr
        self.assert_fixture_report("config-heavy-project")

    def test_inactive_project(self) -> None:
        self.assert_fixture_report("inactive-project")

    def test_false_positives(self) -> None:
        # known false positives, documented in docs/development/baseline.md, to be fixed in a later pr
        self.assert_fixture_report("false-positives")


class GoldenSchemaTests(ActiveProjectTestCase):
    def test_inspect_project_schema(self) -> None:
        source = self.root / "orders" / "handler.py"
        source.parent.mkdir()
        source.write_text("def handle() -> None:\n    pass\n", encoding="utf-8")

        report = inspect_project(self.root)

        self.assertEqual({"active", "root", "findings", "summary"}, set(report))
        summary = report["summary"]
        self.assertEqual({"errors", "advisories"}, set(summary))
        self.assertIsInstance(summary["errors"], int)
        self.assertIsInstance(summary["advisories"], int)
        findings = report["findings"]
        self.assertIsInstance(findings, list)
        for finding in findings:
            self.assertEqual({"severity", "rule", "path", "message"}, set(finding))
            for value in finding.values():
                self.assertIsInstance(value, str)

    def test_inspect_file_schema(self) -> None:
        source = self.root / "orders" / "handler.py"
        source.parent.mkdir()
        source.write_text("def handle() -> None:\n    pass\n", encoding="utf-8")

        findings = inspect_file(source)

        self.assertIsInstance(findings, list)
        for finding in findings:
            self.assertIsInstance(finding, Finding)
            self.assertIsInstance(finding.severity, str)
            self.assertIsInstance(finding.rule, str)
            self.assertIsInstance(finding.path, str)
            self.assertIsInstance(finding.message, str)

    def test_route_prompt_schema(self) -> None:
        result = route_prompt("Run a GARDEN audit", self.root)

        self.assertIsInstance(result, list)
        for skill in result:
            self.assertIsInstance(skill, str)


class RoutePromptGoldenTests(ActiveProjectTestCase):
    def test_golden_triggers(self) -> None:
        cases = {
            "Bootstrap this project": ["garden:bootstrap"],
            "Help me retrofit this legacy app": ["garden:retrofit"],
            "Run a GARDEN audit": ["garden:audit"],
            "Review this GARDEN PR": ["garden:review"],
            "Explain this function": [],
        }

        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                self.assertEqual(expected, route_prompt(prompt, self.root))


class SecurityRegressionTests(unittest.TestCase):
    def test_project_scan_does_not_follow_external_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            outside = workspace / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "naming-registry.txt").write_text(
                "orders: orders\n", encoding="utf-8"
            )
            source = root / "orders" / "handler.py"
            source.parent.mkdir()
            source.write_text("def handle() -> None:\n    pass\n", encoding="utf-8")
            (outside / "handler.py").write_text(
                "def outside() -> None:\n    pass\n", encoding="utf-8"
            )
            (root / "external").symlink_to(outside, target_is_directory=True)

            report = inspect_project(root)

        paths = [finding["path"] for finding in report["findings"]]
        self.assertNotIn("external/handler.py", paths)

    def test_project_scan_reports_entry_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "naming-registry.txt").write_text(
                "orders: orders\n", encoding="utf-8"
            )
            capability = root / "orders"
            capability.mkdir()
            for index in range(4):
                (capability / f"empty-{index}").mkdir()

            budget = 2
            self.assertLess(budget, MAX_SCAN_ENTRIES)
            with patch("garden_core.MAX_SCAN_ENTRIES", budget):
                report = inspect_project(root)

        self.assertTrue(issubclass(ScanLimitExceeded, RuntimeError))
        findings = report["findings"]
        self.assertIn("D-project-scan-limit", [finding["rule"] for finding in findings])
        scan_limit = next(
            finding for finding in findings if finding["rule"] == "D-project-scan-limit"
        )
        self.assertEqual("error", scan_limit["severity"])


if __name__ == "__main__":
    unittest.main()

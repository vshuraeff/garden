from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from garden_core import (  # noqa: E402
    CONTEXT_LINE_BUDGET,
    find_project_root,
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


class GardenModuleTests(unittest.TestCase):
    def test_internal_modules_import_cleanly(self) -> None:
        for module_name in (
            "garden_report",
            "garden_paths",
            "garden_scanner",
            "garden_rules",
        ):
            with self.subTest(module=module_name):
                self.assertIsNotNone(importlib.import_module(module_name))

    def test_modules_import_fresh_without_cycles(self) -> None:
        for module_name in (
            "garden_core",
            "garden_report",
            "garden_paths",
            "garden_scanner",
            "garden_rules",
        ):
            with self.subTest(module=module_name):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        f"import importlib; importlib.import_module({module_name!r})",
                    ],
                    cwd=TOOLS_DIR,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(0, completed.returncode, completed.stderr)

    def test_facade_re_exports_internal_symbols_by_identity(self) -> None:
        garden_core = importlib.import_module("garden_core")
        garden_paths = importlib.import_module("garden_paths")
        garden_report = importlib.import_module("garden_report")
        garden_rules = importlib.import_module("garden_rules")
        garden_scanner = importlib.import_module("garden_scanner")

        self.assertIs(garden_core.Finding, garden_report.Finding)
        self.assertIs(garden_core.ScanLimitExceeded, garden_scanner.ScanLimitExceeded)
        self.assertIs(garden_core.find_project_root, garden_paths.find_project_root)
        self.assertIs(garden_core.is_within, garden_paths.is_within)
        self.assertIs(garden_core.inspect_file, garden_rules.inspect_file)
        self.assertIs(garden_core.inspect_project, garden_rules.inspect_project)


class GardenCoreTests(ActiveProjectTestCase):
    def test_contract_version_is_an_error(self) -> None:
        contract = self.root / "orders" / "CONTRACT.md"
        contract.parent.mkdir()
        contract.write_text("# Missing version\n", encoding="utf-8")
        self.assertEqual(
            ["R-contract-version"], [finding.rule for finding in inspect_file(contract)]
        )

    def test_contract_accepts_utf8_bom(self) -> None:
        contract = self.root / "orders" / "CONTRACT.md"
        contract.parent.mkdir()
        contract.write_bytes(b"\xef\xbb\xbfVersion: 1.2.3\r\n")
        self.assertEqual([], inspect_file(contract))

    def test_context_budget_stops_at_first_excess_line(self) -> None:
        context = self.root / "CONTEXT.md"
        context.write_text("line\n" * CONTEXT_LINE_BUDGET, encoding="utf-8")
        self.assertEqual([], inspect_file(context))
        context.write_text("line\n" * (CONTEXT_LINE_BUDGET + 1), encoding="utf-8")
        self.assertEqual(
            ["N-context-budget"], [item.rule for item in inspect_file(context)]
        )

    def test_project_inspection_reports_missing_contract_and_tests(self) -> None:
        source = self.root / "orders" / "handler.py"
        source.parent.mkdir()
        source.write_text("pass\n", encoding="utf-8")
        report = inspect_project(self.root)
        self.assertTrue(report["active"])
        self.assertEqual(2, report["summary"]["advisories"])

    def test_project_scan_has_an_entry_budget(self) -> None:
        capability = self.root / "orders"
        capability.mkdir()
        for index in range(4):
            (capability / f"empty-{index}").mkdir()
        with patch("garden_core.MAX_SCAN_ENTRIES", 2):
            report = inspect_project(self.root)
        self.assertIn(
            "D-project-scan-limit", [item["rule"] for item in report["findings"]]
        )

    def test_project_scan_reads_patched_facade_budget(self) -> None:
        garden_scanner = importlib.import_module("garden_scanner")
        capability = self.root / "orders"
        capability.mkdir()
        for index in range(4):
            (capability / f"empty-{index}").mkdir()

        with (
            patch("garden_core.MAX_SCAN_ENTRIES", 2),
            self.assertRaises(garden_scanner.ScanLimitExceeded) as raised,
        ):
            list(garden_scanner._walk_files(self.root))

        self.assertEqual("project scan exceeds 2 entries", str(raised.exception))

    def test_inactive_project_is_ignored(self) -> None:
        inactive = self.root / "inactive"
        inactive.mkdir()
        (self.root / "naming-registry.txt").unlink()
        self.assertFalse(inspect_project(inactive)["active"])
        self.assertIsNone(find_project_root(inactive))

    def test_symlink_escape_is_not_inspected(self) -> None:
        outside = Path(self.temp.name).parent / f"{self.root.name}-outside"
        outside.mkdir()
        try:
            target = outside / "CONTRACT.md"
            target.write_text("bad\n", encoding="utf-8")
            link = self.root / "CONTRACT.md"
            link.symlink_to(target)
            self.assertEqual([], inspect_file(link, self.root))
        finally:
            target.unlink(missing_ok=True)
            outside.rmdir()

    def test_pr_word_routes_review(self) -> None:
        self.assertEqual(["garden:review"], route_prompt("GARDEN PR #12", self.root))


if __name__ == "__main__":
    unittest.main()

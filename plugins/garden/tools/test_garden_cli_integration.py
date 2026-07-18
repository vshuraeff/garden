from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TOOLS_DIR.parent
FIXTURES_DIR = TOOLS_DIR / "fixtures"


class GardenCliIntegrationTests(unittest.TestCase):
    def run_garden(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(PLUGIN_ROOT / "bin" / "garden"), *arguments],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )

    def write_exception_project(self, root: Path, review_after: str) -> None:
        (root / ".garden.toml").write_text(
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
            'reason = "integration test exception"\n'
            'owner = "tests"\n'
            f'review_after = "{review_after}"\n',
            encoding="utf-8",
        )
        for capability in ("matched", "active"):
            capability_root = root / "src" / capability
            capability_root.mkdir(parents=True)
            (capability_root / "CONTRACT.md").write_text(
                "# Contract\n", encoding="utf-8"
            )
            (capability_root / "handler.py").write_text(
                "def handle() -> None:\n    pass\n", encoding="utf-8"
            )

    def test_inspect_plain_fixture_reports_expected_advisories(self) -> None:
        completed = self.run_garden("inspect", str(FIXTURES_DIR / "src-layout"))

        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        rules = {finding["rule"] for finding in report["findings"]}
        self.assertTrue(report["active"])
        self.assertIn("R-component-contract", rules)
        self.assertIn("A-colocated-tests", rules)

    def test_exceptions_configured_fixture_matches_expected_report(self) -> None:
        fixture = FIXTURES_DIR / "exceptions-configured"
        completed = self.run_garden("inspect", str(fixture))

        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
        report["root"] = "<FIXTURE_ROOT>"
        self.assertEqual(expected, report)

    def test_strict_inspect_rejects_inactive_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = self.run_garden("inspect", "--strict", directory)

        self.assertNotEqual(0, completed.returncode)
        self.assertFalse(json.loads(completed.stdout)["active"])

    def test_strict_inspect_rejects_expired_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_exception_project(root, "2020-01-01")
            completed = self.run_garden("inspect", "--strict", str(root))

        self.assertEqual(1, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertIs(report["exceptions"][0]["expired"], True)
        self.assertIs(report["exceptions"][0]["applied"], False)
        self.assertEqual(0, report["summary"]["suppressed"])
        self.assertEqual(2, report["summary"]["advisories"])

    def test_strict_inspect_applies_future_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_exception_project(root, "2099-01-01")
            completed = self.run_garden("inspect", "--strict", str(root))
            checked = self.run_garden(
                "check-file", str(root / "src" / "matched" / "handler.py")
            )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(0, checked.returncode, checked.stderr)
        report = json.loads(completed.stdout)
        findings = {finding["path"]: finding for finding in report["findings"]}
        self.assertEqual("suppressed", findings["src/matched/handler.py"]["state"])
        self.assertEqual("fail", findings["src/active/handler.py"]["state"])
        self.assertEqual(
            "suppressed", json.loads(checked.stdout)["findings"][0]["state"]
        )
        self.assertEqual(0, report["summary"]["errors"])
        self.assertEqual(1, report["summary"]["advisories"])
        self.assertEqual(1, report["summary"]["suppressed"])
        self.assertIs(report["exceptions"][0]["applied"], True)
        self.assertEqual(1, report["exceptions"][0]["matched_findings"])
        self.assertIs(report["exceptions"][0]["expired"], False)

    def test_strict_inspect_accepts_review_marker_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_exception_project(root, "on-major-release")
            completed = self.run_garden("inspect", "--strict", str(root))

        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertIs(report["exceptions"][0]["applied"], True)
        self.assertIs(report["exceptions"][0]["expired"], False)

    def test_config_validate_and_show_configured_fixture(self) -> None:
        fixture = FIXTURES_DIR / "src-layout-configured"

        validated = self.run_garden("config", "validate", str(fixture))
        shown = self.run_garden("config", "show", str(fixture))

        self.assertEqual(0, validated.returncode, validated.stderr)
        self.assertEqual(0, shown.returncode, shown.stderr)
        self.assertIn("valid:", validated.stdout)
        self.assertIn("schema_version = 1", shown.stdout)
        self.assertIn('capabilities.strategy = "children"', shown.stdout)

    def test_init_refuses_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.run_garden("init", str(root))
            refused = self.run_garden("init", str(root))
            forced = self.run_garden("init", str(root), "--force")

            self.assertEqual(0, first.returncode, first.stderr)
            self.assertTrue((root / ".garden.toml").is_file())
            self.assertNotEqual(0, refused.returncode)
            self.assertIn("already exists", refused.stderr)
            self.assertEqual(0, forced.returncode, forced.stderr)

    def test_migrate_config_creates_naming_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "naming-registry.txt").write_text(
                "orders: orders\n", encoding="utf-8"
            )

            completed = self.run_garden("migrate-config", str(root))
            content = (root / ".garden.toml").read_text(encoding="utf-8")

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("[naming]", content)
        self.assertIn('registry = "naming-registry.txt"', content)


if __name__ == "__main__":
    unittest.main()

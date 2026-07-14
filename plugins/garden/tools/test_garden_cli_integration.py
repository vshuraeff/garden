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

    def test_inspect_plain_fixture_reports_expected_advisories(self) -> None:
        completed = self.run_garden("inspect", str(FIXTURES_DIR / "src-layout"))

        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        rules = {finding["rule"] for finding in report["findings"]}
        self.assertTrue(report["active"])
        self.assertIn("R-component-contract", rules)
        self.assertIn("A-colocated-tests", rules)

    def test_strict_inspect_rejects_inactive_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = self.run_garden("inspect", "--strict", directory)

        self.assertNotEqual(0, completed.returncode)
        self.assertFalse(json.loads(completed.stdout)["active"])

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

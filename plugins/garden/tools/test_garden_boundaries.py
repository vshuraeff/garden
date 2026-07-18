from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from garden_config import load_config, resolve_effective  # noqa: E402
from garden_rules import inspect_file, inspect_project, resolve_boundary  # noqa: E402


class GardenBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_config(self, sections: str) -> None:
        (self.root / ".garden.toml").write_text(
            "schema_version = 2\n\n"
            "[documentation]\n"
            "root_context_required = false\n\n"
            f"{sections.strip()}\n",
            encoding="utf-8",
        )

    def write_public_import_project(self, imported_module: str) -> Path:
        (self.root / ".garden.toml").write_text(
            "schema_version = 1\n"
            "[scan]\n"
            'roots = ["src"]\n'
            'include = ["**/*.py"]\n'
            "[capabilities]\n"
            'strategy = "explicit"\n'
            "[capabilities.map]\n"
            '"src/orders" = "orders"\n'
            '"src/billing" = "billing"\n'
            "[boundaries]\n"
            'public = ["src/orders/api.py"]\n'
            "[documentation]\n"
            "root_context_required = false\n",
            encoding="utf-8",
        )
        orders = self.root / "src" / "orders"
        billing = self.root / "src" / "billing"
        orders.mkdir(parents=True)
        billing.mkdir(parents=True)
        for capability in (orders, billing):
            (capability / "CONTRACT.md").write_text(
                "Version: 1.0.0\n", encoding="utf-8"
            )
        (orders / "api.py").write_text("VALUE = 1\n", encoding="utf-8")
        (orders / "private.py").write_text("VALUE = 2\n", encoding="utf-8")
        source = billing / "handler.py"
        source.write_text(f"from {imported_module} import VALUE\n", encoding="utf-8")
        return source

    def test_cross_capability_private_import_is_an_error(self) -> None:
        source = self.write_public_import_project("src.orders.private")

        file_finding = next(
            finding
            for finding in inspect_file(source, self.root)
            if finding.rule == "A-private-boundary-import"
        )
        project_findings = [
            finding
            for finding in inspect_project(self.root)["findings"]
            if finding["rule"] == "A-private-boundary-import"
        ]

        self.assertEqual("error", file_finding.severity)
        self.assertEqual("REQUIRED", file_finding.level)
        self.assertEqual("src/billing/handler.py", file_finding.path)
        self.assertEqual(1, len(project_findings))

    def test_cross_capability_public_import_has_no_error(self) -> None:
        source = self.write_public_import_project("src.orders.api")

        file_rules = [finding.rule for finding in inspect_file(source, self.root)]
        project_rules = [
            finding["rule"] for finding in inspect_project(self.root)["findings"]
        ]

        self.assertNotIn("A-private-boundary-import", file_rules)
        self.assertNotIn("A-private-boundary-import", project_rules)

    def test_private_contract_without_version_is_not_checked(self) -> None:
        self.write_config(
            """
[[boundaries]]
path = "src/private-core"
kind = "private"
"""
        )
        contract = self.root / "src" / "private-core" / "CONTRACT.md"
        contract.parent.mkdir(parents=True)
        contract.write_text("# private contract\n", encoding="utf-8")

        rules = [finding.rule for finding in inspect_file(contract, self.root)]

        self.assertNotIn("R-contract-version", rules)

    def test_semver_contract_without_version_is_checked(self) -> None:
        self.write_config(
            """
[[boundaries]]
path = "src/public-api"
kind = "public-api"
owner = "team-api"
versioning = "semver"
contracts = ["CONTRACT.md"]
"""
        )
        contract = self.root / "src" / "public-api" / "CONTRACT.md"
        contract.parent.mkdir(parents=True)
        contract.write_text("# missing version\n", encoding="utf-8")

        rules = [finding.rule for finding in inspect_file(contract, self.root)]

        self.assertIn("R-contract-version", rules)

    def test_semver_contract_with_version_passes(self) -> None:
        self.write_config(
            """
[[boundaries]]
path = "src/public-api"
kind = "public-api"
owner = "team-api"
versioning = "semver"
contracts = ["CONTRACT.md"]
"""
        )
        contract = self.root / "src" / "public-api" / "CONTRACT.md"
        contract.parent.mkdir(parents=True)
        contract.write_text("Version: 2.4.1\n", encoding="utf-8")

        rules = [finding.rule for finding in inspect_file(contract, self.root)]

        self.assertNotIn("R-contract-version", rules)

    def test_custom_versioned_contract_without_version_is_not_checked(self) -> None:
        self.write_config(
            """
[[boundaries]]
path = "src/internal-versioned"
kind = "internal-versioned"
owner = "team-platform"
versioning = "custom"
contracts = ["CONTRACT.md"]
"""
        )
        contract = self.root / "src" / "internal-versioned" / "CONTRACT.md"
        contract.parent.mkdir(parents=True)
        contract.write_text("# custom version policy\n", encoding="utf-8")

        rules = [finding.rule for finding in inspect_file(contract, self.root)]

        self.assertNotIn("R-contract-version", rules)

    def test_existing_declared_contract_satisfies_presence(self) -> None:
        self.write_config(
            """
[[boundaries]]
path = "src/public-api"
kind = "public-api"
owner = "team-api"
contracts = ["openapi.yaml"]
"""
        )
        artifact = self.root / "src" / "public-api" / "openapi.yaml"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("openapi: 3.1.0\n", encoding="utf-8")

        report = inspect_project(self.root)

        self.assertNotIn(
            "R-boundary-contract-missing",
            [finding["rule"] for finding in report["findings"]],
        )

    def test_missing_declared_contract_reports_its_project_path(self) -> None:
        self.write_config(
            """
[[boundaries]]
path = "src/public-api"
kind = "public-api"
owner = "team-api"
contracts = ["openapi.yaml"]
"""
        )

        report = inspect_project(self.root)
        finding = next(
            finding
            for finding in report["findings"]
            if finding["rule"] == "R-boundary-contract-missing"
        )

        self.assertEqual("src/public-api/openapi.yaml", finding["path"])

    def test_nested_declared_contract_is_checked_for_presence_and_version(self) -> None:
        self.write_config(
            """
[[boundaries]]
path = "src/orders"
kind = "public-api"
owner = "team-orders"
versioning = "semver"
contracts = ["CONTRACT.md"]
"""
        )
        contract = self.root / "src" / "orders" / "CONTRACT.md"
        contract.parent.mkdir(parents=True)
        contract.write_text("Version: 1.0.0\n", encoding="utf-8")

        present_report = inspect_project(self.root)
        present_rules = [finding["rule"] for finding in present_report["findings"]]
        self.assertNotIn("R-boundary-contract-missing", present_rules)
        self.assertNotIn("R-contract-version", present_rules)

        contract.unlink()
        missing_report = inspect_project(self.root)
        missing = next(
            finding
            for finding in missing_report["findings"]
            if finding["rule"] == "R-boundary-contract-missing"
        )
        self.assertEqual("src/orders/CONTRACT.md", missing["path"])

    def test_nested_valid_contract_passes_project_and_file_inspection(self) -> None:
        self.write_config(
            """
[[boundaries]]
path = "src/orders"
kind = "public-api"
owner = "team-orders"
versioning = "semver"
"""
        )
        contract = self.root / "src" / "orders" / "nested" / "CONTRACT.md"
        contract.parent.mkdir(parents=True)
        contract.write_text("Version: 1.0.0\n", encoding="utf-8")

        file_rules = [finding.rule for finding in inspect_file(contract, self.root)]
        report = inspect_project(self.root)
        project_rules = [
            finding["rule"]
            for finding in report["findings"]
            if finding["path"] == "src/orders/nested/CONTRACT.md"
        ]

        self.assertNotIn("R-contract-version", file_rules)
        self.assertNotIn("R-contract-version", project_rules)

    def test_longest_boundary_path_wins(self) -> None:
        self.write_config(
            """
[[boundaries]]
path = "src"
kind = "public-api"
owner = "team-api"

[[boundaries]]
path = "src/orders"
kind = "internal-versioned"
owner = "team-orders"
versioning = "custom"
"""
        )
        loaded = load_config(self.root)
        self.assertEqual((), loaded.errors)
        self.assertIsNotNone(loaded.config)
        effective = resolve_effective(loaded.config)

        orders = resolve_boundary("src/orders/service.py", effective)
        other = resolve_boundary("src/other.py", effective)

        self.assertIsNotNone(orders)
        self.assertIsNotNone(other)
        self.assertEqual("src/orders", orders.path.value)
        self.assertEqual("src", other.path.value)

    def test_evidence_categories_are_advisory_unknowns(self) -> None:
        self.write_config(
            """
[[boundaries]]
path = "src/public-api"
kind = "public-api"
owner = "team-api"
required_evidence = ["contract-tests", "rollback-plan"]
"""
        )

        report = inspect_project(self.root)
        findings = [
            finding
            for finding in report["findings"]
            if finding["rule"] == "R-boundary-evidence-review"
        ]

        self.assertTrue(report["complete"])
        self.assertEqual(2, len(findings))
        self.assertEqual({"advisory"}, {finding["severity"] for finding in findings})
        self.assertEqual({"unknown"}, {finding["state"] for finding in findings})
        self.assertTrue(
            all(
                "manual verification is required" in finding["message"]
                for finding in findings
            )
        )
        self.assertTrue(
            all(
                "file existence alone does not establish evidence completeness"
                in finding["message"]
                for finding in findings
            )
        )

    def test_any_accepted_contract_name_satisfies_capability_advisory(self) -> None:
        self.write_config(
            """
[scan]
include = ["**/*.py"]

[capabilities]
strategy = "children"
roots = ["src"]
depth = 1

[contracts]
accepted_names = ["openapi.yaml"]
"""
        )
        capability = self.root / "src" / "orders"
        capability.mkdir(parents=True)
        source = capability / "handler.py"
        source.write_text("pass\n", encoding="utf-8")
        (capability / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")

        rules = [finding.rule for finding in inspect_file(source, self.root)]

        self.assertNotIn("R-component-contract", rules)


if __name__ == "__main__":
    unittest.main()

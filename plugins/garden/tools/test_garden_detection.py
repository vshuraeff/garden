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

from garden_config import (  # noqa: E402
    load_config,
    resolve_capability,
    resolve_effective,
)
from garden_core import Finding, inspect_file, inspect_project  # noqa: E402


CONFIGURED_FIXTURES = (
    "boundaries-configured",
    "src-layout-configured",
    "monorepo-configured",
    "library-configured",
    "config-heavy-configured",
    "false-positives-configured",
)
LEGACY_FIXTURES = (
    "flat-capabilities",
    "src-layout",
    "monorepo",
    "library",
    "config-heavy-project",
    "false-positives",
    "inactive-project",
)


def _write_config(root: Path, sections: str) -> None:
    (root / ".garden.toml").write_text(
        "schema_version = 1\n"
        f"{sections.strip()}\n"
        "[documentation]\n"
        "root_context_required = false\n",
        encoding="utf-8",
    )


def _rules(findings: list[Finding]) -> list[str]:
    return [finding.rule for finding in findings]


class FixtureDetectionTests(unittest.TestCase):
    def assert_fixture_report(self, name: str) -> None:
        fixture_dir = FIXTURES_DIR / name
        loaded = load_config(fixture_dir)
        if loaded.present:
            self.assertEqual((), loaded.errors)
        report = inspect_project(fixture_dir)
        expected = json.loads(
            (fixture_dir / "expected.json").read_text(encoding="utf-8")
        )
        if expected["active"]:
            self.assertEqual(fixture_dir.resolve(), Path(report["root"]))
        report["root"] = EXPECTED_ROOT
        self.assertEqual(expected, report)

    def test_configured_fixtures(self) -> None:
        # the configured src layout removes the widget-level false advisories.
        for name in CONFIGURED_FIXTURES:
            with self.subTest(name=name):
                self.assert_fixture_report(name)

    def test_unconfigured_fixture_reports_are_unchanged(self) -> None:
        for name in LEGACY_FIXTURES:
            with self.subTest(name=name):
                self.assert_fixture_report(name)


class CapabilityDetectionTests(unittest.TestCase):
    def test_capability_strategies_do_not_invent_out_of_scope_findings(self) -> None:
        cases = (
            (
                "none",
                '[capabilities]\nstrategy = "none"',
                "service/handler.py",
                "outside/tool.py",
                "none",
                "none",
                False,
            ),
            (
                "children",
                '[capabilities]\nstrategy = "children"\nroots = ["src"]\ndepth = 1',
                "src/orders/handler.py",
                "outside/tool.py",
                "capability",
                "none",
                True,
            ),
            (
                "explicit",
                '[capabilities]\nstrategy = "explicit"\n'
                'map = { "src/orders" = "orders" }',
                "src/orders/handler.py",
                "outside/tool.py",
                "capability",
                "none",
                True,
            ),
            (
                "markers",
                '[capabilities]\nstrategy = "markers"',
                "service/handler.py",
                "outside/tool.py",
                "unknown",
                "unknown",
                False,
            ),
        )
        for (
            strategy,
            config,
            matching_path,
            outside_path,
            matching_status,
            outside_status,
            matching_contract_finding,
        ) in cases:
            with self.subTest(strategy=strategy):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    _write_config(root, config)
                    matching = root / matching_path
                    outside = root / outside_path
                    matching.parent.mkdir(parents=True, exist_ok=True)
                    outside.parent.mkdir(parents=True, exist_ok=True)
                    matching.write_text("pass\n", encoding="utf-8")
                    outside.write_text("pass\n", encoding="utf-8")
                    effective = resolve_effective(load_config(root).config)

                    matching_resolution = resolve_capability(matching_path, effective)
                    outside_resolution = resolve_capability(outside_path, effective)
                    matching_rules = _rules(inspect_file(matching, root))
                    outside_rules = _rules(inspect_file(outside, root))

                    self.assertEqual(matching_status, matching_resolution.status)
                    self.assertEqual(outside_status, outside_resolution.status)
                    self.assertEqual(
                        matching_contract_finding,
                        "R-component-contract" in matching_rules,
                    )
                    self.assertNotIn("R-component-contract", outside_rules)

    def test_explicit_contract_is_checked_at_the_mapped_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_config(
                root,
                '[capabilities]\nstrategy = "explicit"\n'
                'map = { "src/client" = "client" }',
            )
            source = root / "src" / "client" / "client.py"
            source.parent.mkdir(parents=True)
            source.write_text("pass\n", encoding="utf-8")
            (source.parent / "CONTRACT.md").write_text(
                "Version: 1.0.0\n", encoding="utf-8"
            )

            rules = _rules(inspect_file(source, root))

        self.assertNotIn("R-component-contract", rules)

    def test_shared_root_has_no_capability_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_config(
                root,
                """
[capabilities]
strategy = "children"
roots = ["packages"]
shared_roots = ["packages/shared"]
""",
            )
            source = root / "packages" / "shared" / "helpers.py"
            source.parent.mkdir(parents=True)
            source.write_text("pass\n", encoding="utf-8")

            rules = _rules(inspect_file(source, root))

        self.assertNotIn("R-component-contract", rules)
        self.assertNotIn("A-colocated-tests", rules)


class SourceAndTestDetectionTests(unittest.TestCase):
    def test_scan_include_and_exclude_control_configured_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_config(
                root,
                """
[scan]
include = ["**/*.yaml"]
exclude = ["config/private/**"]
[capabilities]
strategy = "children"
roots = ["."]
""",
            )
            visible = root / "config" / "settings.yaml"
            excluded = root / "config" / "private" / "secret.yaml"
            ordinary = root / "config" / "handler.py"
            hidden = root / "config" / ".hidden.yaml"
            for path in (visible, excluded, ordinary, hidden):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("value: true\n", encoding="utf-8")

            self.assertIn("R-component-contract", _rules(inspect_file(visible, root)))
            self.assertNotIn(
                "R-component-contract", _rules(inspect_file(excluded, root))
            )
            self.assertNotIn(
                "R-component-contract", _rules(inspect_file(ordinary, root))
            )
            self.assertNotIn("R-component-contract", _rules(inspect_file(hidden, root)))

    def test_empty_scan_include_uses_the_legacy_suffix_filter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_config(
                root,
                """
[scan]
include = []
[capabilities]
strategy = "children"
roots = ["."]
""",
            )
            source = root / "orders" / "handler.py"
            config_file = root / "orders" / "settings.yaml"
            source.parent.mkdir()
            source.write_text("pass\n", encoding="utf-8")
            config_file.write_text("enabled: true\n", encoding="utf-8")

            self.assertIn("R-component-contract", _rules(inspect_file(source, root)))
            self.assertNotIn(
                "R-component-contract", _rules(inspect_file(config_file, root))
            )

    def test_same_capability_association_counts_only_its_own_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_config(
                root,
                """
[capabilities]
strategy = "children"
roots = ["src"]
[tests]
patterns = ["**/test_*.py"]
association = "same-capability"
""",
            )
            orders = root / "src" / "orders"
            billing = root / "src" / "billing"
            orders.mkdir(parents=True)
            billing.mkdir(parents=True)
            for capability in (orders, billing):
                (capability / "CONTRACT.md").write_text(
                    "Version: 1.0.0\n", encoding="utf-8"
                )
                (capability / "handler.py").write_text("pass\n", encoding="utf-8")
            (orders / "test_handler.py").write_text("pass\n", encoding="utf-8")

            order_rules = _rules(inspect_file(orders / "handler.py", root))
            billing_rules = _rules(inspect_file(billing / "handler.py", root))

        self.assertNotIn("A-colocated-tests", order_rules)
        self.assertIn("A-colocated-tests", billing_rules)

    def test_test_roots_association_handles_mapped_and_unmapped_tests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_config(
                root,
                """
[capabilities]
strategy = "explicit"
map = { "libcore" = "core", "other" = "other" }
[tests]
patterns = ["tests/**", "checks/**"]
association = "test-roots"
test_roots = { "tests" = "libcore" }
""",
            )
            core = root / "libcore"
            other = root / "other"
            tests = root / "tests"
            checks = root / "checks"
            for path in (core, other, tests, checks):
                path.mkdir()
            for capability in (core, other):
                (capability / "CONTRACT.md").write_text(
                    "Version: 1.0.0\n", encoding="utf-8"
                )
                (capability / "handler.py").write_text("pass\n", encoding="utf-8")
            (tests / "test_core.py").write_text("pass\n", encoding="utf-8")
            (checks / "test_other.py").write_text("pass\n", encoding="utf-8")

            core_rules = _rules(inspect_file(core / "handler.py", root))
            other_rules = _rules(inspect_file(other / "handler.py", root))

        self.assertNotIn("A-colocated-tests", core_rules)
        self.assertIn("A-colocated-tests", other_rules)

    def test_unmapped_test_file_has_no_capability_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_config(
                root,
                """
[capabilities]
strategy = "children"
roots = ["."]
[tests]
patterns = ["checks/**"]
association = "test-roots"
test_roots = { "tests" = "src" }
""",
            )
            test_file = root / "checks" / "test_orphan.py"
            test_file.parent.mkdir()
            test_file.write_text("pass\n", encoding="utf-8")

            rules = _rules(inspect_file(test_file, root))

        self.assertNotIn("R-component-contract", rules)
        self.assertNotIn("A-colocated-tests", rules)

    def test_contest_name_does_not_satisfy_configured_test_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_config(
                root,
                """
[capabilities]
strategy = "children"
roots = ["."]
[tests]
patterns = ["**/test_*.py"]
association = "same-capability"
""",
            )
            capability = root / "widget"
            capability.mkdir()
            (capability / "CONTRACT.md").write_text(
                "Version: 1.0.0\n", encoding="utf-8"
            )
            source = capability / "handler.py"
            source.write_text("pass\n", encoding="utf-8")
            (capability / "contest.py").write_text("pass\n", encoding="utf-8")

            rules = _rules(inspect_file(source, root))

        # the legacy substring heuristic would count contest.py as a test.
        self.assertIn("A-colocated-tests", rules)

    def test_configured_project_scan_limit_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_config(
                root,
                '[capabilities]\nstrategy = "children"\nroots = ["."]',
            )
            capability = root / "orders"
            capability.mkdir()
            for index in range(4):
                (capability / f"empty-{index}").mkdir()

            with patch("garden_core.MAX_SCAN_ENTRIES", 2):
                report = inspect_project(root)

        self.assertIn(
            "D-project-scan-limit",
            [finding["rule"] for finding in report["findings"]],
        )


class NamingRegistryDetectionTests(unittest.TestCase):
    def report_rules(self, *, registry: str | None, required: bool = True) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_config(
                root,
                f"""
[naming]
registry = "registry.txt"
required = {str(required).lower()}
""",
            )
            if registry is not None:
                (root / "registry.txt").write_text(registry, encoding="utf-8")
            report = inspect_project(root)
        return [finding["rule"] for finding in report["findings"]]

    def test_missing_required_registry(self) -> None:
        self.assertIn("N-NAMING-MISSING", self.report_rules(registry=None))

    def test_empty_required_registry(self) -> None:
        self.assertIn(
            "N-NAMING-EMPTY-REGISTRY",
            self.report_rules(registry="\n# no entries\n"),
        )

    def test_invalid_registry_entry(self) -> None:
        self.assertIn(
            "N-NAMING-INVALID-ENTRY",
            self.report_rules(registry="invalid entry\n", required=False),
        )

    def test_duplicate_concept(self) -> None:
        self.assertIn(
            "N-NAMING-DUPLICATE-CONCEPT",
            self.report_rules(registry="orders: orders\norders: purchases\n"),
        )

    def test_duplicate_canonical_name(self) -> None:
        self.assertIn(
            "N-NAMING-DUPLICATE-CANONICAL",
            self.report_rules(registry="orders: shared\nbilling: shared\n"),
        )

    def test_unconfigured_registry_is_not_content_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "naming-registry.txt").write_text(
                "invalid entry\n", encoding="utf-8"
            )

            report = inspect_project(root)

        self.assertFalse(
            any(
                finding["rule"].startswith("N-NAMING-")
                for finding in report["findings"]
            )
        )


if __name__ == "__main__":
    unittest.main()

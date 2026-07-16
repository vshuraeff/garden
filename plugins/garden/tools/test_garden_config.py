from __future__ import annotations

import io
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from config_schema import validate_config  # noqa: E402
from garden_cli import main as garden_cli_main  # noqa: E402
from garden_config import (  # noqa: E402
    ConfigWriteError,
    initialize_config,
    load_config,
    migrate_config,
    render_effective,
    resolve_capability,
    resolve_effective,
    resolve_test_association,
)
from garden_core import (  # noqa: E402
    find_project_activation,
    inspect_file,
    inspect_project,
)


class ConfigSchemaTests(unittest.TestCase):
    def test_valid_config_parses_and_normalizes_paths(self) -> None:
        parsed = tomllib.loads(
            """
schema_version = 1
[project]
type = "service"
context_files = { any_of = ["CONTEXT.md"] }
[scan]
roots = ["src\\\\services"]
include = ["src\\\\**\\\\*.py"]
[capabilities]
strategy = "markers"
depth = 1
[documentation]
root_context_required = true
max_context_lines = 120
"""
        )

        result = validate_config(parsed)

        self.assertEqual((), result.errors)
        self.assertEqual(("src/services",), result.config.scan.roots)
        self.assertEqual(("src/**/*.py",), result.config.scan.include)

    def test_unknown_top_level_and_nested_keys_accumulate(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 1
unknown = true
[project]
extra = "x"
[documentation]
other = 1
"""
            )
        )

        self.assertEqual(
            ["unknown", "project.extra", "documentation.other"],
            [error.path for error in result.errors],
        )

    def test_wrong_types_reject_bool_as_int_and_int_as_bool(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = true
[scan]
roots = "."
[capabilities]
depth = false
[documentation]
root_context_required = 1
"""
            )
        )

        paths = [error.path for error in result.errors]
        self.assertEqual(
            [
                "schema_version",
                "scan.roots",
                "capabilities.depth",
                "documentation.root_context_required",
            ],
            paths,
        )

    def test_bad_globs_accumulate(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
[scan]
include = ["/absolute/*.py", "../escape.py", "**/**", "a/**/**/b"]
"""
            )
        )

        self.assertEqual(4, len(result.errors))
        self.assertTrue(
            all(error.path.startswith("scan.include[") for error in result.errors)
        )


class GardenConfigTests(unittest.TestCase):
    def test_load_reports_malformed_toml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".garden.toml").write_text("[project\n", encoding="utf-8")

            result = load_config(root)

        self.assertTrue(result.present)
        self.assertIsNone(result.config)
        self.assertEqual("config", result.errors[0].path)

    def test_effective_origins_and_rendering_are_stable(self) -> None:
        validation = validate_config(
            tomllib.loads(
                """
schema_version = 1
[project]
type = "library"
[documentation]
max_context_lines = 80
"""
            )
        )
        effective = resolve_effective(validation.config)

        rendered = render_effective(effective)

        self.assertEqual("file", effective.project.type.origin)
        self.assertEqual("default", effective.scan.roots.origin)
        self.assertIn('project.type = "library" # origin: file\n', rendered)
        self.assertIn('scan.roots = ["."] # origin: default\n', rendered)
        self.assertIn("capabilities.map = {} # origin: default\n", rendered)
        self.assertEqual(rendered, render_effective(effective))

    def test_strategy_resolvers_dispatch_without_marker_format(self) -> None:
        markers = validate_config(
            tomllib.loads('[capabilities]\nstrategy = "markers"\n')
        )
        marker_result = resolve_capability(
            "src/orders/handler.py", resolve_effective(markers.config)
        )
        explicit = validate_config(
            tomllib.loads(
                """
[capabilities]
strategy = "explicit"
map = { "src/orders" = "orders" }
[tests]
association = "test-roots"
test_roots = { "tests/orders" = "src/orders" }
"""
            )
        )
        effective = resolve_effective(explicit.config)

        self.assertEqual("unknown", marker_result.status)
        self.assertEqual("EXPERIMENTAL", marker_result.tag)
        self.assertEqual(
            "orders", resolve_capability("src/orders/api.py", effective).capability
        )
        self.assertEqual(
            "src/orders/test_api.py",
            resolve_test_association(
                "tests/orders/test_api.py", effective
            ).source_prefix,
        )

    def test_children_capability_identity_includes_configured_root(self) -> None:
        validation = validate_config(
            tomllib.loads(
                """
[capabilities]
strategy = "children"
roots = ["src", "lib"]
depth = 1
"""
            )
        )
        effective = resolve_effective(validation.config)

        self.assertEqual(
            "src/orders",
            resolve_capability("src/orders/handler.py", effective).capability,
        )
        self.assertEqual(
            "lib/orders",
            resolve_capability("lib/orders/handler.py", effective).capability,
        )

    def test_existing_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            outside = workspace / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "linked").symlink_to(outside, target_is_directory=True)
            (root / ".garden.toml").write_text(
                '[scan]\nroots = ["linked"]\n', encoding="utf-8"
            )

            result = load_config(root)

        self.assertEqual("scan.roots[0]", result.errors[0].path)


class ConfigActivationTests(unittest.TestCase):
    def test_valid_config_activates_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".garden.toml").write_text(
                "schema_version = 1\n[documentation]\nroot_context_required = false\n",
                encoding="utf-8",
            )

            activation = find_project_activation(root)
            report = inspect_project(root)

        self.assertEqual("config", activation.kind)
        self.assertTrue(report["active"])
        self.assertEqual(0, report["summary"]["errors"])

    def test_malformed_config_stops_ancestor_search_and_reports_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ancestor = Path(directory)
            (ancestor / "naming-registry.txt").write_text("x: x\n", encoding="utf-8")
            root = ancestor / "child"
            root.mkdir()
            (root / ".garden.toml").write_text("[broken\n", encoding="utf-8")

            activation = find_project_activation(root)
            report = inspect_project(root)

        self.assertEqual(root.resolve(), activation.root)
        self.assertEqual("config", activation.kind)
        self.assertTrue(report["active"])
        self.assertEqual(
            ["N-CONFIG-INVALID"], [finding["rule"] for finding in report["findings"]]
        )

    def test_legacy_registry_activates_and_marker_check_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / "naming-registry.txt"
            registry.write_text("orders: orders\n", encoding="utf-8")

            activation = find_project_activation(root)
            findings = inspect_file(registry)

        self.assertEqual("legacy", activation.kind)
        self.assertEqual(["N-LEGACY-NAMING-REGISTRY"], [item.rule for item in findings])

    def test_project_without_marker_is_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(find_project_activation(root))
            self.assertFalse(inspect_project(root)["active"])


class ConfigRuleTests(unittest.TestCase):
    def write_config(self, root: Path, extra: str = "") -> None:
        (root / ".garden.toml").write_text(
            "schema_version = 1\n" + extra, encoding="utf-8"
        )

    def test_required_context_finding_and_configured_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_config(
                root,
                """
[project]
context_files = { any_of = ["AGENTS.md"] }
[documentation]
max_context_lines = 2
""",
            )
            report = inspect_project(root)
            self.assertIn(
                "N-CONTEXT-MISSING",
                [finding["rule"] for finding in report["findings"]],
            )
            agents = root / "AGENTS.md"
            agents.write_text("one\ntwo\nthree\n", encoding="utf-8")

            findings = inspect_file(agents)

        self.assertEqual(["N-context-budget"], [finding.rule for finding in findings])

    def test_configured_test_patterns_replace_name_substrings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_config(
                root,
                """
[documentation]
root_context_required = false
[tests]
patterns = ["**/checks.py"]
""",
            )
            capability = root / "orders"
            capability.mkdir()
            (capability / "CONTRACT.md").write_text(
                "Version: 1.0.0\n", encoding="utf-8"
            )
            source = capability / "handler.py"
            source.write_text("pass\n", encoding="utf-8")
            (capability / "contest.py").write_text("pass\n", encoding="utf-8")
            without_match = inspect_file(source)
            (capability / "checks.py").write_text("pass\n", encoding="utf-8")

            with_match = inspect_file(source)

        self.assertIn("A-colocated-tests", [item.rule for item in without_match])
        self.assertNotIn("A-colocated-tests", [item.rule for item in with_match])


class ConfigCliTests(unittest.TestCase):
    def run_cli(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = garden_cli_main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_config_validate_and_show(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".garden.toml").write_text(
                '[project]\ntype = "service"\n', encoding="utf-8"
            )

            validate_code, _, validate_error = self.run_cli(
                ["config", "validate", str(root)]
            )
            show_code, shown, show_error = self.run_cli(["config", "show", str(root)])

        self.assertEqual((0, ""), (validate_code, validate_error))
        self.assertEqual((0, ""), (show_code, show_error))
        self.assertIn('project.type = "service" # origin: file', shown)
        self.assertIn('scan.roots = ["."] # origin: default', shown)

    def test_init_is_conservative_and_requires_force_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            (root / "src").mkdir()

            first, _, first_error = self.run_cli(["init", str(root)])
            refused, _, refused_error = self.run_cli(["init", str(root)])
            forced, _, forced_error = self.run_cli(["init", str(root), "--force"])
            content = (root / ".garden.toml").read_text(encoding="utf-8")

        self.assertEqual((0, ""), (first, first_error))
        self.assertEqual(1, refused)
        self.assertIn("already exists", refused_error)
        self.assertEqual((0, ""), (forced, forced_error))
        self.assertIn('roots = ["src"]', content)
        self.assertIn("# [contracts]", content)
        self.assertIn("# [[exceptions]]", content)

    def test_migration_round_trips_and_force_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "naming-registry.txt").write_text(
                "orders: orders\n", encoding="utf-8"
            )

            legacy_report = inspect_project(root)
            destination = migrate_config(root)
            result = load_config(root)
            migrated_report = inspect_project(root)
            with self.assertRaises(ConfigWriteError):
                migrate_config(root)
            destination.write_text("broken = true\n", encoding="utf-8")
            migrate_config(root, force=True)
            reparsed = load_config(root)

        self.assertTrue(result.valid)
        self.assertTrue(reparsed.valid)
        effective = resolve_effective(reparsed.config)
        self.assertTrue(effective.naming.required.value)
        self.assertFalse(effective.documentation.root_context_required.value)
        self.assertNotIn(
            "N-CONTEXT-MISSING",
            [finding["rule"] for finding in legacy_report["findings"]],
        )
        self.assertNotIn(
            "N-CONTEXT-MISSING",
            [finding["rule"] for finding in migrated_report["findings"]],
        )

    def test_atomic_failure_preserves_existing_config_and_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / ".garden.toml"
            destination.write_text("original\n", encoding="utf-8")

            with patch(
                "garden_config.os.replace", side_effect=OSError("replace failed")
            ):
                with self.assertRaises(OSError):
                    initialize_config(root, force=True)

            remaining = sorted(path.name for path in root.iterdir())
            content = destination.read_text(encoding="utf-8")

        self.assertEqual([".garden.toml"], remaining)
        self.assertEqual("original\n", content)


if __name__ == "__main__":
    unittest.main()

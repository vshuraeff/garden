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


class BoundarySchemaV2Tests(unittest.TestCase):
    def test_valid_v2_boundaries_parse_and_resolve(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/api"
kind = "public-api"
owner = "platform"
versioning = "semver"
contracts = ["openapi.yaml"]
required_evidence = ["contract-tests", "observability"]

[[boundaries]]
path = "src/internal"
kind = "private"
"""
            )
        )

        self.assertEqual((), result.errors)
        self.assertIsNone(result.config.boundaries)
        self.assertEqual(2, len(result.config.boundary_entries))
        first, second = result.config.boundary_entries
        self.assertEqual("src/api", first.path)
        self.assertEqual("public-api", first.kind)
        self.assertEqual("platform", first.owner)
        self.assertEqual("semver", first.versioning)
        self.assertEqual(("openapi.yaml",), first.contracts)
        self.assertEqual(("contract-tests", "observability"), first.required_evidence)
        self.assertEqual("private", second.kind)
        self.assertIsNone(second.owner)

        effective = resolve_effective(result.config)

        self.assertEqual("file", effective.boundary_entries.origin)
        self.assertEqual(2, len(effective.boundary_entries.value))
        effective_first, effective_second = effective.boundary_entries.value
        self.assertEqual("src/api", effective_first.path.value)
        self.assertEqual("file", effective_first.path.origin)
        self.assertEqual("semver", effective_first.versioning.value)
        self.assertEqual(("openapi.yaml",), effective_first.contracts.value)
        self.assertEqual("", effective_second.owner.value)
        self.assertEqual("default", effective_second.owner.origin)
        self.assertEqual("none", effective_second.versioning.value)
        self.assertEqual("default", effective_second.versioning.origin)

    def test_absent_schema_version_keeps_v1_boundaries(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
[boundaries]
public = ["src/api"]
"""
            )
        )

        self.assertEqual((), result.errors)
        self.assertIsNone(result.config.schema_version)
        self.assertEqual(("src/api",), result.config.boundaries.public)
        self.assertIsNone(result.config.boundary_entries)

    def test_v2_rejects_v1_boundaries_table(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[boundaries]
public = ["src/api"]
"""
            )
        )

        self.assertEqual(["boundaries"], [error.path for error in result.errors])
        self.assertIn("schema v2", result.errors[0].message)
        self.assertIn("[[boundaries]]", result.errors[0].message)

    def test_v1_rejects_v2_boundaries_array(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 1
[[boundaries]]
path = "src/api"
kind = "public-api"
owner = "platform"
"""
            )
        )

        self.assertEqual(["boundaries"], [error.path for error in result.errors])
        self.assertIn("schema v1", result.errors[0].message)
        self.assertIn("[boundaries]", result.errors[0].message)

    def test_unsupported_schema_version_lists_supported_versions(self) -> None:
        result = validate_config(tomllib.loads("schema_version = 3\n"))

        self.assertEqual(["schema_version"], [error.path for error in result.errors])
        self.assertIn("1", result.errors[0].message)
        self.assertIn("2", result.errors[0].message)

    def test_boundary_path_is_required(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
kind = "private"
"""
            )
        )

        self.assertEqual(
            ["boundaries[0].path"], [error.path for error in result.errors]
        )

    def test_boundary_kind_is_required_and_closed(self) -> None:
        missing = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/missing"
"""
            )
        )
        bad = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/bad"
kind = "unknown"
owner = "platform"
"""
            )
        )

        self.assertEqual(
            ["boundaries[0].kind"], [error.path for error in missing.errors]
        )
        self.assertEqual(["boundaries[0].kind"], [error.path for error in bad.errors])

    def test_non_private_boundary_requires_non_empty_owner(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/api"
kind = "public-api"
owner = ""
"""
            )
        )

        self.assertEqual(
            ["boundaries[0].owner"], [error.path for error in result.errors]
        )
        self.assertIn("must not be empty", result.errors[0].message)

    def test_private_boundary_does_not_require_owner(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/internal"
kind = "private"
"""
            )
        )

        self.assertEqual((), result.errors)
        self.assertIsNone(result.config.boundary_entries[0].owner)

    def test_boundary_versioning_is_closed(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/api"
kind = "public-api"
owner = "platform"
versioning = "rolling"
"""
            )
        )

        self.assertEqual(
            ["boundaries[0].versioning"], [error.path for error in result.errors]
        )

    def test_boundary_required_evidence_is_closed(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/api"
kind = "public-api"
owner = "platform"
required_evidence = ["load-test"]
"""
            )
        )

        self.assertEqual(
            ["boundaries[0].required_evidence[0]"],
            [error.path for error in result.errors],
        )

    def test_boundary_rejects_unknown_key(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/internal"
kind = "private"
extra = true
"""
            )
        )

        self.assertEqual(
            ["boundaries[0].extra"], [error.path for error in result.errors]
        )

    def test_boundary_paths_reject_absolute_and_parent_segments(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "/src/api"
kind = "public-api"
owner = "platform"

[[boundaries]]
path = "src/../api"
kind = "public-api"
owner = "platform"
"""
            )
        )

        self.assertEqual(
            ["boundaries[0].path", "boundaries[1].path"],
            [error.path for error in result.errors],
        )

    def test_boundary_contracts_reject_escaping_paths(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/api"
kind = "public-api"
owner = "platform"
contracts = ["../openapi.yaml"]
"""
            )
        )

        self.assertEqual(
            ["boundaries[0].contracts[0]"],
            [error.path for error in result.errors],
        )

    def test_private_boundary_rejects_versioning_contracts_and_evidence(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/internal"
kind = "private"
versioning = "semver"
contracts = ["CONTRACT.md"]
required_evidence = ["contract-tests"]
"""
            )
        )

        self.assertEqual(
            [
                "boundaries[0].versioning",
                "boundaries[0].contracts",
                "boundaries[0].required_evidence",
            ],
            [error.path for error in result.errors],
        )

    def test_internal_versioned_boundary_requires_non_none_versioning(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/first"
kind = "internal-versioned"
owner = "platform"

[[boundaries]]
path = "src/second"
kind = "internal-versioned"
owner = "platform"
versioning = "none"
"""
            )
        )

        self.assertEqual(
            ["boundaries[0].versioning", "boundaries[1].versioning"],
            [error.path for error in result.errors],
        )

    def test_duplicate_normalized_boundary_path_is_rejected(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/./api"
kind = "public-api"
owner = "platform"

[[boundaries]]
path = "src/api"
kind = "public-api"
owner = "platform"
"""
            )
        )

        self.assertEqual(
            ["boundaries[1].path"], [error.path for error in result.errors]
        )
        self.assertIn("duplicates another normalized path", result.errors[0].message)

    def test_v2_boundaries_coexist_with_all_v1_sections(self) -> None:
        result = validate_config(
            tomllib.loads(
                """
schema_version = 2
[project]
type = "service"
context_files = { any_of = ["CONTEXT.md"], all_of = ["AGENTS.md"] }
[scan]
roots = ["src"]
include = ["src/**/*.py"]
exclude = ["src/generated/**"]
[capabilities]
strategy = "explicit"
roots = ["src"]
depth = 1
map = { "src/api" = "api" }
shared_roots = ["src/shared"]
[tests]
patterns = ["tests/**/*.py"]
association = "test-roots"
test_roots = { "tests/api" = "src/api" }
[contracts]
required_for = ["public-api"]
accepted_names = ["CONTRACT.md"]

[[boundaries]]
path = "src/api"
kind = "public-api"
owner = "platform"
versioning = "semver"
contracts = ["CONTRACT.md"]
required_evidence = ["contract-tests", "rollback-plan"]

[[exceptions]]
rule_id = "R-component-contract"
paths = ["src/legacy/**"]
reason = "legacy migration"
owner = "platform"
review_after = "2027-01-01"
"""
            )
        )

        self.assertEqual((), result.errors)
        self.assertEqual("service", result.config.project.type)
        self.assertEqual("explicit", result.config.capabilities.strategy)
        self.assertEqual(1, len(result.config.boundary_entries))
        self.assertEqual(1, len(result.config.exceptions))


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

    def test_v2_boundary_entries_render_with_per_field_origins(self) -> None:
        validation = validate_config(
            tomllib.loads(
                """
schema_version = 2
[[boundaries]]
path = "src/api"
kind = "public-api"
owner = "platform"
versioning = "semver"
contracts = ["openapi.yaml"]
required_evidence = ["contract-tests"]

[[boundaries]]
path = "src/internal"
kind = "private"
"""
            )
        )

        self.assertEqual((), validation.errors)
        rendered = render_effective(resolve_effective(validation.config))

        self.assertIn("boundaries = 2 # origin: file\n", rendered)
        self.assertIn('boundaries[0].path = "src/api" # origin: file\n', rendered)
        self.assertIn('boundaries[0].versioning = "semver" # origin: file\n', rendered)
        self.assertIn('boundaries[1].versioning = "none" # origin: default\n', rendered)
        self.assertIn('boundaries[1].owner = "" # origin: default\n', rendered)

    def test_v1_boundaries_render_without_boundary_entries(self) -> None:
        validation = validate_config(tomllib.loads("schema_version = 1\n"))

        self.assertEqual((), validation.errors)
        rendered = render_effective(resolve_effective(validation.config))

        self.assertIn("boundaries.public = [] # origin: default\n", rendered)
        self.assertIn("boundaries = 0 # origin: default\n", rendered)
        self.assertNotIn("boundaries[0]", rendered)

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

    def test_v2_boundary_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            outside = workspace / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "linked").symlink_to(outside, target_is_directory=True)
            (root / ".garden.toml").write_text(
                """schema_version = 2
[[boundaries]]
path = "linked"
kind = "public-api"
owner = "platform"
""",
                encoding="utf-8",
            )

            result = load_config(root)

        self.assertEqual(
            ["boundaries[0].path"], [error.path for error in result.errors]
        )
        self.assertEqual(
            "path resolves outside the project root", result.errors[0].message
        )

    def test_v2_boundary_contract_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            outside = workspace / "outside"
            boundary = root / "src" / "api"
            boundary.mkdir(parents=True)
            outside.mkdir()
            (outside / "CONTRACT.md").write_text("", encoding="utf-8")
            (boundary / "linked").symlink_to(outside, target_is_directory=True)
            (root / ".garden.toml").write_text(
                """schema_version = 2
[[boundaries]]
path = "src/api"
kind = "public-api"
owner = "platform"
contracts = ["linked/CONTRACT.md"]
""",
                encoding="utf-8",
            )

            result = load_config(root)

        self.assertEqual(
            ["boundaries[0].contracts"], [error.path for error in result.errors]
        )
        self.assertEqual(
            "path resolves outside the project root", result.errors[0].message
        )


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

    def test_config_show_renders_v2_boundary_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".garden.toml").write_text(
                """schema_version = 2
[[boundaries]]
path = "src/api"
kind = "public-api"
owner = "platform"
""",
                encoding="utf-8",
            )

            show_code, shown, show_error = self.run_cli(["config", "show", str(root)])

        self.assertEqual((0, ""), (show_code, show_error))
        self.assertIn("boundaries = 1 # origin: file\n", shown)
        self.assertIn('boundaries[0].path = "src/api" # origin: file\n', shown)

    def test_migrate_config_owner_without_to_schema_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code, _, error = self.run_cli(
                ["migrate-config", directory, "--owner", "somebody"]
            )

        self.assertEqual(1, code)
        self.assertIn("--owner requires --to-schema 2", error)

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

    def test_schema_v2_migration_converts_public_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / ".garden.toml"
            destination.write_text(
                """schema_version = 1
[project]
type = "service"
context_files = { any_of = ["CONTEXT.md"], all_of = ["AGENTS.md"] }
[scan]
roots = ["src"]
include = ["src/**/*.py"]
exclude = ["src/generated/**"]
[capabilities]
strategy = "explicit"
roots = ["src"]
depth = 1
map = { "src/api" = "api" }
shared_roots = ["src/shared"]
[tests]
patterns = ["tests/**/*.py"]
association = "test-roots"
test_roots = { "tests/api" = "src/api" }
[contracts]
required_for = ["public-api"]
accepted_names = ["CONTRACT.md"]
[boundaries]
public = ["src/api", "src/sdk"]
[naming]
registry = "names.txt"
required = true
[documentation]
root_context_required = false
max_context_lines = 123
[[exceptions]]
rule_id = "R-component-contract"
paths = ["src/legacy/**"]
reason = "migration"
owner = "platform"
review_after = "2027-01-01"
""",
                encoding="utf-8",
            )

            code, stdout, stderr = self.run_cli(
                [
                    "migrate-config",
                    str(root),
                    "--to-schema",
                    "2",
                    "--owner",
                    "platform",
                    "--force",
                ]
            )
            content = destination.read_text(encoding="utf-8")
            result = load_config(root)

        self.assertEqual((0, ""), (code, stderr))
        self.assertIn(str(destination), stdout)
        self.assertIn("schema_version = 2\n", content)
        self.assertNotIn("\n[boundaries]\n", content)
        self.assertEqual(2, content.count("[[boundaries]]"))
        self.assertTrue(result.valid)
        effective = resolve_effective(result.config)
        self.assertEqual(
            (
                ("src/api", "public-api", "platform", "none"),
                ("src/sdk", "public-api", "platform", "none"),
            ),
            tuple(
                (
                    entry.path.value,
                    entry.kind.value,
                    entry.owner.value,
                    entry.versioning.value,
                )
                for entry in effective.boundary_entries.value
            ),
        )
        self.assertEqual("service", effective.project.type.value)
        self.assertEqual(("src",), effective.scan.roots.value)
        self.assertEqual("explicit", effective.capabilities.strategy.value)
        self.assertEqual(("public-api",), effective.contracts.required_for.value)
        self.assertEqual("names.txt", effective.naming.registry.value)
        self.assertEqual(123, effective.documentation.max_context_lines.value)
        self.assertEqual(1, len(effective.exceptions.value))

    def test_schema_v2_migration_without_boundaries_needs_no_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".garden.toml").write_text(
                '[project]\ntype = "library"\n', encoding="utf-8"
            )

            code, _, stderr = self.run_cli(
                ["migrate-config", str(root), "--to-schema", "2", "--force"]
            )
            result = load_config(root)

        self.assertEqual((0, ""), (code, stderr))
        self.assertTrue(result.valid)
        effective = resolve_effective(result.config)
        self.assertEqual(2, effective.schema_version.value)
        self.assertEqual((), effective.boundary_entries.value)

    def test_schema_v2_migration_requires_owner_for_public_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / ".garden.toml"
            original = '[boundaries]\npublic = ["src/api"]\n'
            destination.write_text(original, encoding="utf-8")

            code, stdout, stderr = self.run_cli(
                ["migrate-config", str(root), "--to-schema", "2", "--force"]
            )
            content = destination.read_text(encoding="utf-8")

        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("owner is required to migrate public boundaries", stderr)
        self.assertEqual(original, content)

    def test_schema_v2_migration_rejects_existing_v2_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / ".garden.toml"
            original = "schema_version = 2\n"
            destination.write_text(original, encoding="utf-8")

            code, stdout, stderr = self.run_cli(
                ["migrate-config", str(root), "--to-schema", "2", "--force"]
            )
            content = destination.read_text(encoding="utf-8")

        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("already uses schema_version 2", stderr)
        self.assertEqual(original, content)

    def test_schema_v2_migration_requires_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            code, stdout, stderr = self.run_cli(
                ["migrate-config", str(root), "--to-schema", "2"]
            )

        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("configuration not found", stderr)

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

    def test_schema_v2_atomic_failure_preserves_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / ".garden.toml"
            original = "schema_version = 1\n"
            destination.write_text(original, encoding="utf-8")
            before = sorted(path.name for path in root.iterdir())

            with patch(
                "garden_config.os.replace", side_effect=OSError("replace failed")
            ):
                code, stdout, stderr = self.run_cli(
                    ["migrate-config", str(root), "--to-schema", "2", "--force"]
                )

            after = sorted(path.name for path in root.iterdir())
            content = destination.read_text(encoding="utf-8")

        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("replace failed", stderr)
        self.assertEqual(before, after)
        self.assertEqual(original, content)

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

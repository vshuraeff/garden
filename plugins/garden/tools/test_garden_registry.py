from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from garden_registry import DEFAULT_REGISTRY_PATH, load_registry  # noqa: E402
from validate_registry import (  # noqa: E402
    _benchmark_map_findings,
    main as validate_registry_main,
)


BENCHMARK_MAP_PATH = TOOLS_DIR.parents[2] / "benchmarks" / "principle-rule-map.json"


class GardenRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.content = DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_registry(self, content: str) -> Path:
        path = self.root / "garden-rules.toml"
        path.write_text(content, encoding="utf-8")
        return path

    def replace_table_value(
        self,
        content: str,
        section: str,
        identifier: str,
        field: str,
        old_value: str,
        new_value: str,
    ) -> str:
        marker = f'[[{section}]]\nid = "{identifier}"'
        start = content.index(marker)
        end = content.find("\n[[", start + len(marker))
        if end == -1:
            end = len(content)
        block = content[start:end]
        old = f"{field} = {old_value}"
        self.assertIn(old, block)
        replacement = block.replace(old, f"{field} = {new_value}", 1)
        return content[:start] + replacement + content[end:]

    def remove_table(self, content: str, section: str, identifier: str) -> str:
        marker = f'[[{section}]]\nid = "{identifier}"'
        start = content.index(marker)
        end = content.find("\n[[", start + len(marker))
        if end == -1:
            return content[:start]
        return content[:start] + content[end + 1 :]

    def run_validator(self, registry_path: Path) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = validate_registry_main(registry_path=registry_path)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_real_registry_loads_with_expected_counts(self) -> None:
        registry = load_registry()

        self.assertEqual(42, len(registry.rules))
        self.assertEqual(12, len(registry.runtime_checks))
        self.assertEqual(6, len(registry.principles))
        self.assertEqual("Recoverable relationships", registry.rule("G-DISC-001").title)
        self.assertEqual(
            "Graph-resolvable Discoverability",
            registry.principle("G").name,
        )
        self.assertIsNotNone(registry.rule("G-DISC-001").digest)
        self.assertIsNone(registry.rule("G-DISC-006").digest)
        self.assertEqual(
            "required naming registry file was not found",
            registry.runtime_check("N-NAMING-MISSING").title,
        )

    def test_required_rule_digest_must_be_non_empty(self) -> None:
        content = self.replace_table_value(
            self.content,
            "rules",
            "G-DISC-001",
            "digest",
            '"Make production domain relationships recoverable through grep, an AST or LSP, a symbol index, a route map, a plugin or schema registry, or generated wiring. Back dynamic dispatch with a machine-readable manifest, schema, registry, or generated map."',
            '""',
        )
        path = self.write_registry(content)

        with self.assertRaisesRegex(ValueError, "digest"):
            load_registry(path)

    def test_experimental_rule_digest_must_be_absent(self) -> None:
        content = self.replace_table_value(
            self.content,
            "rules",
            "G-DISC-006",
            "level",
            '"EXPERIMENTAL"',
            '"EXPERIMENTAL"\ndigest = "not allowed"',
        )
        path = self.write_registry(content)

        with self.assertRaisesRegex(ValueError, "must be absent"):
            load_registry(path)

    def test_invalid_implementation_is_rejected(self) -> None:
        content = self.replace_table_value(
            self.content,
            "rules",
            "G-DISC-001",
            "implementation",
            '"planned"',
            '"invalid"',
        )
        path = self.write_registry(content)

        with self.assertRaisesRegex(ValueError, "implementation"):
            load_registry(path)

    def test_cross_section_duplicate_id_is_rejected(self) -> None:
        content = self.replace_table_value(
            self.content,
            "runtime_checks",
            "D-project-scan-limit",
            "principle",
            '"D"',
            '"G"',
        )
        content = self.replace_table_value(
            content,
            "runtime_checks",
            "D-project-scan-limit",
            "id",
            '"D-project-scan-limit"',
            '"G-DISC-001"',
        )
        path = self.write_registry(content)

        with self.assertRaisesRegex(ValueError, "both sections"):
            load_registry(path)

    def test_real_registry_validator_passes(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = validate_registry_main()

        self.assertEqual(0, result)
        self.assertEqual("", stderr.getvalue())
        self.assertIn("rule registry validation passed", stdout.getvalue())

    def test_benchmark_map_matches_registry_principles(self) -> None:
        findings = _benchmark_map_findings(
            load_registry(), DEFAULT_REGISTRY_PATH, BENCHMARK_MAP_PATH
        )

        self.assertEqual([], findings)

    def test_benchmark_map_detects_principle_mismatch(self) -> None:
        content = BENCHMARK_MAP_PATH.read_text(encoding="utf-8").replace(
            '"A-colocated-tests": "A"',
            '"A-colocated-tests": "G"',
            1,
        )
        benchmark_map_path = self.root / "principle-rule-map.json"
        benchmark_map_path.write_text(content, encoding="utf-8")

        findings = _benchmark_map_findings(
            load_registry(), DEFAULT_REGISTRY_PATH, benchmark_map_path
        )

        self.assertEqual(1, len(findings))
        self.assertIn("maps to principle G", findings[0].reason)
        self.assertIn("resolves to A", findings[0].reason)

    def test_validator_detects_wrong_rule_level(self) -> None:
        content = self.replace_table_value(
            self.content,
            "rules",
            "G-DISC-004",
            "level",
            '"DEFAULT"',
            '"REQUIRED"',
        )
        path = self.write_registry(content)

        result, _, stderr = self.run_validator(path)

        self.assertEqual(1, result)
        self.assertIn("registry level for G-DISC-004", stderr)

    def test_validator_detects_missing_rule(self) -> None:
        path = self.write_registry(
            self.remove_table(self.content, "rules", "G-DISC-006")
        )

        result, _, stderr = self.run_validator(path)

        self.assertEqual(1, result)
        self.assertIn("G-DISC-006 is missing from the registry", stderr)

    def test_validator_detects_duplicate_runtime_alias(self) -> None:
        content = self.replace_table_value(
            self.content,
            "rules",
            "G-DISC-001",
            "runtime_aliases",
            "[]",
            '["A-colocated-tests"]',
        )
        path = self.write_registry(content)

        result, _, stderr = self.run_validator(path)

        self.assertEqual(1, result)
        self.assertIn("assigned to multiple rules", stderr)

    def test_validator_detects_runtime_correspondence_mismatch(self) -> None:
        repository_root = TOOLS_DIR.parents[2]
        principles_path = self.root / "docs" / "reference" / "principles.md"
        checklist_path = self.root / "docs" / "reference" / "checklist.md"
        benchmark_map_path = self.root / "benchmarks" / "principle-rule-map.json"
        sources = (
            (repository_root / "docs" / "reference" / "checklist.md", checklist_path),
            (
                repository_root / "benchmarks" / "principle-rule-map.json",
                benchmark_map_path,
            ),
        )
        for source, destination in sources:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        principles = (
            repository_root / "docs" / "reference" / "principles.md"
        ).read_text(encoding="utf-8")
        old_row = (
            "| `N-KNOW-005` | `N-context-budget` | "
            "Bounded requisite context and progressive disclosure |"
        )
        self.assertIn(old_row, principles)
        principles_path.parent.mkdir(parents=True, exist_ok=True)
        principles_path.write_text(
            principles.replace(
                old_row,
                "| `G-DISC-001` | `N-context-budget` | "
                "Bounded requisite context and progressive disclosure |",
                1,
            ),
            encoding="utf-8",
        )

        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = validate_registry_main(repository_root=self.root)

        self.assertEqual(1, result)
        self.assertIn("runtime correspondence ID N-context-budget", stderr.getvalue())
        self.assertIn("RUNTIME_ALIAS_TABLE targets", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

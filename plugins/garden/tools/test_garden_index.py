from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from config_schema import EffectiveConfig, ResolvedValue  # noqa: E402
from garden_config import load_config, resolve_effective  # noqa: E402
from garden_index import ProjectIndex, build_project_index  # noqa: E402
import garden_scanner  # noqa: E402


def _effective_config(root: Path, sections: str = "") -> EffectiveConfig:
    (root / ".garden.toml").write_text(
        "schema_version = 1\n"
        f"{sections.strip()}\n"
        "[documentation]\n"
        "root_context_required = false\n",
        encoding="utf-8",
    )
    loaded = load_config(root)
    if loaded.errors:
        raise AssertionError(loaded.errors)
    return resolve_effective(loaded.config)


def _all_indexed_paths(index: ProjectIndex) -> set[Path]:
    paths = {
        *index.source_files,
        *index.test_files,
        *index.contract_artifacts,
        *index.unknown_paths,
    }
    for grouped in (
        *index.source_by_capability.values(),
        *index.tests_by_capability.values(),
    ):
        paths.update(grouped)
    return paths


class ProjectIndexTests(unittest.TestCase):
    def test_build_uses_exactly_one_walk_in_legacy_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch.object(
                garden_scanner,
                "_walk_files",
                wraps=garden_scanner._walk_files,
            ) as walk:
                build_project_index(root, None)

        walk.assert_called_once_with(root)

    def test_build_uses_exactly_one_walk_in_configured_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            effective = _effective_config(root)
            with patch.object(
                garden_scanner,
                "_walk_files",
                wraps=garden_scanner._walk_files,
            ) as walk:
                build_project_index(root, effective)

        self.assertEqual(1, walk.call_count)

    def test_configured_root_restricts_every_index_classification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            effective = _effective_config(
                root,
                '[scan]\nroots = ["src"]\ninclude = ["**/*.py"]\n'
                '[capabilities]\nstrategy = "children"\nroots = ["src"]\ndepth = 1',
            )
            inside = root / "src" / "orders" / "handler.py"
            outside = root / "other" / "outside.py"
            inside.parent.mkdir(parents=True)
            outside.parent.mkdir(parents=True)
            inside.write_text("pass\n", encoding="utf-8")
            outside.write_text("pass\n", encoding="utf-8")

            index = build_project_index(root, effective)

        self.assertIn(inside, index.source_files)
        self.assertNotIn(outside, _all_indexed_paths(index))

    def test_overlapping_roots_do_not_duplicate_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            effective = _effective_config(
                root,
                '[scan]\nroots = ["src", "src/nested"]\n'
                'include = ["**/*.py"]\n'
                '[capabilities]\nstrategy = "children"\nroots = ["src"]\ndepth = 1',
            )
            source = root / "src" / "nested" / "handler.py"
            source.parent.mkdir(parents=True)
            source.write_text("pass\n", encoding="utf-8")

            index = build_project_index(root, effective)

        self.assertEqual((source,), index.source_files)
        self.assertEqual((source,), index.source_by_capability["src/nested"])

    def test_missing_root_is_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            effective = _effective_config(
                root,
                '[scan]\nroots = ["missing", "src"]\ninclude = ["**/*.py"]',
            )
            source = root / "src" / "handler.py"
            source.parent.mkdir()
            source.write_text("pass\n", encoding="utf-8")

            index = build_project_index(root, effective)

        self.assertTrue(index.complete)
        self.assertEqual(("missing",), index.missing_roots)
        self.assertIn(source, index.source_files)

    def test_root_outside_project_is_not_walked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            outside_root = base / "outside"
            root.mkdir()
            outside_root.mkdir()
            outside = outside_root / "outside.py"
            outside.write_text("pass\n", encoding="utf-8")
            effective = _effective_config(root, '[scan]\ninclude = ["**/*.py"]')
            effective = replace(
                effective,
                scan=replace(
                    effective.scan,
                    roots=ResolvedValue(("../outside",), "file"),
                ),
            )

            index = build_project_index(root, effective)

        self.assertTrue(index.complete)
        self.assertEqual(("../outside",), index.missing_roots)
        self.assertNotIn(outside, _all_indexed_paths(index))

    def test_excluded_directory_is_pruned_before_entry_counting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            effective = _effective_config(
                root,
                '[scan]\ninclude = ["**/*.py"]\nexclude = ["big/**"]',
            )
            big = root / "big"
            big.mkdir()
            for number in range(50):
                (big / f"ignored-{number}.py").write_text("pass\n", encoding="utf-8")
            source_dir = root / "src"
            source_dir.mkdir()
            sources = tuple(source_dir / f"kept-{number}.py" for number in range(2))
            for source in sources:
                source.write_text("pass\n", encoding="utf-8")

            with patch("garden_core.MAX_SCAN_ENTRIES", 5):
                index = build_project_index(root, effective)

        self.assertTrue(index.complete)
        self.assertIsNone(index.exceeded_budget)
        self.assertTrue(set(sources).issubset(index.source_files))
        self.assertFalse(any(big in path.parents for path in _all_indexed_paths(index)))

    def test_nested_contract_is_discovered_at_any_depth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            effective = _effective_config(
                root,
                '[contracts]\naccepted_names = ["CONTRACT.md"]',
            )
            contract = root / "src" / "a" / "b" / "c" / "CONTRACT.md"
            contract.parent.mkdir(parents=True)
            contract.write_text("Version: 1.0.0\n", encoding="utf-8")

            index = build_project_index(root, effective)

        self.assertEqual((contract,), index.contract_artifacts)
        self.assertNotIn(contract, index.source_files)
        self.assertNotIn(contract, index.unknown_paths)

    def test_entry_budget_exhaustion_returns_partial_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            effective = _effective_config(
                root,
                '[scan]\nroots = ["a", "b"]\ninclude = ["**/*.py"]',
            )
            first = root / "a" / "first.py"
            first.parent.mkdir()
            first.write_text("pass\n", encoding="utf-8")
            second_root = root / "b"
            second_root.mkdir()
            for number in range(2):
                (second_root / f"later-{number}.py").write_text(
                    "pass\n", encoding="utf-8"
                )

            with patch("garden_core.MAX_SCAN_ENTRIES", 2):
                index = build_project_index(root, effective)

        self.assertFalse(index.complete)
        self.assertEqual("entries", index.exceeded_budget)
        self.assertTrue(index.scan_errors)
        self.assertEqual("project scan exceeds 2 entries", index.scan_errors[0])
        self.assertEqual((first,), index.source_files)

    def test_walk_oserror_returns_incomplete_index_without_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch.object(
                garden_scanner,
                "_walk_files",
                side_effect=OSError("forced walk failure"),
            ):
                index = build_project_index(root, None)

        self.assertFalse(index.complete)
        self.assertIsNone(index.exceeded_budget)
        self.assertEqual(("forced walk failure",), index.scan_errors)

    def test_legacy_mode_builds_nontrivial_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "orders" / "handler.py"
            source.parent.mkdir()
            source.write_text("pass\n", encoding="utf-8")
            root_source = root / "tool.py"
            root_source.write_text("pass\n", encoding="utf-8")
            contract = root / "CONTRACT.md"
            contract.write_text("Version: 1.0.0\n", encoding="utf-8")
            readme = root / "README.md"
            readme.write_text("# project\n", encoding="utf-8")

            index = build_project_index(root, None)

        self.assertEqual((source, root_source), index.source_files)
        self.assertEqual((source,), index.source_by_capability["orders"])
        self.assertEqual((), index.test_files)
        self.assertEqual({}, index.tests_by_capability)
        self.assertEqual((contract,), index.contract_artifacts)
        self.assertEqual((readme,), index.unknown_paths)

    def test_scanner_exposes_structured_entry_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "file.py").write_text("pass\n", encoding="utf-8")
            with (
                patch("garden_core.MAX_SCAN_ENTRIES", 0),
                self.assertRaises(garden_scanner.ScanLimitExceeded) as raised,
            ):
                list(garden_scanner._walk_files(root))

        self.assertEqual("project scan exceeds 0 entries", str(raised.exception))
        self.assertEqual("entries", raised.exception.budget)
        self.assertEqual(0, raised.exception.limit)


if __name__ == "__main__":
    unittest.main()

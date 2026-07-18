from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from matrix_compare import evaluate_matrix_identity
from normalized_artifacts import _normalized_json, _normalized_jsonl


CELLS = (
    "ubuntu-latest-3.11",
    "ubuntu-latest-3.14",
    "macos-latest-3.11",
    "macos-latest-3.14",
)
CELL_ENVIRONMENTS = {
    "ubuntu-latest-3.11": ("linux", "3.11.9"),
    "ubuntu-latest-3.14": ("linux", "3.14.0"),
    "macos-latest-3.11": ("macos", "3.11.9"),
    "macos-latest-3.14": ("macos", "3.14.0"),
}


def artifact_bundle(*, passed: bool = True) -> dict[str, object]:
    return {
        "migration.jsonl": [
            {"case_id": "migration-case", "passed": passed},
        ],
        "summary.json": {"matrix_identity": True},
    }


class MatrixComparisonTests(unittest.TestCase):
    def test_identical_inputs_across_all_cells_pass(self) -> None:
        result = evaluate_matrix_identity(
            CELLS, {cell: artifact_bundle() for cell in CELLS}
        )

        self.assertTrue(result.passed)
        self.assertEqual((), result.missing_cells)
        self.assertEqual((), result.unexpected_cells)
        self.assertEqual((), result.differences)

    def test_environment_identity_differences_are_normalized_before_comparison(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifacts = {}
            for cell in CELLS:
                platform, python_version = CELL_ENVIRONMENTS[cell]
                cell_dir = Path(directory) / cell
                cell_dir.mkdir()
                migration_path = cell_dir / "migration.jsonl"
                migration_path.write_text(
                    json.dumps(
                        {
                            "case_id": "migration-case",
                            "passed": True,
                            "platform": platform,
                            "python_version": python_version,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                summary_path = cell_dir / "summary.json"
                summary_path.write_text(
                    json.dumps(
                        {
                            "matrix_identity": True,
                            "toolchain": {
                                "platform": platform,
                                "python_version": python_version,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                artifacts[cell] = {
                    "migration.jsonl": _normalized_jsonl(migration_path),
                    "summary.json": _normalized_json(summary_path),
                }

        result = evaluate_matrix_identity(CELLS, artifacts)

        self.assertTrue(result.passed)
        self.assertEqual((), result.differences)

    def test_differing_record_names_cell_and_artifact(self) -> None:
        artifacts = {cell: artifact_bundle() for cell in CELLS}
        differing_cell = CELLS[-1]
        artifacts[differing_cell] = artifact_bundle(passed=False)

        result = evaluate_matrix_identity(CELLS, artifacts)

        self.assertFalse(result.passed)
        self.assertEqual(1, len(result.differences))
        difference = result.differences[0]
        self.assertEqual(differing_cell, difference.cell)
        self.assertEqual("migration.jsonl", difference.artifact)
        self.assertIn("record 1", difference.detail)

    def test_missing_cell_fails_with_clear_name(self) -> None:
        missing_cell = CELLS[-1]
        result = evaluate_matrix_identity(
            CELLS,
            {cell: artifact_bundle() for cell in CELLS if cell != missing_cell},
        )

        self.assertFalse(result.passed)
        self.assertEqual((missing_cell,), result.missing_cells)
        self.assertEqual((), result.differences)


if __name__ == "__main__":
    unittest.main()

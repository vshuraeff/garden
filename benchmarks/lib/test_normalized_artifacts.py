from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from normalized_artifacts import (
    _checksum_names,
    _normalized_artifact,
    _normalized_json,
    _normalized_jsonl,
)


class NormalizedArtifactTests(unittest.TestCase):
    def test_json_strips_top_level_and_toolchain_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.json"
            path.write_text(
                json.dumps(
                    {
                        "generated_at": "now",
                        "garden_commit": "garden",
                        "platform": "macos",
                        "python_version": "3.14.0",
                        "repository_commit": "repository",
                        "result": "kept",
                        "toolchain": {
                            "garden_commit": "nested-garden",
                            "platform": "macos",
                            "python_version": "3.14.0",
                            "repository_commit": "nested-repository",
                            "version": "kept",
                        },
                    }
                ),
                encoding="utf-8",
            )

            normalized = _normalized_json(path)
            dispatched = _normalized_artifact(path)

        self.assertEqual(
            {"result": "kept", "toolchain": {"version": "kept"}}, normalized
        )
        self.assertEqual(normalized, dispatched)

    def test_jsonl_strips_timing_provenance_and_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "migration.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "elapsed_ns": 10,
                        "garden_commit": "garden",
                        "repository_commit": "repository",
                        "platform": "macos",
                        "python_version": "3.14.0",
                        "generated_at": "kept",
                        "case_id": "case",
                        "toolchain": {
                            "platform": "macos",
                            "python_version": "3.14.0",
                            "version": "kept",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            normalized = _normalized_jsonl(path)
            dispatched = _normalized_artifact(path)

        expected = [
            {
                "generated_at": "kept",
                "case_id": "case",
                "toolchain": {"version": "kept"},
            }
        ]
        self.assertEqual(expected, normalized)
        self.assertEqual(expected, dispatched)

    def test_checksum_normalization_keeps_only_file_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sha256sums.txt"
            path.write_text(
                "abc  migration.jsonl\ndef  summary.json\n", encoding="utf-8"
            )

            normalized = _checksum_names(path)
            dispatched = _normalized_artifact(path)

        self.assertEqual(["migration.jsonl", "summary.json"], normalized)
        self.assertEqual(normalized, dispatched)


if __name__ == "__main__":
    unittest.main()

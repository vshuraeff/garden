from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mutation_ops import (
    apply_mutation,
    hash_path,
    materialize_files,
    reverse_mutation,
    reversal_is_exact,
)


class MutationOperationTests(unittest.TestCase):
    def test_replace_round_trip_and_hash_stability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize_files(root, {"config.txt": "before\n"})
            original = hash_path(root / "config.txt")
            state = apply_mutation(
                root,
                {
                    "operation": {
                        "kind": "replace",
                        "path": "config.txt",
                        "old": "before",
                        "new": "after",
                    }
                },
            )

            self.assertEqual(original, state.before_sha256)
            self.assertNotEqual(state.before_sha256, state.after_sha256)
            self.assertEqual(state.after_sha256, hash_path(root / "config.txt"))
            self.assertEqual(1, len(state.before_file_sha256))
            self.assertEqual(1, len(state.after_file_sha256))
            reverse_mutation(root, state)
            self.assertTrue(reversal_is_exact(root, state))
            self.assertEqual("before\n", (root / "config.txt").read_text())

    def test_new_file_and_delete_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            created = apply_mutation(
                root,
                {
                    "operation": {
                        "kind": "write",
                        "path": "new/file.txt",
                        "content": "created",
                    }
                },
            )
            self.assertIsNone(created.before_sha256)
            reverse_mutation(root, created)
            self.assertFalse((root / "new/file.txt").exists())

            materialize_files(root, {"old/file.txt": "preserved"})
            deleted = apply_mutation(
                root,
                {"operation": {"kind": "delete", "path": "old/file.txt"}},
            )
            self.assertFalse((root / "old/file.txt").exists())
            reverse_mutation(root, deleted)
            self.assertEqual("preserved", (root / "old/file.txt").read_text())

    def test_generated_tree_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = apply_mutation(
                root,
                {
                    "operation": {
                        "kind": "generate-files",
                        "path": "bulk",
                        "count": 4,
                        "prefix": "case",
                        "content": "x",
                    }
                },
            )
            first_hash = state.after_sha256
            self.assertEqual((), state.before_file_sha256)
            self.assertEqual(4, len(state.after_file_sha256))
            reverse_mutation(root, state)
            self.assertTrue(reversal_is_exact(root, state))
            repeated = apply_mutation(
                root,
                {
                    "operation": {
                        "kind": "generate-files",
                        "path": "bulk",
                        "count": 4,
                        "prefix": "case",
                        "content": "x",
                    }
                },
            )
            self.assertEqual(first_hash, repeated.after_sha256)


if __name__ == "__main__":
    unittest.main()

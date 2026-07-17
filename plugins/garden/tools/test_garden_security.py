from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from config_schema import MAX_PATTERN_LENGTH, MAX_PATTERNS  # noqa: E402
from garden_config import load_config, migrate_config  # noqa: E402
from garden_rules import (  # noqa: E402
    _matches_path_pattern,
    inspect_file,
    inspect_project,
)
from garden_scanner import (  # noqa: E402
    MAX_CHECKED_FILE_BYTES,
    ScanLimitExceeded,
    _bounded_binary_lines,
    _decode_line,
)


class GardenSecurityTests(unittest.TestCase):
    @unittest.skipIf(
        sys.platform == "win32",
        "GARDEN v1 does not support Windows; see docs/reference/platform-support.md",
    )
    def test_windows_platform_constraint_is_explicit(self) -> None:
        """record the documented POSIX-only platform policy."""
        self.assertNotEqual("win32", sys.platform)

    def test_symlinked_capability_directory_escape_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            outside = workspace / "outside"
            root.mkdir()
            (root / ".garden.toml").write_text(
                "schema_version = 1\n"
                '[scan]\ninclude = ["**/*.py"]\n'
                '[capabilities]\nstrategy = "children"\nroots = ["."]\n'
                "[documentation]\nroot_context_required = false\n",
                encoding="utf-8",
            )
            capability = root / "orders"
            capability.mkdir()
            source = capability / "handler.py"
            source.write_text("pass\n", encoding="utf-8")

            def swap_capability_for_symlink(relative: Path, config: object) -> bool:
                self.assertEqual(Path("orders/handler.py"), relative)
                self.assertIsNotNone(config)
                capability.rename(outside)
                capability.symlink_to(outside, target_is_directory=True)
                return True

            with patch(
                "garden_rules._is_configured_source_file",
                side_effect=swap_capability_for_symlink,
            ):
                findings = inspect_file(source, root)
            is_real_symlink = capability.is_symlink()

        self.assertTrue(is_real_symlink)
        self.assertEqual([], findings)

    def test_parent_segment_in_config_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".garden.toml").write_text(
                '[scan]\ninclude = ["../outside/**"]\n', encoding="utf-8"
            )

            result = load_config(root)

        self.assertTrue(result.present)
        self.assertIsNone(result.config)
        self.assertEqual("scan.include[0]", result.errors[0].path)
        self.assertIn("parent path segments", result.errors[0].message)

    def test_oversized_checked_file_raises_scan_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            oversized = Path(directory) / "CONTEXT.md"
            oversized.write_bytes(b"x" * (MAX_CHECKED_FILE_BYTES + 4096))

            with self.assertRaisesRegex(ScanLimitExceeded, "checked bytes"):
                list(_bounded_binary_lines(oversized))

    def test_malformed_utf8_is_replaced_and_rule_check_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "naming-registry.txt").write_text(
                "orders: orders\n", encoding="utf-8"
            )
            capability = root / "orders"
            capability.mkdir()
            contract = capability / "CONTRACT.md"
            contract.write_bytes(b"\xff\n")

            decoded = _decode_line(b"\xff\n")
            first = inspect_file(contract, root)
            second = inspect_file(contract, root)

        self.assertEqual("\ufffd", decoded)
        self.assertEqual(first, second)
        self.assertEqual(["R-contract-version"], [finding.rule for finding in first])

    def test_malicious_glob_limits_and_pathological_valid_match(self) -> None:
        relative = Path(*(["segment"] * 60), "handler.py")
        pattern = "/".join(["**", "segment"] * 60 + ["*.py"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            too_long = "a" * (MAX_PATTERN_LENGTH + 1)
            (root / ".garden.toml").write_text(
                f'[scan]\ninclude = ["{too_long}"]\n', encoding="utf-8"
            )
            long_result = load_config(root)

            entries = ", ".join(f'"path-{index}"' for index in range(MAX_PATTERNS + 1))
            (root / ".garden.toml").write_text(
                f"[scan]\ninclude = [{entries}]\n", encoding="utf-8"
            )
            count_result = load_config(root)
            (root / ".garden.toml").write_text(
                f'[scan]\ninclude = ["{pattern}"]\n', encoding="utf-8"
            )
            pathological_result = load_config(root)

        self.assertIsNone(long_result.config)
        self.assertIn(
            f"at most {MAX_PATTERN_LENGTH} characters", long_result.errors[0].message
        )
        self.assertIsNone(count_result.config)
        self.assertIn(
            f"at most {MAX_PATTERNS} entries",
            next(
                error.message
                for error in count_result.errors
                if error.path == "scan.include"
            ),
        )
        self.assertEqual((), pathological_result.errors)

        started = time.monotonic()
        matched = _matches_path_pattern(relative, (pattern,))
        elapsed = time.monotonic() - started

        self.assertTrue(matched)
        self.assertLess(elapsed, 1.0, f"pathological glob took {elapsed:.3f}s")

    def test_interrupted_atomic_write_cleans_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "naming-registry.txt").write_text(
                "orders: orders\n", encoding="utf-8"
            )
            before = sorted(path.name for path in root.iterdir())

            with patch("garden_config.os.replace", side_effect=OSError("interrupted")):
                with self.assertRaisesRegex(OSError, "interrupted"):
                    migrate_config(root)

            after = sorted(path.name for path in root.iterdir())

        self.assertEqual(before, after)
        self.assertEqual(["naming-registry.txt"], after)

    def test_toctou_file_swap_degrades_to_a_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "naming-registry.txt").write_text(
                "orders: orders\n", encoding="utf-8"
            )
            capability = root / "orders"
            capability.mkdir()
            source = capability / "handler.py"
            source.write_text("pass\n", encoding="utf-8")

            def racing_walk(scan_root: Path):
                self.assertEqual(root, scan_root)
                yield source
                source.unlink()
                source.mkdir()

            with patch("garden_rules._walk_files", side_effect=racing_walk):
                report = inspect_project(root)
            swapped_to_directory = source.is_dir()

        self.assertTrue(report["active"])
        self.assertIsInstance(report["findings"], list)
        self.assertTrue(swapped_to_directory)

    def test_configured_scan_limit_does_not_claim_tests_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / ".garden.toml").write_text(
                "schema_version = 1\n"
                '[scan]\ninclude = ["**/*.py"]\n'
                '[capabilities]\nstrategy = "children"\nroots = ["."]\n'
                '[tests]\npatterns = ["**/test_*.py"]\n'
                "[documentation]\nroot_context_required = false\n",
                encoding="utf-8",
            )
            capability = root / "orders"
            capability.mkdir()
            (capability / "CONTRACT.md").write_text(
                "Version: 1.0.0\n", encoding="utf-8"
            )
            source = capability / "handler.py"
            source.write_text("pass\n", encoding="utf-8")

            def limited_walk(scan_root: Path, **kwargs: object):
                self.assertEqual(root, scan_root)
                yield source
                # entries is deterministic and must remain an error-severity limit.
                raise ScanLimitExceeded("forced mid-scan limit", budget="entries")

            with patch("garden_scanner._walk_files", side_effect=limited_walk) as walk:
                report = inspect_project(root)

        rules = [finding["rule"] for finding in report["findings"]]
        walk.assert_called_once()
        self.assertIn("D-project-scan-limit", rules)
        self.assertNotIn("A-colocated-tests", rules)


if __name__ == "__main__":
    unittest.main()

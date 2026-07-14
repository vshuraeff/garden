from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = TOOLS_DIR.parents[2]
sys.path.insert(0, str(TOOLS_DIR))

from garden_cli import main as garden_cli_main  # noqa: E402
from garden_core import find_project_activation, inspect_project  # noqa: E402


class GardenSelfAuditTests(unittest.TestCase):
    def run_cli(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = garden_cli_main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_repository_root_is_active_from_its_config(self) -> None:
        activation = find_project_activation(REPOSITORY_ROOT)

        self.assertIsNotNone(activation)
        self.assertEqual(REPOSITORY_ROOT, activation.root)
        self.assertEqual("config", activation.kind)

    def test_repository_self_audit_has_no_errors(self) -> None:
        report = inspect_project(REPOSITORY_ROOT)

        self.assertTrue(report["active"])
        self.assertEqual(0, report["summary"]["errors"])

    def test_plain_inspect_reports_an_inactive_project_without_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = inspect_project(Path(directory))

        self.assertFalse(report["active"])
        self.assertEqual(0, report["summary"]["errors"])

    def test_strict_inspect_rejects_an_inactive_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plain_code, plain_output, plain_error = self.run_cli(["inspect", str(root)])
            strict_code, strict_output, strict_error = self.run_cli(
                ["inspect", "--strict", str(root)]
            )

        self.assertEqual((0, ""), (plain_code, plain_error))
        self.assertIn('"active": false', plain_output)
        self.assertEqual((1, ""), (strict_code, strict_error))
        self.assertIn('"active": false', strict_output)


if __name__ == "__main__":
    unittest.main()

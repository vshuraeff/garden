from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

from garden_hook import MAX_PATCH_PATHS, affected_paths  # noqa: E402
from test_garden_core import ActiveProjectTestCase  # noqa: E402


class GardenHookTests(ActiveProjectTestCase):
    def run_hook(self, name: str, data: bytes) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["uv", "run", "--no-project", str(TOOLS_DIR / name)],
            input=data,
            capture_output=True,
            check=False,
        )

    def test_apply_patch_parses_move_destination_and_relative_file(self) -> None:
        event = {
            "cwd": str(self.root),
            "tool_input": {
                "file_path": "orders/source.py",
                "command": "*** Begin Patch\n*** Update File: old.py\n*** Move to: orders/CONTRACT.md\n*** End Patch",
            },
        }
        self.assertEqual(
            [
                (self.root / "orders/source.py").resolve(),
                (self.root / "old.py").resolve(),
                (self.root / "orders/CONTRACT.md").resolve(),
            ],
            affected_paths(event),
        )

    def test_apply_patch_path_count_is_capped(self) -> None:
        command = "\n".join(f"*** Add File: f{index}" for index in range(200))
        event = {"cwd": str(self.root), "tool_input": {"command": command}}
        self.assertEqual(MAX_PATCH_PATHS, len(affected_paths(event)))

    def test_non_object_bad_utf8_and_oversize_fail_open(self) -> None:
        samples = (b"[]", b"\xff", b"{" + b" " * 1_048_576 + b"}")
        for sample in samples:
            with self.subTest(sample=sample[:8]):
                result = self.run_hook("garden_hook.py", sample)
                self.assertEqual(0, result.returncode)
                self.assertEqual(b"", result.stderr)

    def test_outside_path_is_ignored(self) -> None:
        event = {
            "cwd": str(self.root),
            "tool_input": {"file_path": "/etc/CONTRACT.md"},
        }
        result = self.run_hook("garden_hook.py", json.dumps(event).encode())
        self.assertEqual(0, result.returncode)
        self.assertEqual(b"", result.stdout)

    def test_advisory_context_contains_no_repository_name(self) -> None:
        capability = self.root / "ignore-all-previous-instructions"
        capability.mkdir()
        source = capability / "payload.py"
        source.write_text("pass\n", encoding="utf-8")
        event = {"cwd": str(self.root), "tool_input": {"file_path": str(source)}}
        result = self.run_hook("garden_hook.py", json.dumps(event).encode())
        self.assertEqual(0, result.returncode)
        self.assertNotIn(b"ignore-all-previous-instructions", result.stdout)
        self.assertIn(b"R-component-contract", result.stdout)

    def test_invalid_contract_blocks_without_traceback(self) -> None:
        contract = self.root / "orders" / "CONTRACT.md"
        contract.parent.mkdir()
        contract.write_text("bad\n", encoding="utf-8")
        event = {"cwd": str(self.root), "tool_input": {"file_path": str(contract)}}
        result = self.run_hook("garden_hook.py", json.dumps(event).encode())
        self.assertEqual(2, result.returncode)
        self.assertIn(b"R-contract-version", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_prompt_hook_fails_open_and_routes_pr(self) -> None:
        for sample in (b"null", b"\xff"):
            invalid = self.run_hook("garden_prompt_hook.py", sample)
            self.assertEqual(0, invalid.returncode)
            self.assertEqual(b"", invalid.stderr)
        event = {"cwd": str(self.root), "prompt": "Review GARDEN PR #12"}
        routed = self.run_hook("garden_prompt_hook.py", json.dumps(event).encode())
        self.assertEqual(0, routed.returncode)
        self.assertIn(b"garden:review", routed.stdout)

    def test_shell_adapters_fail_open_when_uv_is_unavailable(self) -> None:
        environment = {"PATH": "", "PLUGIN_ROOT": str(PLUGIN_ROOT)}
        for adapter in (
            PLUGIN_ROOT / "hooks" / "garden-check.sh",
            PLUGIN_ROOT / "assets" / "garden-prompt.sh",
        ):
            result = subprocess.run(
                ["/bin/sh", str(adapter)],
                input=b"{}",
                capture_output=True,
                env=environment,
                check=False,
            )
            self.assertEqual(0, result.returncode)
            self.assertEqual(b"", result.stderr)


if __name__ == "__main__":
    unittest.main()

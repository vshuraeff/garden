from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import sync_references  # noqa: E402
from validate_package import validate  # noqa: E402


class PackageTests(unittest.TestCase):
    def test_reference_pairs_are_the_documented_pairs(self) -> None:
        expected = {
            (
                "docs/reference/principles.md",
                "plugins/garden/references/principles.md",
            ),
            (
                "docs/reference/checklist.md",
                "plugins/garden/references/checklist.md",
            ),
            (
                "docs/reference/glossary.md",
                "plugins/garden/references/glossary.md",
            ),
            (
                "docs/how-to/review-code-as-agent.md",
                "plugins/garden/references/review-procedure.md",
            ),
        }
        actual = {
            (
                source.relative_to(sync_references.REPOSITORY_ROOT).as_posix(),
                copy.relative_to(sync_references.REPOSITORY_ROOT).as_posix(),
            )
            for source, copy in sync_references.REFERENCE_PAIRS.items()
        }
        self.assertEqual(expected, actual)

    def test_render_inserts_header_before_content_or_after_front_matter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "docs" / "reference" / "example.md"
            source.parent.mkdir(parents=True)
            with patch.object(sync_references, "REPOSITORY_ROOT", root):
                source.write_text("# Example\n", encoding="utf-8")
                self.assertEqual(
                    "<!-- Generated from docs/reference/example.md. Do not edit directly. "
                    "Run sync_references.py --write to update. -->\n# Example\n",
                    sync_references.render(source),
                )
                source.write_text(
                    "---\ntitle: Example\n---\n# Example\n", encoding="utf-8"
                )
                self.assertEqual(
                    "---\ntitle: Example\n---\n"
                    "<!-- Generated from docs/reference/example.md. Do not edit directly. "
                    "Run sync_references.py --write to update. -->\n# Example\n",
                    sync_references.render(source),
                )

    def test_check_passes_when_references_match_and_fails_on_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "docs" / "reference" / "example.md"
            copy = root / "plugins" / "garden" / "references" / "example.md"
            source.parent.mkdir(parents=True)
            copy.parent.mkdir(parents=True)
            source.write_text("# Example\n", encoding="utf-8")
            with (
                patch.object(sync_references, "REPOSITORY_ROOT", root),
                patch.object(sync_references, "REFERENCE_PAIRS", {source: copy}),
                patch("sys.stdout"),
            ):
                copy.write_text(sync_references.render(source), encoding="utf-8")
                self.assertEqual(0, sync_references.main(["--check"]))
                copy.write_text("corrupt\n", encoding="utf-8")
                with patch("sys.stderr") as stderr:
                    self.assertEqual(1, sync_references.main(["--check"]))
                stderr.write.assert_called_once_with(f"{copy}\n")

    def test_package_contract(self) -> None:
        validate()

    def test_cli_inspects_inactive_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [str(PLUGIN_ROOT / "bin" / "garden"), "inspect", directory],
                capture_output=True,
                text=True,
                check=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        self.assertFalse(json.loads(completed.stdout)["active"])

    def test_cli_install_remove_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in ("install-project", "remove-project"):
                completed = subprocess.run(
                    [
                        str(PLUGIN_ROOT / "bin" / "garden"),
                        command,
                        str(root),
                        "--harness",
                        "codex",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                self.assertEqual(command, json.loads(completed.stdout)["action"])
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / ".codex/agents/garden-reviewer.toml").exists())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from garden_project import (  # noqa: E402
    ManagedSurfaceError,
    install,
    remove,
)
from test_garden_core import ActiveProjectTestCase  # noqa: E402


class GardenProjectTests(ActiveProjectTestCase):
    def test_install_is_idempotent_and_remove_preserves_surrounding_content(
        self,
    ) -> None:
        agents = self.root / "AGENTS.md"
        original = "# Local rules\n\nKeep this text.\n"
        agents.write_text(original, encoding="utf-8")
        install(self.root, "both")
        first = agents.read_bytes()
        install(self.root, "both")
        self.assertEqual(first, agents.read_bytes())
        self.assertTrue((self.root / ".claude/rules/garden.md").is_file())
        self.assertTrue((self.root / ".codex/agents/garden-reviewer.toml").is_file())
        remove(self.root, "both")
        self.assertEqual(original, agents.read_text(encoding="utf-8"))
        self.assertFalse((self.root / ".claude/rules/garden.md").exists())
        self.assertFalse((self.root / ".codex/agents/garden-reviewer.toml").exists())

    def test_install_remove_preserves_missing_final_newline(self) -> None:
        agents = self.root / "AGENTS.md"
        original = "local rule without final newline"
        agents.write_text(original, encoding="utf-8")
        install(self.root, "codex")
        remove(self.root, "codex")
        self.assertEqual(original, agents.read_text(encoding="utf-8"))

    def test_unmanaged_file_is_never_replaced_or_removed(self) -> None:
        rules = self.root / ".claude/rules/garden.md"
        rules.parent.mkdir(parents=True)
        rules.write_text("user content\n", encoding="utf-8")
        with self.assertRaises(ManagedSurfaceError):
            install(self.root, "claude", force=True)
        with self.assertRaises(ManagedSurfaceError):
            remove(self.root, "claude", force=True)
        self.assertEqual("user content\n", rules.read_text(encoding="utf-8"))

    def test_duplicate_or_malformed_markers_are_refused(self) -> None:
        agents = self.root / "AGENTS.md"
        agents.write_text(
            "<!-- garden:managed-instructions:v1 sha256=x -->\n"
            "<!-- garden:managed-instructions:v1 sha256=y -->\n"
            "<!-- /garden:managed-instructions:v1 -->\n",
            encoding="utf-8",
        )
        with self.assertRaises(ManagedSurfaceError):
            install(self.root, "codex")
        with self.assertRaises(ManagedSurfaceError):
            remove(self.root, "codex")

    def test_edited_owned_content_requires_force(self) -> None:
        install(self.root, "codex")
        agents = self.root / "AGENTS.md"
        agents.write_text(
            agents.read_text(encoding="utf-8").replace(
                "# GARDEN project rules", "# Edited GARDEN rules"
            ),
            encoding="utf-8",
        )
        with self.assertRaises(ManagedSurfaceError):
            remove(self.root, "codex")
        remove(self.root, "codex", force=True)
        self.assertFalse(agents.exists())


if __name__ == "__main__":
    unittest.main()

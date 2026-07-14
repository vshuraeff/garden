from __future__ import annotations

import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATHS = tuple(
    REPOSITORY_ROOT / "plugins" / "garden" / "skills" / name / "SKILL.md"
    for name in ("bootstrap", "retrofit", "audit", "review", "start", "stop")
)


class GardenSkillsMigrationTests(unittest.TestCase):
    def test_skills_drop_significant_directory_term(self) -> None:
        for path in SKILL_PATHS:
            with self.subTest(path=path):
                self.assertNotIn(
                    "significant directory", path.read_text(encoding="utf-8")
                )

    def test_skills_drop_one_context_task_term(self) -> None:
        for path in SKILL_PATHS:
            with self.subTest(path=path):
                self.assertNotIn("one-context task", path.read_text(encoding="utf-8"))

    def test_skill_registry_mentions_are_config_aware(self) -> None:
        for path in SKILL_PATHS:
            content = path.read_text(encoding="utf-8")
            paragraphs = re.split(r"\n\s*\n", content)
            for paragraph in paragraphs:
                if "naming-registry.txt" in paragraph:
                    with self.subTest(path=path, paragraph=paragraph):
                        self.assertIn(".garden.toml", paragraph)

    def test_prompt_hook_message_mentions_config_activation(self) -> None:
        path = (
            REPOSITORY_ROOT / "plugins" / "garden" / "tools" / "garden_prompt_hook.py"
        )
        self.assertIn(".garden.toml", path.read_text(encoding="utf-8"))

    def test_tool_contract_activation_mentions_config(self) -> None:
        path = REPOSITORY_ROOT / "plugins" / "garden" / "tools" / "CONTRACT.md"
        content = path.read_text(encoding="utf-8")
        section = content.split("## Activation and confinement", 1)[1].split(
            "\n## ", 1
        )[0]
        self.assertIn(".garden.toml", section)


if __name__ == "__main__":
    unittest.main()

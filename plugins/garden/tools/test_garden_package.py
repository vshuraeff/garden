from __future__ import annotations

import json
import os
import shutil
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
            (
                "docs/evidence/evidence-registry.md",
                "plugins/garden/references/evidence-registry.md",
            ),
            (
                "docs/how-to/set-up-verification-gates.md",
                "plugins/garden/references/set-up-verification-gates.md",
            ),
            (
                "docs/reference/rule-registry.md",
                "plugins/garden/references/rule-registry.md",
            ),
            (
                "docs/reference/configuration.md",
                "plugins/garden/references/configuration.md",
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

    def test_render_rewrites_packaged_and_external_reference_links(self) -> None:
        expected_targets = {
            "docs/reference/principles.md": (
                "./rule-registry.md",
                "./evidence-registry.md#claim-n004",
            ),
            "docs/reference/checklist.md": (
                "./principles.md",
                "./review-procedure.md",
                "./set-up-verification-gates.md",
            ),
            "docs/reference/glossary.md": (
                "./principles.md",
                "./evidence-registry.md#claim-n002",
            ),
            "docs/how-to/review-code-as-agent.md": (
                "./set-up-verification-gates.md",
                "./principles.md",
                "./checklist.md",
                "./evidence-registry.md#claim-n003",
            ),
            "docs/how-to/set-up-verification-gates.md": (
                "./principles.md",
                "./evidence-registry.md#claim-n001",
                "./review-procedure.md",
                f"{sync_references.GITHUB_BLOB_BASE}"
                "docs/how-to/apply-to-new-project.md",
                f"{sync_references.GITHUB_BLOB_BASE}"
                "docs/how-to/retrofit-legacy-codebase.md",
                f"{sync_references.GITHUB_BLOB_BASE}"
                "docs/explanation/why-agent-first-principles.md",
            ),
            "docs/reference/rule-registry.md": (
                "./configuration.md#exceptions",
                "./principles.md",
                "./checklist.md",
                f"{sync_references.GITHUB_BLOB_BASE}"
                "docs/reference/report-schema.md#coverage",
            ),
            "docs/reference/configuration.md": (
                f"{sync_references.GITHUB_BLOB_BASE}docs/reference/report-schema.md",
                f"{sync_references.GITHUB_BLOB_BASE}docs/reference/platform-support.md",
            ),
        }
        for source_relative, targets in expected_targets.items():
            with self.subTest(source=source_relative):
                rendered = sync_references.render(
                    sync_references.REPOSITORY_ROOT / source_relative
                )
                for target in targets:
                    self.assertIn(f"]({target})", rendered)

    def test_render_rejects_unresolvable_relative_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "docs" / "reference" / "example.md"
            source.parent.mkdir(parents=True)
            source.write_text("[missing](missing.md)\n", encoding="utf-8")
            with patch.object(sync_references, "REPOSITORY_ROOT", root):
                with self.assertRaisesRegex(
                    ValueError,
                    "docs/reference/example.md: unresolved relative link "
                    "'missing.md' has no packaged target and is not in "
                    "EXTERNAL_FALLBACK",
                ):
                    sync_references.render(source)

    def test_rewrite_links_preserves_surrounding_markdown(self) -> None:
        source = (
            sync_references.REPOSITORY_ROOT
            / "docs"
            / "how-to"
            / "review-code-as-agent.md"
        )
        content = (
            '[plain](../reference/glossary.md?view=full#default "plain title")\n'
            "[angle](<../reference/checklist.md#coverage> 'angle title')\n"
        )

        self.assertEqual(
            '[plain](./glossary.md?view=full#default "plain title")\n'
            "[angle](<./checklist.md#coverage> 'angle title')\n",
            sync_references.rewrite_links(content, source),
        )

    def test_packaged_references_do_not_link_to_parent_directories(self) -> None:
        for path in sorted((PLUGIN_ROOT / "references").glob("*.md")):
            with self.subTest(path=path.name):
                self.assertNotIn("](../", path.read_text(encoding="utf-8"))

    def test_render_is_byte_stable(self) -> None:
        for source in sync_references.REFERENCE_PAIRS:
            with self.subTest(source=source.name):
                self.assertEqual(
                    sync_references.render(source).encode("utf-8"),
                    sync_references.render(source).encode("utf-8"),
                )

    def test_package_contract(self) -> None:
        validate()

    def test_packaged_link_cannot_escape_plugin_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin_root = root / "plugins" / "garden"
            shutil.copytree(PLUGIN_ROOT, plugin_root)
            marketplace = root / ".agents" / "plugins" / "marketplace.json"
            marketplace.parent.mkdir(parents=True)
            marketplace.write_text(
                json.dumps(
                    {
                        "name": "garden",
                        "plugins": [
                            {
                                "name": "garden",
                                "source": {"path": "./plugins/garden"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "outside.md").write_text("# Outside\n", encoding="utf-8")
            (plugin_root / "references" / "bad.md").write_text(
                "[outside](../../../outside.md)\n", encoding="utf-8"
            )

            with (
                patch("validate_package.PLUGIN_ROOT", plugin_root),
                patch("validate_package.REPOSITORY_ROOT", root),
                patch("validate_package.REFERENCE_PAIRS", {}),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    r"plugins/garden/references/bad.md.*\.\./\.\./outside\.md",
                ):
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

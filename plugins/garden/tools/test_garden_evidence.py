from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from validate_evidence import validate as validate_evidence  # noqa: E402


class EvidenceValidationTests(unittest.TestCase):
    def write_registry(self, root: Path) -> Path:
        registry = root / "docs" / "evidence" / "evidence-registry.md"
        registry.parent.mkdir(parents=True)
        registry.write_text(
            "# Evidence registry\n\n"
            "## CLAIM-N001 — example\n\n"
            "Verdict: practitioner-report\n\n"
            "### Statement\n\n"
            "Example statement.\n\n"
            "### Source\n\n"
            "Example source.\n\n"
            "### Population\n\n"
            "Example population.\n\n"
            "### Measured result\n\n"
            "Example result.\n\n"
            "### Limitations\n\n"
            "Example limitation.\n\n"
            "### Used by\n\n"
            "- `docs/reference/example.md`\n",
            encoding="utf-8",
        )
        return registry

    def write_usage(self, root: Path, content: str) -> Path:
        usage = root / "docs" / "reference" / "example.md"
        usage.parent.mkdir(parents=True, exist_ok=True)
        usage.write_text(content, encoding="utf-8")
        return usage

    def test_valid_registry_and_usage_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_registry(root)
            self.write_usage(
                root,
                "The measured result was 25%. [CLAIM-N001]\n",
            )
            findings, warnings = validate_evidence(root)
        self.assertEqual([], findings)
        self.assertEqual([], warnings)

    def test_missing_required_registry_section_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = self.write_registry(root)
            registry.write_text(
                registry.read_text(encoding="utf-8").replace("### Source\n\n", ""),
                encoding="utf-8",
            )
            self.write_usage(root, "[CLAIM-N001]\n")
            findings, _ = validate_evidence(root)
        self.assertTrue(
            any("misses required section Source" in item.reason for item in findings)
        )

    def test_unknown_claim_reference_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_registry(root)
            self.write_usage(root, "[CLAIM-N999]\n")
            findings, _ = validate_evidence(root)
        self.assertTrue(
            any("unknown evidence claim CLAIM-N999" in item.reason for item in findings)
        )

    def test_bare_percentage_in_normative_doc_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_registry(root)
            self.write_usage(root, "The measured result was 25%.\n")
            findings, _ = validate_evidence(root)
        self.assertTrue(any("bare percentage" in item.reason for item in findings))

    def test_broken_relative_markdown_link_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_registry(root)
            self.write_usage(root, "[missing](missing.md) [CLAIM-N001]\n")
            findings, _ = validate_evidence(root)
        self.assertTrue(
            any("broken relative Markdown link" in item.reason for item in findings)
        )


if __name__ == "__main__":
    unittest.main()

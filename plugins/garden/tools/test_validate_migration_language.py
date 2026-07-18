from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from validate_migration_language import (  # noqa: E402
    LEGACY_MARKER,
    PROHIBITED_PHRASES,
    migration_language_findings,
    validate,
)


class MigrationLanguageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, relative: str | Path, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_current_terminology_has_no_findings(self) -> None:
        self.write(
            "docs/tutorials/current.md",
            "# Current language\n\nDeterministic Verification and unrelated prose.\n",
        )

        findings = validate(self.root)

        self.assertEqual([], findings)

    def test_each_prohibited_phrase_reports_its_file_and_line(self) -> None:
        for index, phrase in enumerate(PROHIBITED_PHRASES):
            with self.subTest(phrase=phrase):
                path = self.write(
                    f"docs/tutorials/retired-{index}.md",
                    f"current prose\n{phrase}\n",
                )

                findings = migration_language_findings(path, self.root)

                self.assertEqual(
                    [(path, 2)], [(item.path, item.line) for item in findings]
                )
                self.assertEqual(
                    f"prohibited retired terminology: '{phrase}'",
                    findings[0].reason,
                )

    def test_matching_is_case_insensitive_and_phrase_bounded(self) -> None:
        path = self.write(
            "docs/explanation/matching.md",
            "grep-FIRST discoverability\nGrep-first Discoverabilityish\n",
        )

        findings = migration_language_findings(path, self.root)

        self.assertEqual([1], [finding.line for finding in findings])

    def test_migration_document_is_fully_exempt(self) -> None:
        self.write(
            "docs/how-to/migrate-from-garden-v0.md",
            "\n".join(PROHIBITED_PHRASES) + "\n",
        )

        findings = validate(self.root)

        self.assertEqual([], findings)

    def test_inline_marker_exempts_only_the_marked_violation_lines(self) -> None:
        cases = (
            (
                "same-line",
                f"{PROHIBITED_PHRASES[0]} {LEGACY_MARKER}\n{PROHIBITED_PHRASES[1]}\n",
                2,
            ),
            (
                "preceding-line",
                f"{LEGACY_MARKER}\n"
                f"{PROHIBITED_PHRASES[0]}\n"
                "current prose\n"
                f"{PROHIBITED_PHRASES[1]}\n",
                4,
            ),
        )
        for name, content, expected_line in cases:
            with self.subTest(marker_position=name):
                path = self.write(f"docs/reference/{name}.md", content)

                findings = migration_language_findings(path, self.root)

                self.assertEqual(
                    [(path, expected_line)],
                    [(item.path, item.line) for item in findings],
                )

    def test_validate_reports_violations_and_accepts_clean_tree(self) -> None:
        self.write(
            "bad/docs/explanation/legacy.md",
            f"{PROHIBITED_PHRASES[0]}\n",
        )
        self.write(
            "good/docs/explanation/current.md",
            "Defense-in-depth Verification\n",
        )

        bad_findings = validate(self.root / "bad")
        good_findings = validate(self.root / "good")

        self.assertNotEqual([], bad_findings)
        self.assertEqual([], good_findings)


if __name__ == "__main__":
    unittest.main()

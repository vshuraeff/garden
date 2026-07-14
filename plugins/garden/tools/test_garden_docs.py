from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from validate_docs import (  # noqa: E402
    NORMATIVE_DOCUMENTS,
    freshness_findings,
    link_findings,
    rule_id_findings,
    validate,
)


class GardenDocumentationTests(unittest.TestCase):
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

    def front_matter(self, extra: str = "") -> str:
        return (
            "---\n"
            "owner: vshuraeff\n"
            "last_reviewed: 2026-07-14\n"
            "review_on:\n"
            "  - rule-change\n"
            f"{extra}"
            "---\n"
        )

    def test_broken_relative_link_is_detected(self) -> None:
        path = self.write("docs/guide.md", "# Guide\n\n[missing](missing.md)\n")

        findings = link_findings(path, self.root)

        self.assertEqual(1, len(findings))
        self.assertIn("broken link 'missing.md'", findings[0].reason)

    def test_link_inside_code_fence_is_not_checked(self) -> None:
        path = self.write(
            "docs/guide.md",
            "# Guide\n\n```markdown\n[inside](inside.md)\n```\n\n"
            "[outside](outside.md)\n",
        )

        findings = link_findings(path, self.root)

        self.assertEqual(1, len(findings))
        self.assertIn("broken link 'outside.md'", findings[0].reason)

    def test_external_https_link_is_not_checked_for_existence(self) -> None:
        path = self.write(
            "docs/guide.md",
            "# Guide\n\n[external](https://example.invalid/nonexistent)\n",
        )

        findings = link_findings(path, self.root)

        self.assertEqual([], findings)

    def test_non_deterministic_headings_disable_anchor_checking(self) -> None:
        self.write("docs/target.md", "# Target\n\n## Foo Bar\n\n## foo-bar\n")
        path = self.write(
            "docs/guide.md", "# Guide\n\n[target](target.md#missing-anchor)\n"
        )

        findings = link_findings(path, self.root)

        self.assertEqual([], findings)

    def test_duplicate_and_cross_referenced_rule_ids_are_detected(self) -> None:
        self.write(
            "docs/reference/principles.md",
            "# Principles\n\n"
            "- **G-DISC-001 [REQUIRED] One.** Definition.\n"
            "- **G-DISC-001 [DEFAULT] Duplicate.** Definition.\n",
        )
        self.write("docs/reference/checklist.md", "# Checklist\n\nA-LOC-001\n")

        reasons = [finding.reason for finding in rule_id_findings(self.root)]

        self.assertIn("duplicate defined rule ID G-DISC-001", reasons)
        self.assertIn("checklist references undefined rule ID A-LOC-001", reasons)
        self.assertIn(
            "defined rule ID G-DISC-001 is not referenced in checklist", reasons
        )

    def test_missing_front_matter_is_detected(self) -> None:
        path = Path("docs/reference/checklist.md")
        self.write(path, "# Checklist\n")

        findings = freshness_findings(self.root, (path,), date(2026, 7, 14))

        self.assertEqual(
            ["invalid front matter: missing leading front matter"],
            [finding.reason for finding in findings],
        )

    def test_invalid_front_matter_is_detected(self) -> None:
        path = Path("docs/reference/checklist.md")
        self.write(
            path,
            "---\n"
            "owner: vshuraeff\n"
            "last_reviewed: 2026-13-40\n"
            "review_on:\n"
            "  - unsupported-trigger\n"
            "extra: value\n"
            "---\n"
            "# Checklist\n",
        )
        future_path = Path("docs/reference/configuration.md")
        self.write(
            future_path,
            self.front_matter().replace("2026-07-14", "2026-07-15") + "# Config\n",
        )

        findings = freshness_findings(self.root, (path, future_path), date(2026, 7, 14))
        reasons = [finding.reason for finding in findings]

        self.assertIn("unknown front matter key extra", reasons)
        self.assertIn("last_reviewed must be a valid YYYY-MM-DD date", reasons)
        self.assertIn("invalid review_on entry unsupported-trigger", reasons)
        self.assertIn("last_reviewed must not be in the future", reasons)

    def test_fully_valid_fixture_has_no_findings(self) -> None:
        for relative in NORMATIVE_DOCUMENTS:
            self.write(relative, self.front_matter() + "# Document\n")
        self.write(
            "docs/reference/principles.md",
            self.front_matter()
            + "# Principles\n\n- **G-DISC-001 [REQUIRED] Example.** Definition.\n",
        )
        self.write(
            "docs/reference/checklist.md",
            self.front_matter()
            + "# Checklist\n\n[Principles](principles.md#principles)\n\nG-DISC-001\n",
        )

        findings = validate(self.root, date(2026, 7, 14))

        self.assertEqual([], findings)


if __name__ == "__main__":
    unittest.main()

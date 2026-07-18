#!/usr/bin/env -S uv run --no-project
"""Validate active GARDEN surfaces for retired migration terminology.

The migration guide at ``docs/how-to/migrate-from-garden-v0.md`` is fully
exempt because it documents the retired terminology for migrators. Elsewhere,
``<!-- legacy-term-ok -->`` exempts only one violation line: its own line when
that line contains retired terminology, or the immediately following line. It
never exempts an entire file.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PLUGIN_ROOT.parent.parent
PROHIBITED_PHRASES = (
    "Grep-first Discoverability",
    "Atomic Vertical Slices",
    "Regenerable Components",
    "Explicit Everything",
    "Navigable Knowledge",
    "one-context task",
    "significant directory",
    "one canonical name across the codebase",
    "every slice has CONTRACT.md",
    "one hop from the edit site",
    "code is expendable",
)
# deterministic verification is current terminology and intentionally allowed.
PROHIBITED_PATTERNS = tuple(
    (
        phrase,
        re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE),
    )
    for phrase in PROHIBITED_PHRASES
)
EXEMPT_FILES = (Path("docs/how-to/migrate-from-garden-v0.md"),)
LEGACY_MARKER = "<!-- legacy-term-ok -->"
MARKDOWN_DIRECTORIES = (
    Path("docs/tutorials"),
    Path("docs/how-to"),
    Path("docs/explanation"),
    Path("docs/reference"),
    Path("plugins/garden/skills"),
    Path("plugins/garden/agents"),
    Path("plugins/garden/assets"),
    Path("plugins/garden/references"),
)
MARKDOWN_FILES = (
    Path("README.md"),
    Path("plugins/garden/README.md"),
)
TEXT_FILES = (
    Path("plugins/garden/.claude-plugin/plugin.json"),
    Path("plugins/garden/.codex-plugin/plugin.json"),
    Path(".agents/plugins/marketplace.json"),
)


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    reason: str

    def format(self, repository_root: Path) -> str:
        try:
            path = self.path.relative_to(repository_root).as_posix()
        except ValueError:
            path = str(self.path)
        return f"{path}:{self.line}: {self.reason}"


def scanned_files(repository_root: Path) -> list[Path]:
    roots = tuple(repository_root / relative for relative in MARKDOWN_DIRECTORIES)
    paths = {
        path
        for root in roots
        if root.exists()
        for path in root.rglob("*.md")
        if path.is_file()
    }
    for relative in (*MARKDOWN_FILES, *TEXT_FILES):
        path = repository_root / relative
        if path.is_file():
            paths.add(path)
    return sorted(paths)


def is_exempt_file(path: Path, repository_root: Path) -> bool:
    try:
        relative = path.relative_to(repository_root)
    except ValueError:
        return False
    return relative in EXEMPT_FILES


def has_prohibited_phrase(line: str) -> bool:
    return any(pattern.search(line) for _, pattern in PROHIBITED_PATTERNS)


def is_exempt_line(lines: list[str], index: int) -> bool:
    if LEGACY_MARKER in lines[index]:
        return True
    if index == 0 or LEGACY_MARKER not in lines[index - 1]:
        return False
    return not has_prohibited_phrase(lines[index - 1])


def migration_language_findings(path: Path, repository_root: Path) -> list[Finding]:
    if is_exempt_file(path, repository_root):
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        return [Finding(path, 1, f"cannot read scanned file: {error}")]

    findings: list[Finding] = []
    for index, line in enumerate(lines):
        if is_exempt_line(lines, index):
            continue
        for phrase, pattern in PROHIBITED_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        path,
                        index + 1,
                        f"prohibited retired terminology: '{phrase}'",
                    )
                )
    return findings


def validate(repository_root: Path = REPOSITORY_ROOT) -> list[Finding]:
    repository_root = repository_root.resolve()
    findings = [
        finding
        for path in scanned_files(repository_root)
        for finding in migration_language_findings(path, repository_root)
    ]
    return sorted(findings, key=lambda item: (str(item.path), item.line, item.reason))


def main() -> int:
    findings = validate()
    for finding in findings:
        print(finding.format(REPOSITORY_ROOT), file=sys.stderr)
    if findings:
        return 1
    print("migration language validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

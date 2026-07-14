#!/usr/bin/env -S uv run --no-project
"""Validate deterministic documentation contracts for the GARDEN repository."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PLUGIN_ROOT.parent.parent
NORMATIVE_DOCUMENTS = (
    Path("docs/reference/checklist.md"),
    Path("docs/reference/configuration.md"),
    Path("docs/reference/glossary.md"),
    Path("docs/reference/principles.md"),
    Path("docs/explanation/relation-to-classic-principles.md"),
    Path("docs/explanation/the-garden-model.md"),
    Path("docs/explanation/why-agent-first-principles.md"),
    Path("docs/how-to/apply-to-new-project.md"),
    Path("docs/how-to/install-codex-and-claude-plugin.md"),
    Path("docs/how-to/migrate-from-garden-v0.md"),
    Path("docs/how-to/retrofit-legacy-codebase.md"),
    Path("docs/how-to/review-code-as-agent.md"),
    Path("docs/how-to/set-up-verification-gates.md"),
)
REVIEW_ON_VALUES = frozenset(
    {
        "rule-change",
        "config-schema-change",
        "major-release",
        "evidence-change",
    }
)
FRONT_MATTER_KEYS = frozenset({"owner", "last_reviewed", "review_on"})
RULE_ID = r"[A-Z]+(?:-[A-Z]+)+-\d{3}"
RULE_ID_TOKEN = re.compile(rf"\b({RULE_ID})\b")
RULE_DEFINITION = re.compile(
    rf"^(?:#{{1,6}}\s+(?:\*\*)?|[-*]\s+\*\*)({RULE_ID})(?:\*\*)?(?:\s+\[|\b)",
    re.MULTILINE,
)
MARKDOWN_LINK = re.compile(
    r"(?<!!)\[[^\]]+\]\(\s*(?:<(?P<angle>[^>]+)>|(?P<plain>[^\s)]+))"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
)
HEADING = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*$", re.MULTILINE)
GENERATED_SOURCE = re.compile(
    r"<!-- Generated from (?P<source>[^\s]+)\. Do not edit directly\."
)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
FRONT_MATTER_FIELD = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]+(.*))?$")
FRONT_MATTER_ITEM = re.compile(r"^[ \t]+-[ \t]+(.+?)\s*$")


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


@dataclass(frozen=True)
class FrontMatter:
    values: dict[str, str | list[str]]
    lines: dict[str, int]


def line_number(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def markdown_files(repository_root: Path) -> list[Path]:
    roots = (
        repository_root / "docs",
        repository_root / "plugins" / "garden" / "references",
        repository_root / "plugins" / "garden" / "skills",
        repository_root / "plugins" / "garden" / "assets",
        repository_root / "plugins" / "garden" / "agents",
    )
    paths = {
        path
        for root in roots
        if root.exists()
        for path in root.rglob("*.md")
        if path.is_file()
    }
    for path in (
        repository_root / "README.md",
        repository_root / "plugins" / "garden" / "README.md",
    ):
        if path.is_file():
            paths.add(path)
    return sorted(paths)


def generated_source(path: Path, content: str, repository_root: Path) -> Path | None:
    try:
        path.relative_to(repository_root / "plugins" / "garden" / "references")
    except ValueError:
        return None
    match = GENERATED_SOURCE.search(content)
    if match is None:
        return None
    source = (repository_root / match.group("source")).resolve()
    try:
        source.relative_to(repository_root)
    except ValueError:
        return None
    return source if source.is_file() else None


def without_inline_code(line: str) -> str:
    return re.sub(r"(`+).*?\1", lambda match: " " * len(match.group(0)), line)


def markdown_links(content: str) -> list[tuple[int, str]]:
    links: list[tuple[int, str]] = []
    fence: str | None = None
    for line_number_value, raw_line in enumerate(content.splitlines(), start=1):
        marker = FENCE.match(raw_line)
        if marker is not None:
            token = marker.group(1)
            if fence is None:
                fence = token[0]
            elif token[0] == fence:
                fence = None
            continue
        if fence is not None:
            continue
        for match in MARKDOWN_LINK.finditer(without_inline_code(raw_line)):
            links.append(
                (line_number_value, match.group("angle") or match.group("plain"))
            )
    return links


def heading_slugs(content: str) -> tuple[set[str], bool]:
    slugs: set[str] = set()
    deterministic = True
    for match in HEADING.finditer(content):
        heading = match.group(1).rstrip(" #")
        if not heading or re.search(r"[`*_~\\[\\]<>]", heading):
            deterministic = False
            continue
        slug = re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-")
        if not slug:
            deterministic = False
            continue
        if slug in slugs:
            deterministic = False
        slugs.add(slug)
    return slugs, deterministic


def link_findings(path: Path, repository_root: Path) -> list[Finding]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        return [Finding(path, 1, f"cannot read Markdown file: {error}")]

    base = generated_source(path, content, repository_root) or path
    findings: list[Finding] = []
    anchors: dict[Path, tuple[set[str], bool]] = {}
    for line, raw_target in markdown_links(content):
        target = raw_target.strip()
        if target.lower().startswith(
            ("http://", "https://", "mailto:")
        ) or target.startswith(("#", "/")):
            continue
        target_path, separator, anchor = target.partition("#")
        target_path = target_path.split("?", maxsplit=1)[0]
        if not target_path:
            continue
        resolved = (base.parent / target_path).resolve()
        try:
            resolved.relative_to(repository_root)
        except ValueError:
            findings.append(
                Finding(
                    path, line, f"broken link '{target}' (target escapes repository)"
                )
            )
            continue
        if not resolved.is_file():
            findings.append(
                Finding(
                    path, line, f"broken link '{target}' (target file does not exist)"
                )
            )
            continue
        if not separator or resolved.suffix.lower() != ".md":
            continue
        if resolved not in anchors:
            try:
                anchors[resolved] = heading_slugs(resolved.read_text(encoding="utf-8"))
            except OSError:
                continue
        slugs, deterministic = anchors[resolved]
        if anchor in slugs:
            continue
        if deterministic and re.fullmatch(r"[a-z0-9-]+", anchor):
            findings.append(
                Finding(path, line, f"broken link '{target}' (anchor does not exist)")
            )
    return findings


def rule_definitions(path: Path) -> tuple[list[tuple[str, int]], list[Finding]]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        return [], [Finding(path, 1, f"cannot read rule definitions: {error}")]
    return [
        (match.group(1), line_number(content, match.start(1)))
        for match in RULE_DEFINITION.finditer(content)
    ], []


def rule_id_findings(repository_root: Path) -> list[Finding]:
    principles = repository_root / "docs/reference/principles.md"
    checklist = repository_root / "docs/reference/checklist.md"
    definitions, findings = rule_definitions(principles)
    defined: dict[str, int] = {}
    for identifier, line in definitions:
        if identifier in defined:
            findings.append(
                Finding(principles, line, f"duplicate defined rule ID {identifier}")
            )
            continue
        defined[identifier] = line
    if not definitions:
        findings.append(Finding(principles, 1, "no defined rule IDs found"))

    try:
        checklist_content = checklist.read_text(encoding="utf-8")
    except OSError as error:
        return findings + [Finding(checklist, 1, f"cannot read checklist: {error}")]
    checklist_ids = {
        match.group(1): line_number(checklist_content, match.start(1))
        for match in RULE_ID_TOKEN.finditer(checklist_content)
    }
    for identifier, line in sorted(checklist_ids.items()):
        if identifier not in defined:
            findings.append(
                Finding(
                    checklist,
                    line,
                    f"checklist references undefined rule ID {identifier}",
                )
            )
    for identifier, line in sorted(defined.items()):
        if identifier not in checklist_ids:
            findings.append(
                Finding(
                    principles,
                    line,
                    f"defined rule ID {identifier} is not referenced in checklist",
                )
            )
    return findings


def parse_front_matter(content: str) -> FrontMatter:
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing leading front matter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise ValueError("front matter is not closed") from error

    values: dict[str, str | list[str]] = {}
    field_lines: dict[str, int] = {}
    index = 1
    while index < end:
        raw_line = lines[index]
        if not raw_line.strip():
            index += 1
            continue
        match = FRONT_MATTER_FIELD.fullmatch(raw_line)
        if match is None:
            raise ValueError(f"cannot parse front matter line {index + 1}")
        key, value = match.groups()
        if key in values:
            raise ValueError(f"duplicate front matter key {key}")
        field_lines[key] = index + 1
        index += 1
        if value is not None:
            values[key] = value.strip()
            continue
        items: list[str] = []
        while index < end:
            item = FRONT_MATTER_ITEM.fullmatch(lines[index])
            if item is None:
                break
            items.append(item.group(1).strip())
            index += 1
        values[key] = items
    return FrontMatter(values, field_lines)


def freshness_findings(
    repository_root: Path,
    normative_documents: tuple[Path, ...] = NORMATIVE_DOCUMENTS,
    current_date: date | None = None,
) -> list[Finding]:
    today = current_date or date.today()
    findings: list[Finding] = []
    for relative in normative_documents:
        path = repository_root / relative
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            findings.append(
                Finding(path, 1, f"cannot read normative document: {error}")
            )
            continue
        try:
            front_matter = parse_front_matter(content)
        except ValueError as error:
            findings.append(Finding(path, 1, f"invalid front matter: {error}"))
            continue
        for key in sorted(set(front_matter.values) - FRONT_MATTER_KEYS):
            findings.append(
                Finding(
                    path, front_matter.lines[key], f"unknown front matter key {key}"
                )
            )

        owner = front_matter.values.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            findings.append(Finding(path, 1, "owner must be a non-empty string"))

        reviewed = front_matter.values.get("last_reviewed")
        try:
            if (
                not isinstance(reviewed, str)
                or re.fullmatch(r"\d{4}-\d{2}-\d{2}", reviewed) is None
            ):
                raise ValueError
            reviewed_date = date.fromisoformat(reviewed)
        except ValueError:
            findings.append(
                Finding(path, 1, "last_reviewed must be a valid YYYY-MM-DD date")
            )
        else:
            if reviewed_date > today:
                findings.append(
                    Finding(path, 1, "last_reviewed must not be in the future")
                )

        review_on = front_matter.values.get("review_on")
        if not isinstance(review_on, list) or not review_on:
            findings.append(Finding(path, 1, "review_on must be a non-empty list"))
            continue
        for entry in review_on:
            if entry not in REVIEW_ON_VALUES:
                findings.append(
                    Finding(
                        path,
                        front_matter.lines["review_on"],
                        f"invalid review_on entry {entry}",
                    )
                )
    return findings


def validate(
    repository_root: Path = REPOSITORY_ROOT,
    current_date: date | None = None,
) -> list[Finding]:
    repository_root = repository_root.resolve()
    findings: list[Finding] = []
    for path in markdown_files(repository_root):
        findings.extend(link_findings(path, repository_root))
    findings.extend(rule_id_findings(repository_root))
    findings.extend(freshness_findings(repository_root, current_date=current_date))
    return sorted(findings, key=lambda item: (str(item.path), item.line, item.reason))


def main() -> int:
    findings = validate()
    for finding in findings:
        print(finding.format(REPOSITORY_ROOT), file=sys.stderr)
    if findings:
        return 1
    print("documentation validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

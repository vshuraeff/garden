#!/usr/bin/env -S uv run --no-project
"""Validate evidence claims and citations; orphan claims are warnings, not failures."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PLUGIN_ROOT.parent.parent
REGISTRY_PATH = Path("docs/evidence/evidence-registry.md")
REQUIRED_SECTIONS = (
    "Statement",
    "Source",
    "Population",
    "Measured result",
    "Limitations",
    "Used by",
)
VERDICTS = {"confirmed", "trend-only", "practitioner-report"}
CLAIM_HEADING = re.compile(r"^## (CLAIM-N\d+)\b", re.MULTILINE)
CLAIM_TOKEN = re.compile(r"\bCLAIM-N\d+\b")
PERCENTAGE = re.compile(r"\b\d+(?:[-–]\d+)?%")
LINK = re.compile(r"\[[^\]]+\]\(([^\s)]+)(?:\s+[^)]*)?\)")


@dataclass(frozen=True)
class Claim:
    identifier: str
    line: int
    used_by: tuple[Path, ...]


@dataclass(frozen=True)
class Reference:
    identifier: str
    path: Path
    line: int


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


def line_number(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def markdown_files(repository_root: Path) -> list[Path]:
    roots = (
        repository_root / "docs",
        repository_root / "plugins" / "garden",
    )
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*.md") if path.is_file())
    return sorted(set(files))


def normal_surface(path: Path, repository_root: Path) -> bool:
    relative = path.relative_to(repository_root)
    if relative.parts[:2] in {
        ("docs", "reference"),
        ("docs", "explanation"),
        ("docs", "how-to"),
    }:
        return True
    return (
        relative.parts[:3] == ("plugins", "garden", "skills")
        and path.name == "SKILL.md"
    )


def canonical_surface(path: Path, repository_root: Path) -> bool:
    relative = path.relative_to(repository_root)
    return relative.parts[:1] == ("docs",) or (
        relative.parts[:3] == ("plugins", "garden", "skills")
        and path.name == "SKILL.md"
    )


def used_by_paths(content: str, start: int, end: int) -> tuple[Path, ...]:
    heading = re.search(r"^### Used by\s*$", content[start:end], re.MULTILINE)
    if heading is None:
        return ()
    section_start = start + heading.end()
    next_heading = re.search(r"^### ", content[section_start:end], re.MULTILINE)
    section_end = section_start + next_heading.start() if next_heading else end
    paths = re.findall(r"`([^`]+\.md)`", content[section_start:section_end])
    return tuple(Path(path) for path in paths)


def parse_registry(registry: Path) -> tuple[dict[str, Claim], list[Finding]]:
    try:
        content = registry.read_text(encoding="utf-8")
    except OSError as error:
        return {}, [Finding(registry, 1, f"cannot read evidence registry: {error}")]

    headings = list(CLAIM_HEADING.finditer(content))
    findings: list[Finding] = []
    claims: dict[str, Claim] = {}
    if not headings:
        return {}, [Finding(registry, 1, "evidence registry has no CLAIM-N entries")]

    for index, heading in enumerate(headings):
        identifier = heading.group(1)
        end = headings[index + 1].start() if index + 1 < len(headings) else len(content)
        block = content[heading.start() : end]
        line = line_number(content, heading.start())
        if identifier in claims:
            findings.append(
                Finding(registry, line, f"duplicate registry entry {identifier}")
            )
            continue
        for section in REQUIRED_SECTIONS:
            if (
                re.search(rf"^### {re.escape(section)}\s*$", block, re.MULTILINE)
                is None
            ):
                findings.append(
                    Finding(
                        registry,
                        line,
                        f"{identifier} misses required section {section}",
                    )
                )
        verdict = re.search(r"^Verdict:\s*(\S+)\s*$", block, re.MULTILINE)
        if verdict is None:
            findings.append(
                Finding(registry, line, f"{identifier} misses Verdict line")
            )
        elif verdict.group(1) not in VERDICTS:
            findings.append(
                Finding(
                    registry,
                    line,
                    f"{identifier} has invalid verdict {verdict.group(1)}",
                )
            )
        claims[identifier] = Claim(
            identifier, line, used_by_paths(content, heading.start(), end)
        )
    return claims, findings


def claim_references(
    paths: list[Path], registry: Path
) -> tuple[list[Reference], list[Finding]]:
    references: list[Reference] = []
    findings: list[Finding] = []
    for path in paths:
        if path == registry:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            findings.append(Finding(path, 1, f"cannot read Markdown file: {error}"))
            continue
        for match in CLAIM_TOKEN.finditer(content):
            references.append(
                Reference(match.group(0), path, line_number(content, match.start()))
            )
    return references, findings


def paragraphs(content: str) -> list[tuple[int, int, list[tuple[int, str]]]]:
    blocks: list[tuple[int, int, list[tuple[int, str]]]] = []
    current: list[tuple[int, str]] = []
    fenced = False

    def flush() -> None:
        if current:
            blocks.append((current[0][0], current[-1][0], current.copy()))
            current.clear()

    for line, text in enumerate(content.splitlines(), start=1):
        if text.strip().startswith("```"):
            flush()
            fenced = not fenced
            continue
        if fenced:
            continue
        if text.strip():
            current.append((line, text))
        else:
            flush()
    flush()
    return blocks


def percentage_findings(path: Path, repository_root: Path) -> list[Finding]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        return [Finding(path, 1, f"cannot read Markdown file: {error}")]

    findings: list[Finding] = []
    previous_claim_values: set[str] = set()
    previous_end = 0
    for start, end, block in paragraphs(content):
        text = "\n".join(value for _, value in block)
        values = set(PERCENTAGE.findall(text))
        has_claim = CLAIM_TOKEN.search(text) is not None
        repeated_after_claim = (
            start - previous_end <= 2
            and bool(values)
            and values.issubset(previous_claim_values)
        )
        if values and not has_claim and not repeated_after_claim:
            for line, value in block:
                if PERCENTAGE.search(value):
                    findings.append(
                        Finding(
                            path,
                            line,
                            "bare percentage without a CLAIM-N reference in the paragraph",
                        )
                    )
        previous_claim_values = values if has_claim else set()
        previous_end = end
    return findings


def link_findings(path: Path, repository_root: Path) -> list[Finding]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        return [Finding(path, 1, f"cannot read Markdown file: {error}")]

    findings: list[Finding] = []
    for match in LINK.finditer(content):
        target = match.group(1).strip("<>")
        if target.startswith("#") or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", target):
            continue
        target = target.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0]
        if not target or target.startswith("/"):
            continue
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(repository_root)
        except ValueError:
            findings.append(
                Finding(
                    path,
                    line_number(content, match.start()),
                    f"relative Markdown link escapes the repository: {target}",
                )
            )
            continue
        if not resolved.is_file():
            findings.append(
                Finding(
                    path,
                    line_number(content, match.start()),
                    f"broken relative Markdown link: {target}",
                )
            )
    return findings


def validate(
    repository_root: Path = REPOSITORY_ROOT,
) -> tuple[list[Finding], list[str]]:
    repository_root = repository_root.resolve()
    registry = repository_root / REGISTRY_PATH
    claims, findings = parse_registry(registry)
    paths = markdown_files(repository_root)
    references, reference_findings = claim_references(paths, registry)
    findings.extend(reference_findings)

    referenced_identifiers = {reference.identifier for reference in references}
    for reference in references:
        if reference.identifier not in claims:
            findings.append(
                Finding(
                    reference.path,
                    reference.line,
                    f"unknown evidence claim {reference.identifier}",
                )
            )

    for identifier, claim in claims.items():
        listed = {repository_root / path for path in claim.used_by}
        for path in listed:
            if not path.is_file():
                findings.append(
                    Finding(
                        registry,
                        claim.line,
                        f"{identifier} Used by path does not exist: {path.relative_to(repository_root)}",
                    )
                )
        actual = {
            reference.path
            for reference in references
            if reference.identifier == identifier
            and canonical_surface(reference.path, repository_root)
        }
        for path in actual - listed:
            findings.append(
                Finding(
                    path,
                    1,
                    f"{identifier} is not listed in the registry Used by section",
                )
            )
        for path in listed - actual:
            findings.append(
                Finding(
                    registry,
                    claim.line,
                    f"{identifier} Used by path does not cite the claim: {path.relative_to(repository_root)}",
                )
            )

    for path in paths:
        if normal_surface(path, repository_root):
            findings.extend(percentage_findings(path, repository_root))
        if canonical_surface(path, repository_root):
            findings.extend(link_findings(path, repository_root))

    warnings = [
        f"warning: orphan evidence claim {identifier}"
        for identifier in claims
        if identifier not in referenced_identifiers
    ]
    return findings, warnings


def main() -> None:
    findings, warnings = validate()
    for warning in warnings:
        print(warning, file=sys.stderr)
    for finding in findings:
        print(finding.format(REPOSITORY_ROOT), file=sys.stderr)
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()

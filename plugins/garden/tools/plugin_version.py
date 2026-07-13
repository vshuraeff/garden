#!/usr/bin/env -S uv run --no-project
"""Synchronize and enforce the GARDEN plugin SemVer across both harnesses."""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PLUGIN_ROOT.parent.parent
MANIFESTS = (
    PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
    PLUGIN_ROOT / ".claude-plugin" / "plugin.json",
)
SEMVER_CORE = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
VERSION_PATTERN = re.compile(rf'(?m)^(\s*"version"\s*:\s*")({SEMVER_CORE})("\s*,?\s*)$')


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> Version:
        match = re.fullmatch(
            r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value
        )
        if match is None:
            raise ValueError(f"not a strict SemVer core version: {value}")
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump(self, kind: str) -> Version:
        if kind == "major":
            return Version(self.major + 1, 0, 0)
        if kind == "minor":
            return Version(self.major, self.minor + 1, 0)
        if kind == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ValueError(f"unknown bump kind: {kind}")


def version_from_text(content: str) -> Version:
    matches = list(VERSION_PATTERN.finditer(content))
    if len(matches) != 1:
        raise ValueError("manifest must contain exactly one strict version field")
    return Version.parse(matches[0].group(2))


def replace_version(content: str, version: Version) -> str:
    if len(VERSION_PATTERN.findall(content)) != 1:
        raise ValueError("manifest must contain exactly one strict version field")
    return VERSION_PATTERN.sub(rf"\g<1>{version}\g<3>", content, count=1)


def current_version() -> Version:
    versions = {
        version_from_text(path.read_text(encoding="utf-8")) for path in MANIFESTS
    }
    if len(versions) != 1:
        raise ValueError("Codex and Claude manifest versions differ")
    return versions.pop()


def _atomic_write(path: Path, content: str) -> None:
    original_mode = stat.S_IMODE(path.stat().st_mode)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, original_mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def bump_manifests(kind: str) -> tuple[Version, Version]:
    before = current_version()
    after = before.bump(kind)
    replacements = [
        (path, replace_version(path.read_text(encoding="utf-8"), after))
        for path in MANIFESTS
    ]
    for path, content in replacements:
        _atomic_write(path, content)
    if current_version() != after:
        raise RuntimeError("manifest version synchronization failed")
    return before, after


def _base_version(base: str) -> Version:
    relative = MANIFESTS[1].relative_to(REPOSITORY_ROOT).as_posix()
    completed = subprocess.run(
        ["git", "show", f"{base}:{relative}"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return version_from_text(completed.stdout)


def plugin_changed(base: str) -> bool:
    completed = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            base,
            "--",
            "plugins/garden",
            ".agents/plugins/marketplace.json",
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError("git diff failed while checking plugin changes")
    return completed.returncode == 1


def check_version_bump(base: str) -> tuple[Version, Version]:
    baseline = _base_version(base)
    current = current_version()
    if plugin_changed(base) and current <= baseline:
        raise ValueError(
            f"plugin changed but version {current} is not greater than base {baseline}"
        )
    return baseline, current


def main() -> int:
    parser = argparse.ArgumentParser(prog="garden-plugin-version")
    subparsers = parser.add_subparsers(dest="command", required=True)
    bump_parser = subparsers.add_parser("bump")
    bump_parser.add_argument("kind", choices=("patch", "minor", "major"))
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--base", required=True)
    subparsers.add_parser("show")
    args = parser.parse_args()

    if args.command == "bump":
        before, after = bump_manifests(args.kind)
        print(f"{before} -> {after}")
    elif args.command == "check":
        baseline, current = check_version_bump(args.base)
        print(f"plugin version check passed: base={baseline} current={current}")
    else:
        print(current_version())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env -S uv run --no-project
"""Measure deterministic legacy configuration migration properties."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from lib.provenance import (
    git_commit,
    load_toolchain,
    normalize_path_bytes,
    platform_string,
    plugin_version,
    python_version_string,
    repository_root,
    sha256_bytes,
    sha256_file,
)


VALID_PROPERTIES = (
    "independent-output-parity",
    "config-validation",
    "force-idempotence",
    "tree-atomicity",
    "normalized-inspect-parity",
)


@dataclass(frozen=True)
class CommandResult:
    """Captured subprocess result with elapsed nanoseconds."""

    exit_code: int
    stdout: bytes
    stderr: bytes
    elapsed_ns: int


def benchmark_root() -> Path:
    """Return the benchmark directory."""

    return Path(__file__).resolve().parent


def detection_root() -> Path:
    """Return the reusable detection corpus root."""

    return benchmark_root() / "corpus" / "detection"


def invalid_root() -> Path:
    """Return the invalid migration corpus root."""

    return benchmark_root() / "corpus" / "migration-invalid"


def _garden_cli() -> Path:
    return repository_root() / "plugins" / "garden" / "tools" / "garden_cli.py"


def _run(*arguments: str) -> CommandResult:
    started = time.perf_counter_ns()
    completed = subprocess.run(
        ["uv", "run", "--no-project", str(_garden_cli()), *arguments],
        capture_output=True,
        check=False,
    )
    temporary_paths = [Path(value) for value in arguments if Path(value).is_absolute()]
    return CommandResult(
        completed.returncode,
        normalize_path_bytes(completed.stdout, temporary_paths),
        normalize_path_bytes(completed.stderr, temporary_paths),
        time.perf_counter_ns() - started,
    )


def _combine(results: Sequence[CommandResult]) -> CommandResult:
    return CommandResult(
        max((result.exit_code for result in results), default=0),
        b"\n".join(result.stdout for result in results),
        b"\n".join(result.stderr for result in results),
        sum(result.elapsed_ns for result in results),
    )


def _tree_hashes(root: Path, *, exclude_config: bool = False) -> dict[str, str]:
    hashes = {}
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        relative = path.relative_to(root).as_posix()
        if exclude_config and relative == ".garden.toml":
            continue
        hashes[relative] = sha256_file(path)
    return hashes


def _normalized_report(
    result: CommandResult,
) -> tuple[list[dict[str, Any]] | None, list[str]]:
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, []
    if not isinstance(payload, dict):
        return None, []
    findings = [
        finding
        for finding in payload.get("findings", [])
        if isinstance(finding, dict)
        and finding.get("rule") != "N-LEGACY-NAMING-REGISTRY"
    ]
    rules = sorted(
        str(finding["rule"])
        for finding in findings
        if isinstance(finding.get("rule"), str)
    )
    normalized = sorted(
        findings,
        key=lambda finding: (
            str(finding.get("severity")),
            str(finding.get("rule")),
            str(finding.get("path")),
            str(finding.get("message")),
        ),
    )
    return normalized, rules


def _outcome(**values: object) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _record(
    *,
    case_id: str,
    condition: str,
    passed: bool,
    command: CommandResult,
    finding_ids: Sequence[str],
    toolchain: Mapping[str, Any],
    commit: str,
    version: str,
) -> dict[str, Any]:
    return {
        "schema_version": str(toolchain["schema_version"]),
        "benchmark_version": str(toolchain["benchmark_version"]),
        "suite": "migration",
        "case_id": case_id,
        "condition": condition,
        "repository_commit": toolchain["repository_commit"],
        "garden_commit": commit,
        "plugin_version": version,
        "seed": toolchain["seed"],
        "expected_outcome": _outcome(passed=True),
        "actual_outcome": _outcome(passed=passed),
        "exit_code": command.exit_code,
        "finding_ids": sorted(set(finding_ids)),
        "stdout_sha256": sha256_bytes(command.stdout),
        "stderr_sha256": sha256_bytes(command.stderr),
        "elapsed_ns": command.elapsed_ns,
        "platform": platform_string(),
        "python_version": python_version_string(),
    }


def _valid_fixture_records(
    fixture: Path,
    toolchain: Mapping[str, Any],
    commit: str,
    version: str,
) -> Iterator[tuple[str, dict[str, Any], bool]]:
    source = fixture / "legacy"
    with tempfile.TemporaryDirectory(prefix="garden-migration-valid-") as directory:
        root = Path(directory)
        before = root / "before"
        first = root / "first"
        second = root / "second"
        shutil.copytree(source, before)
        shutil.copytree(source, first)
        shutil.copytree(source, second)
        original_hashes = _tree_hashes(source)

        legacy_inspect = _run("inspect", str(before))
        migrate_first = _run("migrate-config", str(first))
        migrate_second = _run("migrate-config", str(second))
        first_config = first / ".garden.toml"
        second_config = second / ".garden.toml"
        independent_pass = (
            migrate_first.exit_code == migrate_second.exit_code == 0
            and first_config.is_file()
            and second_config.is_file()
            and first_config.read_bytes() == second_config.read_bytes()
        )
        independent_command = _combine((migrate_first, migrate_second))
        yield (
            VALID_PROPERTIES[0],
            _record(
                case_id=f"{fixture.name}:{VALID_PROPERTIES[0]}",
                condition="valid",
                passed=independent_pass,
                command=independent_command,
                finding_ids=[],
                toolchain=toolchain,
                commit=commit,
                version=version,
            ),
            independent_pass,
        )

        validate_first = _run("config", "validate", str(first))
        validate_second = _run("config", "validate", str(second))
        validation_pass = validate_first.exit_code == validate_second.exit_code == 0
        validation_command = _combine((validate_first, validate_second))
        yield (
            VALID_PROPERTIES[1],
            _record(
                case_id=f"{fixture.name}:{VALID_PROPERTIES[1]}",
                condition="valid",
                passed=validation_pass,
                command=validation_command,
                finding_ids=[],
                toolchain=toolchain,
                commit=commit,
                version=version,
            ),
            validation_pass,
        )

        initial_content = first_config.read_bytes() if first_config.is_file() else b""
        force = _run("migrate-config", str(first), "--force")
        force_pass = (
            force.exit_code == 0
            and first_config.is_file()
            and first_config.read_bytes() == initial_content
        )
        yield (
            VALID_PROPERTIES[2],
            _record(
                case_id=f"{fixture.name}:{VALID_PROPERTIES[2]}",
                condition="valid",
                passed=force_pass,
                command=force,
                finding_ids=[],
                toolchain=toolchain,
                commit=commit,
                version=version,
            ),
            force_pass,
        )

        other_hashes = _tree_hashes(first, exclude_config=True)
        tree_pass = other_hashes == original_hashes and set(_tree_hashes(first)) == {
            *original_hashes,
            ".garden.toml",
        }
        yield (
            VALID_PROPERTIES[3],
            _record(
                case_id=f"{fixture.name}:{VALID_PROPERTIES[3]}",
                condition="valid",
                passed=tree_pass,
                command=migrate_first,
                finding_ids=[],
                toolchain=toolchain,
                commit=commit,
                version=version,
            ),
            tree_pass,
        )

        configured_inspect = _run("inspect", str(first))
        legacy_normalized, legacy_rules = _normalized_report(legacy_inspect)
        configured_normalized, configured_rules = _normalized_report(configured_inspect)
        parity_pass = (
            legacy_normalized is not None
            and configured_normalized is not None
            and legacy_normalized == configured_normalized
        )
        parity_command = _combine((legacy_inspect, configured_inspect))
        yield (
            VALID_PROPERTIES[4],
            _record(
                case_id=f"{fixture.name}:{VALID_PROPERTIES[4]}",
                condition="valid",
                passed=parity_pass,
                command=parity_command,
                finding_ids=sorted(set(legacy_rules) ^ set(configured_rules)),
                toolchain=toolchain,
                commit=commit,
                version=version,
            ),
            parity_pass,
        )


def _load_invalid_cases() -> list[dict[str, Any]]:
    value = json.loads((invalid_root() / "cases.json").read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("invalid migration corpus must contain exactly four cases")
    return value


def _materialize_invalid(case: Mapping[str, Any], root: Path) -> None:
    source = invalid_root() / str(case["fixture_path"])
    shutil.copytree(source, root, dirs_exist_ok=True)


def _invalid_record(
    case: Mapping[str, Any],
    toolchain: Mapping[str, Any],
    commit: str,
    version: str,
) -> tuple[dict[str, Any], bool]:
    with tempfile.TemporaryDirectory(prefix="garden-migration-invalid-") as directory:
        root = Path(directory) / "fixture"
        root.mkdir()
        _materialize_invalid(case, root)
        before = _tree_hashes(root)
        migrate = _run("migrate-config", str(root))
        signature = str(case["expected_signature"])
        if case["expected_behavior"] == "fail":
            unchanged = _tree_hashes(root) == before
            passed = (
                migrate.exit_code != 0
                and signature.encode() in migrate.stdout + migrate.stderr
                and unchanged
                and not (root / ".garden.toml").exists()
            )
            command = migrate
            findings = [signature] if signature.encode() in migrate.stderr else []
        else:
            inspect = _run("inspect", "--strict", str(root))
            passed = (
                migrate.exit_code == 0
                and inspect.exit_code != 0
                and signature.encode() in inspect.stdout + inspect.stderr
            )
            command = _combine((migrate, inspect))
            findings = [signature] if signature.encode() in inspect.stdout else []
    record = _record(
        case_id=f"{case['case_id']}:failure-atomicity",
        condition="invalid",
        passed=passed,
        command=command,
        finding_ids=findings,
        toolchain=toolchain,
        commit=commit,
        version=version,
    )
    return record, passed


def _write_records(
    stream: TextIO,
    valid_fixtures: Sequence[Path],
    invalid_cases: Sequence[Mapping[str, Any]],
    toolchain: Mapping[str, Any],
    commit: str,
    version: str,
) -> tuple[dict[str, int], int]:
    property_passes: dict[str, int] = defaultdict(int)
    for fixture in valid_fixtures:
        for property_name, record, passed in _valid_fixture_records(
            fixture, toolchain, commit, version
        ):
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            property_passes[property_name] += passed
    invalid_passes = 0
    for case in invalid_cases:
        record, passed = _invalid_record(case, toolchain, commit, version)
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        invalid_passes += passed
    return dict(property_passes), invalid_passes


def main(argv: Sequence[str] | None = None) -> int:
    """Run migration reproducibility and invalid-input properties."""

    valid = sorted(path for path in detection_root().iterdir() if path.is_dir())
    invalid = _load_invalid_cases()
    fixture_choices = [path.name for path in valid] + [
        str(case["case_id"]) for case in invalid
    ]
    parser = argparse.ArgumentParser(
        description="run deterministic migration reproducibility properties"
    )
    parser.add_argument("--fixture", choices=fixture_choices)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.fixture:
        valid = [path for path in valid if path.name == args.fixture]
        invalid = [case for case in invalid if case["case_id"] == args.fixture]

    toolchain = load_toolchain()
    commit = git_commit()
    version = plugin_version()
    if version != toolchain["plugin_version"]:
        parser.error("plugin version differs from benchmarks/toolchain.toml")

    if args.out is None:
        stats = _write_records(sys.stdout, valid, invalid, toolchain, commit, version)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="\n") as stream:
            stats = _write_records(stream, valid, invalid, toolchain, commit, version)
    property_passes, invalid_passes = stats
    valid_total = len(valid)
    rendered = " ".join(
        f"{name}={property_passes.get(name, 0)}/{valid_total}"
        for name in VALID_PROPERTIES
    )
    print(
        f"migration_properties {rendered} "
        f"failure_atomicity={invalid_passes}/{len(invalid)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

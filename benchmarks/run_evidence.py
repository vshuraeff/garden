#!/usr/bin/env -S uv run --no-project
"""Run isolated evidence-validator corpus cases.

Each payload is a registry-shaped Markdown file. An optional
``benchmark-citation`` separator carries a second Markdown document that is
materialized at ``docs/explanation/case.md`` inside the temporary repository.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

from lib.provenance import (
    git_commit,
    load_toolchain,
    platform_string,
    plugin_version,
    python_version_string,
    repository_root,
    sha256_bytes,
)


CITATION_SEPARATOR = "\n<!-- benchmark-citation -->\n"


def corpus_root() -> Path:
    """Return the evidence corpus directory."""

    return Path(__file__).resolve().parent / "corpus" / "evidence"


def _load_cases() -> list[dict[str, Any]]:
    value = json.loads((corpus_root() / "cases.json").read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != 48:
        raise ValueError("evidence corpus must contain exactly 48 cases")
    if not all(isinstance(case, dict) for case in value):
        raise TypeError("every evidence case must be an object")
    return value


def _materialize_case(case: Mapping[str, Any], root: Path) -> Path:
    payload = corpus_root() / str(case["payload_path"])
    content = payload.read_text(encoding="utf-8")
    registry_content, separator, citation_content = content.partition(
        CITATION_SEPARATOR
    )
    registry = root / "docs" / "evidence" / "evidence-registry.md"
    registry.parent.mkdir(parents=True)
    registry.write_text(registry_content.rstrip() + "\n", encoding="utf-8")
    if separator:
        citation = root / "docs" / "explanation" / "case.md"
        citation.parent.mkdir(parents=True)
        citation.write_text(citation_content.lstrip(), encoding="utf-8")

    validator = root / "plugins" / "garden" / "tools" / "validate_evidence.py"
    validator.parent.mkdir(parents=True)
    source = repository_root() / "plugins" / "garden" / "tools" / "validate_evidence.py"
    shutil.copy2(source, validator)
    return validator


def _outcome(**values: object) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _run_case(
    case: Mapping[str, Any],
    toolchain: Mapping[str, Any],
    commit: str,
    version: str,
) -> tuple[dict[str, Any], bool, bool]:
    with tempfile.TemporaryDirectory(prefix="garden-evidence-") as directory:
        root = Path(directory)
        validator = _materialize_case(case, root)
        started = time.perf_counter_ns()
        completed = subprocess.run(
            ["uv", "run", "--no-project", str(validator)],
            cwd=root,
            capture_output=True,
            check=False,
        )
        elapsed = time.perf_counter_ns() - started

    combined = completed.stdout + completed.stderr
    expect_detected = bool(case["expect_detected"])
    family = str(case["expected_diagnostic_family"])
    actual_detected = completed.returncode != 0
    family_seen = family == "none" or family.encode() in combined
    matched = actual_detected == expect_detected and (
        not expect_detected or family_seen
    )
    record = {
        "schema_version": str(toolchain["schema_version"]),
        "benchmark_version": str(toolchain["benchmark_version"]),
        "suite": "evidence",
        "case_id": case["case_id"],
        "condition": "defect" if expect_detected else "clean",
        "repository_commit": toolchain["repository_commit"],
        "garden_commit": commit,
        "plugin_version": version,
        "seed": toolchain["seed"],
        "expected_outcome": _outcome(
            detected=expect_detected,
            diagnostic_family=family,
        ),
        "actual_outcome": _outcome(
            detected=actual_detected,
            diagnostic_family_seen=family_seen,
            matched=matched,
        ),
        "exit_code": completed.returncode,
        "finding_ids": [family] if family != "none" and family_seen else [],
        "stdout_sha256": sha256_bytes(completed.stdout),
        "stderr_sha256": sha256_bytes(completed.stderr),
        "elapsed_ns": elapsed,
        "platform": platform_string(),
        "python_version": python_version_string(),
    }
    return record, actual_detected, matched


def _write_records(
    stream: TextIO,
    cases: Sequence[Mapping[str, Any]],
    toolchain: Mapping[str, Any],
    commit: str,
    version: str,
) -> tuple[int, int, int]:
    detected_defects = 0
    blocked_clean = 0
    matched = 0
    for case in cases:
        record, detected, case_matched = _run_case(case, toolchain, commit, version)
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        if case["expect_detected"]:
            detected_defects += detected
        else:
            blocked_clean += detected
        matched += case_matched
    return detected_defects, blocked_clean, matched


def main(argv: Sequence[str] | None = None) -> int:
    """Run selected evidence cases and emit raw records."""

    cases = _load_cases()
    case_ids = [str(case["case_id"]) for case in cases]
    parser = argparse.ArgumentParser(
        description="run isolated deterministic evidence-validator cases"
    )
    parser.add_argument("--case", choices=case_ids)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    selected = [case for case in cases if args.case in (None, case["case_id"])]

    toolchain = load_toolchain()
    commit = git_commit()
    version = plugin_version()
    if version != toolchain["plugin_version"]:
        parser.error("plugin version differs from benchmarks/toolchain.toml")

    if args.out is None:
        stats = _write_records(sys.stdout, selected, toolchain, commit, version)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="\n") as stream:
            stats = _write_records(stream, selected, toolchain, commit, version)
    detected_defects, blocked_clean, matched = stats
    defect_total = sum(bool(case["expect_detected"]) for case in selected)
    clean_total = len(selected) - defect_total
    print(
        f"supported_defect_recall={detected_defects}/{defect_total} "
        f"false_block_rate={blocked_clean}/{clean_total} "
        f"matched_expectations={matched}/{len(selected)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

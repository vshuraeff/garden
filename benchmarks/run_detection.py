#!/usr/bin/env -S uv run --no-project
"""Run the deterministic configured-detection corpus."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

from lib.garden_adapter import (
    classify_path,
    finding_ids_for_path,
    inspect_condition,
    scan_complete,
)
from lib.provenance import (
    git_commit,
    load_toolchain,
    platform_string,
    plugin_version,
    python_version_string,
    repository_root,
    sha256_bytes,
)


CONDITIONS = ("legacy", "configured")


def detection_root() -> Path:
    """Return the checked-in detection corpus root."""

    return Path(__file__).resolve().parent / "corpus" / "detection"


def fixture_names() -> list[str]:
    """Return fixture names in deterministic order."""

    return sorted(path.name for path in detection_root().iterdir() if path.is_dir())


def _load_labels(fixture: Path) -> list[dict[str, Any]]:
    value = json.loads((fixture / "labels.json").read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != 12:
        raise ValueError(f"fixture must contain exactly 12 labels: {fixture.name}")
    labels: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError(f"fixture label is not an object: {fixture.name}")
        labels.append(item)
    paths = [label.get("path") for label in labels]
    if any(not isinstance(path, str) or not path for path in paths):
        raise ValueError(f"fixture has an invalid label path: {fixture.name}")
    if len(set(paths)) != len(paths):
        raise ValueError(f"fixture has duplicate label paths: {fixture.name}")
    return sorted(labels, key=lambda label: str(label["path"]))


def _outcome(
    *,
    production_source: bool,
    test: bool,
    capability: str,
    scan_complete_value: bool,
) -> str:
    return json.dumps(
        {
            "capability": capability,
            "production_source": production_source,
            "scan_complete": scan_complete_value,
            "test": test,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _require_label_fields(label: Mapping[str, Any], fixture: str) -> None:
    required = {
        "path": str,
        "production_source": bool,
        "test": bool,
        "capability": str,
        "classification_reason": str,
        "expected_findings": list,
    }
    if set(label) != set(required):
        raise ValueError(f"label fields differ from schema in {fixture}: {label}")
    for field, field_type in required.items():
        if type(label[field]) is not field_type:
            raise TypeError(f"label {field} has the wrong type in {fixture}")
    if not all(isinstance(value, str) for value in label["expected_findings"]):
        raise TypeError(f"expected_findings contains a non-string in {fixture}")


def _records_for_fixture(
    fixture_name: str,
    toolchain: Mapping[str, Any],
    garden_commit: str,
    actual_plugin_version: str,
) -> Iterator[dict[str, Any]]:
    fixture = detection_root() / fixture_name
    labels = _load_labels(fixture)
    for label in labels:
        _require_label_fields(label, fixture_name)
    for condition in CONDITIONS:
        condition_root = fixture / condition
        for label in labels:
            path = condition_root / label["path"]
            if not path.is_file():
                raise FileNotFoundError(f"labeled path is missing: {path}")

        cli_result = inspect_condition(condition_root)
        complete = scan_complete(cli_result)
        for label in labels:
            relative_path = str(label["path"])
            actual = classify_path(condition_root, relative_path)
            yield {
                "schema_version": str(toolchain["schema_version"]),
                "benchmark_version": str(toolchain["benchmark_version"]),
                "suite": "detection",
                "case_id": f"{fixture_name}:{relative_path}",
                "condition": condition,
                "repository_commit": toolchain["repository_commit"],
                "garden_commit": garden_commit,
                "plugin_version": actual_plugin_version,
                "seed": toolchain["seed"],
                "expected_outcome": _outcome(
                    production_source=label["production_source"],
                    test=label["test"],
                    capability=label["capability"],
                    scan_complete_value=True,
                ),
                "actual_outcome": _outcome(
                    production_source=actual.production_source,
                    test=actual.test,
                    capability=actual.capability,
                    scan_complete_value=complete,
                ),
                "exit_code": cli_result.exit_code,
                "finding_ids": finding_ids_for_path(cli_result, relative_path),
                "stdout_sha256": sha256_bytes(cli_result.stdout),
                "stderr_sha256": sha256_bytes(cli_result.stderr),
                "elapsed_ns": cli_result.elapsed_ns,
                "platform": platform_string(),
                "python_version": python_version_string(),
            }


def _write_records(stream: TextIO, records: Iterator[dict[str, Any]]) -> int:
    count = 0
    for record in records:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        count += 1
    return count


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and emit detection records."""

    available = fixture_names()
    parser = argparse.ArgumentParser(
        description="run deterministic GARDEN configured-detection fixtures"
    )
    parser.add_argument("--fixture", choices=available)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    root = repository_root()
    toolchain = load_toolchain()
    actual_plugin_version = plugin_version(root)
    if actual_plugin_version != toolchain["plugin_version"]:
        parser.error(
            "plugin version differs from benchmarks/toolchain.toml: "
            f"{actual_plugin_version} != {toolchain['plugin_version']}"
        )
    selected = [args.fixture] if args.fixture else available
    commit = git_commit(root)

    def records() -> Iterator[dict[str, Any]]:
        for fixture in selected:
            yield from _records_for_fixture(
                fixture,
                toolchain,
                commit,
                actual_plugin_version,
            )

    if args.out is None:
        _write_records(sys.stdout, records())
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="\n") as stream:
            _write_records(stream, records())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

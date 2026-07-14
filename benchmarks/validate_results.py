#!/usr/bin/env -S uv run --no-project
"""Validate committed benchmark result structure and checksum integrity."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.provenance import sha256_file


SUITES = ("detection", "evidence", "mutations", "migration")


class ValidationError(ValueError):
    """One result-contract violation with a human-readable location."""


def benchmark_root() -> Path:
    """Return the benchmark directory."""

    return Path(__file__).resolve().parent


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValidationError(f"schema uses unsupported type {expected!r}")


def _resolve_ref(root_schema: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        raise ValidationError(f"unsupported schema reference {reference!r}")
    value: Any = root_schema
    for component in reference[2:].split("/"):
        value = value[component.replace("~1", "/").replace("~0", "~")]
    if not isinstance(value, Mapping):
        raise ValidationError(f"schema reference is not an object: {reference}")
    return value


def _validate(
    value: Any,
    schema: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    location: str,
) -> None:
    if "$ref" in schema:
        _validate(
            value, _resolve_ref(root_schema, str(schema["$ref"])), root_schema, location
        )
        return
    if "const" in schema and value != schema["const"]:
        raise ValidationError(f"{location}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{location}: value {value!r} is outside the enum")
    expected_types = schema.get("type")
    if isinstance(expected_types, str):
        expected_types = [expected_types]
    if isinstance(expected_types, list) and not any(
        _json_type_matches(value, str(expected)) for expected in expected_types
    ):
        raise ValidationError(
            f"{location}: expected type {' or '.join(map(str, expected_types))}"
        )
    if isinstance(value, dict):
        required = schema.get("required", [])
        for field in required:
            if field not in value:
                raise ValidationError(f"{location}: missing required field {field}")
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            raise ValidationError(f"{location}: schema properties are invalid")
        for field, field_value in value.items():
            if field in properties:
                field_schema = properties[field]
            else:
                additional = schema.get("additionalProperties", True)
                if additional is False:
                    raise ValidationError(f"{location}: unexpected field {field}")
                if additional is True:
                    continue
                field_schema = additional
            if not isinstance(field_schema, Mapping):
                raise ValidationError(f"{location}.{field}: schema is invalid")
            _validate(field_value, field_schema, root_schema, f"{location}.{field}")
    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                _validate(item, item_schema, root_schema, f"{location}[{index}]")
        if schema.get("uniqueItems") is True:
            rendered = [json.dumps(item, sort_keys=True) for item in value]
            if len(rendered) != len(set(rendered)):
                raise ValidationError(f"{location}: array items are not unique")
    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            raise ValidationError(f"{location}: string is too short")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            raise ValidationError(f"{location}: value does not match {pattern}")
        if schema.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValidationError(f"{location}: invalid date-time") from error
            if parsed.tzinfo is None:
                raise ValidationError(f"{location}: date-time has no timezone")
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and "minimum" in schema
        and value < schema["minimum"]
    ):
        raise ValidationError(f"{location}: value is below minimum")


def _load_schema(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: schema is not an object")
    return value


def _validate_jsonl(path: Path, suite: str, schema: Mapping[str, Any]) -> int:
    count = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValidationError(f"{path}: cannot read: {error}") from error
    if not lines:
        raise ValidationError(f"{path}: JSONL file is empty")
    for line_number, line in enumerate(lines, start=1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValidationError(
                f"{path}:{line_number}: invalid JSON: {error}"
            ) from error
        _validate(value, schema, schema, f"{path.name}:{line_number}")
        if value.get("suite") != suite:
            raise ValidationError(
                f"{path.name}:{line_number}.suite: expected {suite!r}"
            )
        count += 1
    return count


def _validate_summary(path: Path, schema: Mapping[str, Any]) -> None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"{path}: cannot load summary: {error}") from error
    _validate(value, schema, schema, path.name)


def _validate_checksums(results_dir: Path) -> int:
    checksum_path = results_dir / "sha256sums.txt"
    try:
        lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValidationError(f"{checksum_path}: cannot read: {error}") from error
    entries: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        digest, separator, filename = line.partition("  ")
        if not separator or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValidationError(
                f"{checksum_path}:{line_number}: malformed checksum entry"
            )
        if not filename or Path(filename).name != filename:
            raise ValidationError(
                f"{checksum_path}:{line_number}: invalid result filename"
            )
        if filename in entries:
            raise ValidationError(
                f"{checksum_path}:{line_number}: duplicate entry {filename}"
            )
        entries[filename] = digest
    expected_names = {
        path.name
        for path in results_dir.iterdir()
        if path.is_file() and path.name != checksum_path.name
    }
    if set(entries) != expected_names:
        missing = sorted(expected_names - set(entries))
        extra = sorted(set(entries) - expected_names)
        raise ValidationError(
            f"{checksum_path}: entry set differs; missing={missing}, extra={extra}"
        )
    for filename, expected in entries.items():
        actual = sha256_file(results_dir / filename)
        if actual != expected:
            raise ValidationError(
                f"{checksum_path}: hash mismatch for {filename}: {actual} != {expected}"
            )
    return len(entries)


def validate_results(results_dir: Path) -> tuple[dict[str, int], int]:
    """Validate all raw records, summary structure, and result hashes."""

    schemas = benchmark_root() / "schemas"
    raw_schema = _load_schema(schemas / "raw-result.schema.json")
    summary_schema = _load_schema(schemas / "summary.schema.json")
    counts = {
        suite: _validate_jsonl(results_dir / f"{suite}.jsonl", suite, raw_schema)
        for suite in SUITES
    }
    _validate_summary(results_dir / "summary.json", summary_schema)
    checksum_count = _validate_checksums(results_dir)
    return counts, checksum_count


def main(argv: Sequence[str] | None = None) -> int:
    """Validate result artifacts and report the first contract violation."""

    parser = argparse.ArgumentParser(description="validate Benchmark v1 artifacts")
    parser.add_argument(
        "--results-dir", type=Path, default=benchmark_root() / "results" / "v1"
    )
    args = parser.parse_args(argv)
    try:
        counts, checksum_count = validate_results(args.results_dir)
    except (OSError, KeyError, TypeError, ValidationError) as error:
        print(f"benchmark result validation failed: {error}", file=sys.stderr)
        return 1
    rendered = " ".join(f"{suite}={count}" for suite, count in counts.items())
    print(f"benchmark result validation passed: {rendered} checksums={checksum_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

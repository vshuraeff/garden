"""Normalize benchmark artifacts for deterministic comparisons."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _normalized_json(path: Path) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value.pop("generated_at", None)
        provenance_blocks = [value]
        if isinstance(value.get("toolchain"), dict):
            provenance_blocks.append(value["toolchain"])
        for block in provenance_blocks:
            block.pop("garden_commit", None)
            block.pop("repository_commit", None)
            block.pop("platform", None)
            block.pop("python_version", None)
    return value


def _normalized_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise TypeError(f"{path}: JSONL record is not an object")
        value.pop("elapsed_ns", None)
        value.pop("garden_commit", None)
        value.pop("repository_commit", None)
        environment_blocks = [value]
        if isinstance(value.get("toolchain"), dict):
            environment_blocks.append(value["toolchain"])
        for block in environment_blocks:
            block.pop("platform", None)
            block.pop("python_version", None)
        records.append(value)
    return records


def _checksum_names(path: Path) -> list[str]:
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        _, separator, name = line.partition("  ")
        if not separator:
            raise ValueError(f"{path}: malformed checksum line")
        names.append(name)
    return names


def _normalized_artifact(path: Path) -> Any:
    if path.suffix == ".jsonl":
        return _normalized_jsonl(path)
    if path.name == "sha256sums.txt":
        return _checksum_names(path)
    if path.suffix == ".json":
        return _normalized_json(path)
    return path.read_bytes()

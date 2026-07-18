#!/usr/bin/env -S uv run --no-project
"""Normalize benchmark outputs and compare them across matrix cells."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from lib.matrix_compare import evaluate_matrix_identity
from lib.normalized_artifacts import _normalized_artifact


EXPECTED_CELLS = (
    "ubuntu-latest-3.11",
    "ubuntu-latest-3.14",
    "macos-latest-3.11",
    "macos-latest-3.14",
)
NORMALIZED_ARTIFACTS = ("migration.jsonl", "summary.json")
BUNDLE_NAME = "bundle.json"


def _write_normalized_bundle(results_dir: Path, output: Path) -> None:
    bundle = {}
    for name in NORMALIZED_ARTIFACTS:
        path = results_dir / name
        if not path.is_file():
            raise ValueError(f"missing benchmark artifact: {path}")
        bundle[name] = _normalized_artifact(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _parse_cell_dirs(values: Sequence[str]) -> dict[str, Path]:
    cell_dirs = {}
    for value in values:
        name, separator, directory = value.partition("=")
        if not separator or not name or not directory:
            raise ValueError(f"invalid --cell-dir {value!r}; expected NAME=PATH")
        if name in cell_dirs:
            raise ValueError(f"duplicate --cell-dir for {name}")
        cell_dirs[name] = Path(directory)
    return cell_dirs


def _read_bundle(directory: Path) -> dict[str, object]:
    path = directory / BUNDLE_NAME
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path}: normalized bundle is not an object")
    return {str(name): artifact for name, artifact in value.items()}


def _compare(cell_dir_values: Sequence[str]) -> int:
    cell_dirs = _parse_cell_dirs(cell_dir_values)
    cell_artifacts = {
        cell: _read_bundle(directory) for cell, directory in cell_dirs.items()
    }
    result = evaluate_matrix_identity(EXPECTED_CELLS, cell_artifacts)
    if result.passed:
        print(
            f"matrix identity check passed for {len(EXPECTED_CELLS)} cells",
            file=sys.stderr,
        )
        return 0

    print("matrix identity check failed", file=sys.stderr)
    if result.missing_cells:
        print(
            "missing cells: " + ", ".join(result.missing_cells),
            file=sys.stderr,
        )
    if result.unexpected_cells:
        print(
            "unexpected cells: " + ", ".join(result.unexpected_cells),
            file=sys.stderr,
        )
    for difference in result.differences:
        print(
            f"{difference.cell} differs from {difference.reference_cell} in "
            f"{difference.artifact}: {difference.detail}",
            file=sys.stderr,
        )
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Normalize one run or compare normalized matrix-cell bundles."""

    parser = argparse.ArgumentParser(
        description="normalize and compare Benchmark v1 matrix artifacts"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    normalize_parser = subparsers.add_parser(
        "normalize", help="write a normalized benchmark artifact bundle"
    )
    normalize_parser.add_argument("--results-dir", type=Path, required=True)
    normalize_parser.add_argument("--output", type=Path, required=True)

    compare_parser = subparsers.add_parser(
        "compare", help="compare normalized bundles from all matrix cells"
    )
    compare_parser.add_argument(
        "--cell-dir",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="matrix cell name and downloaded artifact directory",
    )

    args = parser.parse_args(argv)
    try:
        if args.command == "normalize":
            _write_normalized_bundle(args.results_dir, args.output)
            print(f"wrote normalized benchmark bundle to {args.output}")
            return 0
        return _compare(args.cell_dir)
    except (OSError, TypeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

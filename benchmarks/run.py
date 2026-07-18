#!/usr/bin/env -S uv run --no-project
"""Run all Benchmark v1 suites and verify normalized reproducibility."""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

import run_detection
import run_evidence
import run_migration
import run_mutations
import summarize
from lib.normalized_artifacts import _normalized_artifact
from lib.provenance import (
    git_commit,
    load_toolchain,
    platform_string,
    plugin_tree_hash,
    plugin_version,
    python_version_string,
    sha256_file,
)


SuiteMain = Callable[[Sequence[str] | None], int]
SUITES: dict[str, tuple[str, SuiteMain]] = {
    "detection": ("run_detection.py", run_detection.main),
    "evidence": ("run_evidence.py", run_evidence.main),
    "mutations": ("run_mutations.py", run_mutations.main),
    "migration": ("run_migration.py", run_migration.main),
}
RESULT_FILES = (
    "ablations.json",
    "detection.jsonl",
    "evidence.jsonl",
    "metadata.json",
    "migration.jsonl",
    "mutations.jsonl",
    "summary.json",
    "sha256sums.txt",
)


def benchmark_root() -> Path:
    """Return the benchmark directory."""

    return Path(__file__).resolve().parent


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_metadata(
    output_dir: Path, generated_at: str, suite_order: Sequence[str]
) -> None:
    toolchain = load_toolchain()
    scripts = {
        suite: {
            "path": f"benchmarks/{script}",
            "sha256": sha256_file(benchmark_root() / script),
        }
        for suite, (script, _) in sorted(SUITES.items())
    }
    scripts["summary"] = {
        "path": "benchmarks/summarize.py",
        "sha256": sha256_file(benchmark_root() / "summarize.py"),
    }
    scripts["orchestration"] = {
        "path": "benchmarks/run.py",
        "sha256": sha256_file(benchmark_root() / "run.py"),
    }
    support_files = {
        f"benchmarks/lib/{name}": sha256_file(benchmark_root() / "lib" / name)
        for name in (
            "garden_adapter.py",
            "metrics.py",
            "mutation_ops.py",
            "provenance.py",
        )
    }
    metadata = {
        "schema_version": str(toolchain["schema_version"]),
        "benchmark_version": str(toolchain["benchmark_version"]),
        "generated_at": generated_at,
        "repository_commit": toolchain["repository_commit"],
        "garden_commit": git_commit(),
        "plugin_version": plugin_version(),
        "seed": toolchain["seed"],
        "platform": platform_string(),
        "python_version": python_version_string(),
        "suite_execution_order": list(suite_order),
        "producers": scripts,
        "support_files": support_files,
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_checksums(output_dir: Path) -> None:
    checksum_path = output_dir / "sha256sums.txt"
    files = sorted(
        path
        for path in output_dir.iterdir()
        if path.is_file() and path.name != checksum_path.name
    )
    checksum_path.write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in files),
        encoding="utf-8",
    )


def _run_all(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    toolchain = load_toolchain()
    current_plugin_tree = plugin_tree_hash()
    if current_plugin_tree != toolchain["plugin_tree_commit"]:
        raise RuntimeError(
            "plugin subtree differs from benchmarks/toolchain.toml: "
            f"{current_plugin_tree} != {toolchain['plugin_tree_commit']}"
        )
    current_version = plugin_version()
    if current_version != toolchain["plugin_version"]:
        raise RuntimeError(
            "plugin version differs from benchmarks/toolchain.toml: "
            f"{current_version} != {toolchain['plugin_version']}"
        )
    order = list(SUITES)
    random.Random(int(toolchain["seed"])).shuffle(order)
    for suite in order:
        _, suite_main = SUITES[suite]
        print(f"running {suite}", file=sys.stderr)
        result = suite_main(["--out", str(output_dir / f"{suite}.jsonl")])
        if result != 0:
            raise RuntimeError(f"{suite} runner exited {result}")
    generated_at = _generated_at()
    summarize_result = summarize.main(
        [
            "--results-dir",
            str(output_dir),
            "--generated-at",
            generated_at,
        ]
    )
    if summarize_result != 0:
        raise RuntimeError(f"summarizer exited {summarize_result}")
    _write_metadata(output_dir, generated_at, order)
    _write_checksums(output_dir)


def _check(reference_dir: Path) -> int:
    missing = [name for name in RESULT_FILES if not (reference_dir / name).is_file()]
    if missing:
        print(f"missing reference result files: {', '.join(missing)}", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix="garden-benchmark-check-") as directory:
        candidate_dir = Path(directory) / "v1"
        _run_all(candidate_dir)
        drift = []
        for name in RESULT_FILES:
            if _normalized_artifact(reference_dir / name) != _normalized_artifact(
                candidate_dir / name
            ):
                drift.append(name)
    if drift:
        print(
            "reproducibility drift after normalizing timing and provenance fields: "
            + ", ".join(drift),
            file=sys.stderr,
        )
        return 1
    print("normalized reproducibility check passed", file=sys.stderr)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run all suites or compare a fresh run with existing results."""

    parser = argparse.ArgumentParser(
        description="run deterministic Benchmark v1 suites"
    )
    parser.add_argument(
        "--out-dir", type=Path, default=benchmark_root() / "results" / "v1"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="rerun in a temporary directory and compare normalized results",
    )
    args = parser.parse_args(argv)
    if args.check:
        return _check(args.out_dir)
    _run_all(args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

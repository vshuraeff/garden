#!/usr/bin/env -S uv run --no-project
"""Render the generated benchmark report region from committed artifacts.

Gate-family ablations live in ablations.json because summary.schema.json has no
ablation field. This renderer reads that separate, checksum-covered artifact.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


BEGIN = "<!-- BEGIN GENERATED RESULTS -->"
END = "<!-- END GENERATED RESULTS -->"
SUITE_ORDER = ("detection", "evidence", "mutations", "migration")
COMPARISONS = {
    "detection": (
        ("configured_max_error_rate", "configured_error_rate"),
        ("min_absolute_error_reduction", "absolute_error_reduction"),
        ("min_relative_error_reduction", "relative_error_reduction"),
        ("allow_project_type_mean_regression", "project_type_mean_regression_present"),
        ("min_improved_repositories", "improved_repositories"),
        ("repository_count", "repository_count"),
        ("source_max_false_positive_rate", "source_false_positive_rate"),
        ("source_max_false_negative_rate", "source_false_negative_rate"),
        ("test_max_false_positive_rate", "test_false_positive_rate"),
        ("test_max_false_negative_rate", "test_false_negative_rate"),
        ("capability_min_exact_accuracy", "capability_exact_accuracy"),
        ("incomplete_scan_counts_as_pass", "incomplete_scan_present"),
    ),
    "evidence": (
        ("defect_recall_required", "defects_detected"),
        ("defect_total", "defect_total"),
        ("false_blocks_allowed", "clean_false_blocks"),
        ("clean_total", "clean_total"),
    ),
    "mutations": (
        ("killed_required", "must_block_killed"),
        ("mutation_total", "must_block_total"),
        ("clean_blocked_allowed", "clean_blocked"),
        ("clean_total", "clean_total"),
        ("gap_probes_required", "gap_probe_total"),
        ("gap_probe_total", "gap_probe_total"),
    ),
    "migration": (
        ("cases_required_per_property", "minimum_property_pass_count"),
        ("case_total", "valid_fixture_count"),
        ("property_count", "property_count"),
        ("failure_atomicity_required", "failure_atomicity_passed"),
        ("failure_atomicity_total", "failure_atomicity_total"),
    ),
}


def repository_root() -> Path:
    """Return the repository root."""

    return Path(__file__).resolve().parents[1]


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path}: expected JSON object")
    return value


def _render_scalar(value: Any) -> str:
    if value is None:
        return "not applicable"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def _summary_sha(checksum_path: Path) -> str:
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        digest, separator, filename = line.partition("  ")
        if separator and filename == "summary.json":
            return digest
    raise ValueError(f"{checksum_path}: summary.json checksum is missing")


def _suite_table(summary: Mapping[str, Any]) -> list[str]:
    lines = [
        "### Suite status",
        "",
        "| Suite | Status | Records | Passed records | Failed records | Incomplete |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    suites = summary["suites"]
    for name in SUITE_ORDER:
        suite = suites[name]
        counts = suite["counts"]
        lines.append(
            f"| {name} | {'pass' if suite['passed'] else 'fail'} | "
            f"{counts['total']} | {counts['passed']} | {counts['failed']} | "
            f"{counts['incomplete']} |"
        )
    lines.extend(
        [
            "",
            f"Top-level result: **{'pass' if summary['passed'] else 'fail'}**.",
        ]
    )
    return lines


def _matrix_identity_table(summary: Mapping[str, Any]) -> list[str]:
    identity = summary["matrix_identity"]
    lines = [
        "",
        "### Matrix identity",
        "",
        "| Property | Value |",
        "| --- | --- |",
    ]
    for key in (
        "required_combinations",
        "observed_combinations",
        "identical",
        "enforced_in",
    ):
        lines.append(f"| `{key}` | {_render_scalar(identity[key])} |")
    return lines


def _comparison_tables(summary: Mapping[str, Any]) -> list[str]:
    lines = ["", "### Thresholds and actual values"]
    suites = summary["suites"]
    for name in SUITE_ORDER:
        suite = suites[name]
        lines.extend(
            [
                "",
                f"#### {name.capitalize()}",
                "",
                "| Protocol key | Preregistered value | Actual metric | Actual value |",
                "| --- | ---: | --- | ---: |",
            ]
        )
        for threshold_key, metric_key in COMPARISONS[name]:
            lines.append(
                f"| `{threshold_key}` | "
                f"{_render_scalar(suite['thresholds'][threshold_key])} | "
                f"`{metric_key}` | {_render_scalar(suite['metrics'][metric_key])} |"
            )
    return lines


def _ablation_tables(ablations: Mapping[str, Any]) -> list[str]:
    lines = [
        "",
        "### Gate-family ablation accounting",
        "",
        "Ablations use only the checked-in must-block mutation rows and mapped, "
        "observed rule IDs. They do not measure outcomes outside this corpus.",
        "",
        "| Family | Mapped rules | Observed rules | Computed |",
        "| --- | ---: | ---: | --- |",
    ]
    presence = ablations["family_presence"]
    computed = ablations["computed_families"]
    for family in ("D", "N", "G", "A", "R", "E"):
        values = presence[family]
        lines.append(
            f"| {family} | {values['mapped_rule_count']} | "
            f"{values['observed_rule_count']} | "
            f"{'yes' if family in computed else 'no'} |"
        )
    lines.extend(
        [
            "",
            "| Family | Targeted killed / total | Targeted recall | Standalone coverage | Leave-one-out loss |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for family, values in sorted(computed.items()):
        lines.append(
            f"| {family} | {values['targeted_killed']} / "
            f"{values['targeted_mutations']} | "
            f"{_render_scalar(values['targeted_recall'])} | "
            f"{values['standalone_covered_mutations']} / "
            f"{ablations['must_block_total']} | {values['leave_one_out_loss']} |"
        )
    absent = ", ".join(ablations["absent_families"])
    lines.extend(["", f"Families without observed mapped rules: {absent}."])
    return lines


def generated_region(
    summary: Mapping[str, Any], ablations: Mapping[str, Any], summary_sha: str
) -> str:
    """Render the complete generated region, including boundary markers."""

    lines = [BEGIN]
    lines.extend(_suite_table(summary))
    lines.extend(_matrix_identity_table(summary))
    lines.extend(_comparison_tables(summary))
    lines.extend(_ablation_tables(ablations))
    lines.extend(
        [
            "",
            "### Result integrity and reproduction",
            "",
            f"`summary.json` SHA-256: `{summary_sha}`",
            "",
            "```sh",
            "uv run --no-project benchmarks/run.py",
            "uv run --no-project benchmarks/run.py --check",
            "uv run --no-project benchmarks/validate_results.py",
            "```",
            END,
        ]
    )
    return "\n".join(lines)


def render(document: Path, results_dir: Path) -> None:
    """Replace only the marked generated region in the report document."""

    content = document.read_text(encoding="utf-8")
    begin = content.find(BEGIN)
    end = content.find(END)
    if begin < 0 or end < 0 or end < begin:
        raise ValueError(f"{document}: generated region markers are missing or invalid")
    end += len(END)
    summary = _load_object(results_dir / "summary.json")
    ablations = _load_object(results_dir / "ablations.json")
    replacement = generated_region(
        summary, ablations, _summary_sha(results_dir / "sha256sums.txt")
    )
    updated = content[:begin] + replacement + content[end:]
    document.write_text(updated, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Render the generated result region from a selected result directory."""

    root = repository_root()
    parser = argparse.ArgumentParser(description="render Benchmark v1 report results")
    parser.add_argument(
        "--results-dir", type=Path, default=root / "benchmarks" / "results" / "v1"
    )
    parser.add_argument(
        "--document", type=Path, default=root / "docs" / "evidence" / "benchmark-v1.md"
    )
    args = parser.parse_args(argv)
    render(args.document, args.results_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

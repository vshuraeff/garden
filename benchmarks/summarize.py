#!/usr/bin/env -S uv run --no-project
"""Summarize raw benchmark results and compute gate-family ablations."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

from lib.metrics import (
    absolute_improvement,
    capability_exact_match_accuracy,
    classification_error_rate,
    false_negative_rate,
    false_positive_rate,
    improved_fixture_count,
    path_error,
    per_project_type_mean_error_rates,
    relative_error_reduction,
    scan_counts_as_pass,
)
from lib.provenance import (
    git_commit,
    load_toolchain,
    platform_string,
    plugin_version,
    python_version_string,
)


SUITES = ("detection", "evidence", "mutations", "migration")
PRINCIPLE_FAMILIES = ("D", "N", "G", "A", "R", "E")


def benchmark_root() -> Path:
    """Return the benchmark directory."""

    return Path(__file__).resolve().parent


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_protocol(
    path: Path | None = None,
    toolchain: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected = path
    if selected is None:
        values = toolchain if toolchain is not None else load_toolchain()
        selected = Path(str(values.get("protocol_file", "protocol-v1.1.toml")))
    if not selected.is_absolute():
        selected = benchmark_root() / selected
    with selected.open("rb") as handle:
        return tomllib.load(handle)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error
        if not isinstance(value, dict):
            raise TypeError(f"{path}:{line_number}: record is not an object")
        records.append(value)
    return records


def _outcome(record: Mapping[str, Any], field: str) -> dict[str, Any]:
    value = json.loads(str(record[field]))
    if not isinstance(value, dict):
        raise TypeError(f"{record['case_id']}: {field} is not an object")
    return value


def _counts(total: int, passed: int, incomplete: int = 0) -> dict[str, int]:
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "incomplete": incomplete,
    }


def _scalar_thresholds(section: Mapping[str, Any]) -> dict[str, Any]:
    values = {}
    for key, value in section.items():
        if not isinstance(value, (bool, int, float, str)):
            raise TypeError(f"threshold {key} is not scalar")
        values[key] = value
    return values


def _detection_summary(
    records: list[dict[str, Any]], thresholds: Mapping[str, Any]
) -> dict[str, Any]:
    legacy = [record for record in records if record["condition"] == "legacy"]
    configured = [record for record in records if record["condition"] == "configured"]
    legacy_error = classification_error_rate(legacy)
    configured_error = classification_error_rate(configured)
    absolute_reduction = absolute_improvement(legacy_error, configured_error)
    relative_reduction = relative_error_reduction(legacy_error, configured_error)
    project_means = per_project_type_mean_error_rates(records)
    regressions = sum(
        values.get("configured", 0.0) > values.get("legacy", 0.0)
        for values in project_means.values()
        if "configured" in values and "legacy" in values
    )
    incomplete = sum(
        _outcome(record, "actual_outcome").get("scan_complete") is not True
        for record in records
    )
    complete_and_correct = sum(
        not path_error(record)
        and _outcome(record, "actual_outcome").get("scan_complete") is True
        for record in records
    )
    metrics = {
        "repository_count": len(
            {str(record["case_id"]).split(":", 1)[0] for record in records}
        ),
        "legacy_error_rate": legacy_error,
        "configured_error_rate": configured_error,
        "absolute_error_reduction": absolute_reduction,
        "relative_error_reduction": relative_reduction,
        "improved_repositories": improved_fixture_count(records),
        "project_type_mean_regressions": regressions,
        "project_type_mean_regression_present": regressions > 0,
        "source_false_positive_rate": false_positive_rate(
            configured, "production_source"
        ),
        "source_false_negative_rate": false_negative_rate(
            configured, "production_source"
        ),
        "test_false_positive_rate": false_positive_rate(configured, "test"),
        "test_false_negative_rate": false_negative_rate(configured, "test"),
        "capability_exact_accuracy": capability_exact_match_accuracy(configured),
        "scan_complete": incomplete == 0 and bool(records),
        "incomplete_scan_present": incomplete > 0,
    }
    threshold_pass = (
        configured_error <= float(thresholds["configured_max_error_rate"])
        and absolute_reduction >= float(thresholds["min_absolute_error_reduction"])
        and relative_reduction >= float(thresholds["min_relative_error_reduction"])
        and (bool(thresholds["allow_project_type_mean_regression"]) or regressions == 0)
        and metrics["improved_repositories"]
        >= int(thresholds["min_improved_repositories"])
        and metrics["source_false_positive_rate"]
        <= float(thresholds["source_max_false_positive_rate"])
        and metrics["source_false_negative_rate"]
        <= float(thresholds["source_max_false_negative_rate"])
        and metrics["test_false_positive_rate"]
        <= float(thresholds["test_max_false_positive_rate"])
        and metrics["test_false_negative_rate"]
        <= float(thresholds["test_max_false_negative_rate"])
        and metrics["capability_exact_accuracy"]
        >= float(thresholds["capability_min_exact_accuracy"])
    )
    passed = scan_counts_as_pass(records, threshold_pass)
    return {
        "counts": _counts(len(records), complete_and_correct, incomplete),
        "thresholds": _scalar_thresholds(thresholds),
        "metrics": metrics,
        "passed": passed,
    }


def _evidence_summary(
    records: list[dict[str, Any]], thresholds: Mapping[str, Any]
) -> dict[str, Any]:
    defects = [record for record in records if record["condition"] == "defect"]
    clean = [record for record in records if record["condition"] == "clean"]
    detected = sum(
        _outcome(record, "actual_outcome").get("detected") is True
        and _outcome(record, "actual_outcome").get("diagnostic_family_seen") is True
        for record in defects
    )
    false_blocks = sum(
        _outcome(record, "actual_outcome").get("detected") is True for record in clean
    )
    passed_cases = detected + len(clean) - false_blocks
    metrics = {
        "defects_detected": detected,
        "defect_total": len(defects),
        "supported_defect_recall": detected / len(defects) if defects else 0.0,
        "clean_false_blocks": false_blocks,
        "clean_total": len(clean),
        "false_block_rate": false_blocks / len(clean) if clean else 0.0,
    }
    passed = (
        detected >= int(thresholds["defect_recall_required"])
        and len(defects) == int(thresholds["defect_total"])
        and false_blocks <= int(thresholds["false_blocks_allowed"])
        and len(clean) == int(thresholds["clean_total"])
    )
    return {
        "counts": _counts(len(records), passed_cases),
        "thresholds": _scalar_thresholds(thresholds),
        "metrics": metrics,
        "passed": passed,
    }


def _mutation_summary(
    records: list[dict[str, Any]], thresholds: Mapping[str, Any]
) -> dict[str, Any]:
    must_block = [record for record in records if record["condition"] == "must_block"]
    gap_probes = [record for record in records if record["condition"] == "gap_probe"]
    clean = [record for record in records if record["condition"] == "clean_control"]
    killed = sum(
        _outcome(record, "actual_outcome").get("killed") is True
        for record in must_block
    )
    clean_blocked = sum(
        _outcome(record, "actual_outcome").get("blocked") is True for record in clean
    )
    gap_detected = sum(
        _outcome(record, "actual_outcome").get("detected") is True
        for record in gap_probes
    )
    gap_blocked = sum(
        _outcome(record, "actual_outcome").get("blocked") is True
        for record in gap_probes
    )
    gap_kinds: dict[str, int] = defaultdict(int)
    detected_by_kind: dict[str, int] = defaultdict(int)
    for record in gap_probes:
        kind = str(_outcome(record, "expected_outcome")["gap_probe_kind"])
        gap_kinds[kind] += 1
        if _outcome(record, "actual_outcome").get("detected") is True:
            detected_by_kind[kind] += 1
    metrics = {
        "must_block_killed": killed,
        "must_block_total": len(must_block),
        "kill_rate": killed / len(must_block) if must_block else 0.0,
        "clean_blocked": clean_blocked,
        "clean_total": len(clean),
        "clean_false_block_rate": clean_blocked / len(clean) if clean else 0.0,
        "gap_probe_total": len(gap_probes),
        "gap_probe_detected": gap_detected,
        "gap_probe_blocked": gap_blocked,
        "gap_detect_only_total": gap_kinds["detect_only"],
        "gap_detect_only_detected": detected_by_kind["detect_only"],
        "gap_known_unenforced_total": gap_kinds["known_unenforced"],
        "gap_known_unenforced_detected": detected_by_kind["known_unenforced"],
    }
    passed_cases = killed + len(gap_probes) + len(clean) - clean_blocked
    passed = (
        killed >= int(thresholds["killed_required"])
        and len(must_block) == int(thresholds["mutation_total"])
        and clean_blocked <= int(thresholds["clean_blocked_allowed"])
        and len(clean) == int(thresholds["clean_total"])
        and len(gap_probes) >= int(thresholds["gap_probes_required"])
        and len(gap_probes) == int(thresholds["gap_probe_total"])
    )
    return {
        "counts": _counts(len(records), passed_cases),
        "thresholds": _scalar_thresholds(thresholds),
        "metrics": metrics,
        "passed": passed,
    }


def _matrix_comparison(
    records: list[dict[str, Any]], toolchain: Mapping[str, Any]
) -> tuple[int, int, bool]:
    combinations = {
        (
            str(record["platform"]),
            ".".join(str(record["python_version"]).split(".")[:2]),
        )
        for record in records
    }
    expected_combinations = set(
        product(toolchain["platforms"], toolchain["python_versions"])
    )
    matrix_groups: dict[tuple[str, str], dict[tuple[str, str], str]] = defaultdict(dict)
    for record in records:
        combination = (
            str(record["platform"]),
            ".".join(str(record["python_version"]).split(".")[:2]),
        )
        normalized = {
            key: value
            for key, value in record.items()
            if key not in {"elapsed_ns", "platform", "python_version"}
        }
        matrix_groups[(str(record["case_id"]), str(record["condition"]))][
            combination
        ] = json.dumps(normalized, sort_keys=True)
    identical = combinations == expected_combinations and all(
        set(group) == expected_combinations and len(set(group.values())) == 1
        for group in matrix_groups.values()
    )
    return len(combinations), len(expected_combinations), identical


def _matrix_identity_summary(
    records: list[dict[str, Any]],
    settings: Mapping[str, Any],
    toolchain: Mapping[str, Any],
) -> dict[str, Any]:
    observed, _expected, identical = _matrix_comparison(records, toolchain)
    required = int(settings["required_combinations"])
    enforced_in = str(settings["enforced_in"])
    if required < 0:
        raise ValueError("matrix identity required combinations must be non-negative")
    if not enforced_in:
        raise ValueError("matrix identity enforcement location must be non-empty")
    return {
        "required_combinations": required,
        "observed_combinations": observed,
        "identical": None if observed < required else identical,
        "enforced_in": enforced_in,
    }


def _migration_summary(
    records: list[dict[str, Any]],
    thresholds: Mapping[str, Any],
    toolchain: Mapping[str, Any],
) -> dict[str, Any]:
    valid = [record for record in records if record["condition"] == "valid"]
    invalid = [record for record in records if record["condition"] == "invalid"]
    property_passes: dict[str, int] = defaultdict(int)
    for record in valid:
        property_name = str(record["case_id"]).rsplit(":", 1)[-1]
        property_passes[property_name] += (
            _outcome(record, "actual_outcome").get("passed") is True
        )
    invalid_passes = sum(
        _outcome(record, "actual_outcome").get("passed") is True for record in invalid
    )
    legacy_invariant = "normalized_output_identical_across_matrix" in thresholds
    semantic_invariant = "semantic_migration_invariant_required" in thresholds
    if legacy_invariant == semantic_invariant:
        raise ValueError("migration protocol must select exactly one invariant")
    invariant_property = (
        "normalized-inspect-parity"
        if legacy_invariant
        else "semantic-migration-invariant"
    )
    invariant_metric = (
        "normalized_inspect_parity_passed"
        if legacy_invariant
        else "semantic_migration_invariant_passed"
    )
    valid_fixtures = {str(record["case_id"]).rsplit(":", 1)[0] for record in valid}
    invalid_fixtures = {str(record["case_id"]).rsplit(":", 1)[0] for record in invalid}
    metrics: dict[str, Any] = {
        "independent_output_parity_passed": property_passes[
            "independent-output-parity"
        ],
        "config_validation_passed": property_passes["config-validation"],
        "force_idempotence_passed": property_passes["force-idempotence"],
        "tree_atomicity_passed": property_passes["tree-atomicity"],
        invariant_metric: property_passes[invariant_property],
        "failure_atomicity_passed": invalid_passes,
        "failure_atomicity_total": len(invalid_fixtures),
        "valid_fixture_count": len(valid_fixtures),
        "property_count": len(property_passes),
        "minimum_property_pass_count": min(property_passes.values(), default=0),
    }
    required = int(thresholds["cases_required_per_property"])
    valid_properties = (
        "independent-output-parity",
        "config-validation",
        "force-idempotence",
        "tree-atomicity",
        invariant_property,
    )
    passed = (
        len(valid_properties) == int(thresholds["property_count"])
        and len(valid_fixtures) == int(thresholds["case_total"])
        and all(property_passes[name] >= required for name in valid_properties)
        and invalid_passes >= int(thresholds["failure_atomicity_required"])
        and len(invalid_fixtures) == int(thresholds["failure_atomicity_total"])
    )
    if legacy_invariant:
        observed, expected, matrix_identical = _matrix_comparison(records, toolchain)
        metrics.update(
            {
                "observed_platform_python_combinations": observed,
                "required_platform_python_combinations": expected,
                "normalized_output_identical_across_matrix": matrix_identical,
            }
        )
        passed = passed and matrix_identical == bool(
            thresholds["normalized_output_identical_across_matrix"]
        )
    else:
        passed = passed and bool(thresholds["semantic_migration_invariant_required"])
    passed_records = sum(
        _outcome(record, "actual_outcome").get("passed") is True for record in records
    )
    return {
        "counts": _counts(len(records), passed_records),
        "thresholds": _scalar_thresholds(thresholds),
        "metrics": metrics,
        "passed": passed,
    }


def _ablations(
    records: list[dict[str, Any]],
    toolchain: Mapping[str, Any],
    benchmark_version: str,
) -> dict[str, Any]:
    manifest = _load_json(benchmark_root() / "mutations" / "manifest.json")
    rule_map_payload = _load_json(benchmark_root() / "principle-rule-map.json")
    gates_payload = _load_json(benchmark_root() / "gates.json")
    if not isinstance(manifest, list) or not isinstance(rule_map_payload, dict):
        raise TypeError("ablation inputs have invalid top-level shapes")
    rule_map = rule_map_payload["rules"]
    gate_rules = {
        rule
        for gate in gates_payload["gates"]
        for rule in gate.get("rule_ids", [])
        if isinstance(rule, str)
    }
    rows = {str(row["mutation_id"]): row for row in manifest}
    must_records = [record for record in records if record["condition"] == "must_block"]
    all_observed_rules = {
        rule for record in records for rule in record["finding_ids"] if rule in rule_map
    }
    killed_total = sum(
        _outcome(record, "actual_outcome").get("killed") is True
        for record in must_records
    )
    presence = {}
    families = {}
    for family in PRINCIPLE_FAMILIES:
        mapped = sorted(rule for rule, owner in rule_map.items() if owner == family)
        gated = sorted(rule for rule in mapped if rule in gate_rules)
        observed = sorted(rule for rule in mapped if rule in all_observed_rules)
        presence[family] = {
            "mapped_rule_count": len(mapped),
            "gate_rule_count": len(gated),
            "observed_rule_count": len(observed),
            "mapped_rules": mapped,
            "observed_rules": observed,
        }
        if not observed:
            continue
        targeted = [
            record
            for record in must_records
            if rule_map.get(
                str(rows[str(record["case_id"])]["expected_rule_id_or_signature"])
            )
            == family
        ]
        targeted_killed = sum(
            _outcome(record, "actual_outcome").get("killed") is True
            for record in targeted
        )
        standalone = 0
        for record in must_records:
            if _outcome(record, "actual_outcome").get("killed") is not True:
                continue
            observed_families = {
                rule_map[rule] for rule in record["finding_ids"] if rule in rule_map
            }
            standalone += observed_families == {family}
        families[family] = {
            "represented_rules": observed,
            "targeted_mutations": len(targeted),
            "targeted_killed": targeted_killed,
            "targeted_recall": (targeted_killed / len(targeted) if targeted else None),
            "standalone_covered_mutations": standalone,
            "standalone_coverage": (
                standalone / len(must_records) if must_records else 0.0
            ),
            "leave_one_out_remaining_killed": killed_total - targeted_killed,
            "leave_one_out_loss": targeted_killed,
            "leave_one_out_loss_rate": (
                targeted_killed / killed_total if killed_total else 0.0
            ),
        }
    return {
        "schema_version": "1",
        "benchmark_version": benchmark_version,
        "repository_commit": toolchain["repository_commit"],
        "population": "must_block mutation rows",
        "must_block_total": len(must_records),
        "must_block_killed": killed_total,
        "definitions": {
            "standalone_coverage": "fraction of must-block rows killed with findings from only this represented family",
            "leave_one_out_loss": "targeted killed rows lost when this family's expected rule is removed",
            "targeted_recall": "killed fraction among must-block rows whose expected signature is a mapped rule in this family",
        },
        "family_presence": presence,
        "computed_families": families,
        "absent_families": [
            family
            for family in PRINCIPLE_FAMILIES
            if not presence[family]["observed_rules"]
        ],
    }


def build_summary(
    results_dir: Path, generated_at: str, protocol_path: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build summary and ablation payloads from a result directory."""

    toolchain = load_toolchain()
    protocol = _load_protocol(protocol_path, toolchain)
    records = {suite: _load_jsonl(results_dir / f"{suite}.jsonl") for suite in SUITES}
    summary_suites = {
        "detection": _detection_summary(records["detection"], protocol["detection"]),
        "evidence": _evidence_summary(records["evidence"], protocol["evidence"]),
        "mutations": _mutation_summary(records["mutations"], protocol["mutations"]),
        "migration": _migration_summary(
            records["migration"], protocol["migration"], toolchain
        ),
    }
    summary: dict[str, Any] = {
        "schema_version": str(protocol["schema_version"]),
        "benchmark_version": str(protocol["benchmark_version"]),
        "generated_at": generated_at,
        "toolchain": {
            "repository_commit": toolchain["repository_commit"],
            "garden_commit": git_commit(),
            "plugin_version": plugin_version(),
            "seed": toolchain["seed"],
            "platform": platform_string(),
            "python_version": python_version_string(),
        },
        "suites": summary_suites,
        "passed": all(suite["passed"] for suite in summary_suites.values()),
    }
    matrix_settings = protocol.get("matrix_identity")
    if matrix_settings is not None:
        if not isinstance(matrix_settings, dict):
            raise TypeError("matrix identity protocol section must be a table")
        summary["matrix_identity"] = _matrix_identity_summary(
            records["migration"], matrix_settings, toolchain
        )
    return summary, _ablations(
        records["mutations"], toolchain, str(protocol["benchmark_version"])
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Write summary.json and ablations.json for existing raw results."""

    parser = argparse.ArgumentParser(description="summarize benchmark results")
    parser.add_argument(
        "--results-dir", type=Path, default=benchmark_root() / "results" / "v1"
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        help="protocol filename or path relative to the benchmarks directory",
    )
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)
    generated_at = args.generated_at or _generated_at()
    summary, ablations = build_summary(
        args.results_dir, generated_at, protocol_path=args.protocol
    )
    args.results_dir.mkdir(parents=True, exist_ok=True)
    (args.results_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.results_dir / "ablations.json").write_text(
        json.dumps(ablations, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "summary "
        + " ".join(
            f"{name}={'pass' if value['passed'] else 'fail'}"
            for name, value in summary["suites"].items()
        )
        + f" overall={'pass' if summary['passed'] else 'fail'}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

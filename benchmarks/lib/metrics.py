"""Pure detection-suite metric functions."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal


Record = Mapping[str, Any]
BinaryField = Literal["production_source", "test"]


@dataclass(frozen=True)
class ConfusionMatrix:
    """Binary classification counts."""

    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int


def _outcome(record: Record, key: str) -> Mapping[str, Any]:
    value = record[key]
    if isinstance(value, str):
        decoded = json.loads(value)
    else:
        decoded = value
    if not isinstance(decoded, Mapping):
        raise TypeError(f"{key} must decode to an object")
    return decoded


def path_error(record: Record) -> bool:
    """Return whether any detection classification differs from ground truth."""

    expected = _outcome(record, "expected_outcome")
    actual = _outcome(record, "actual_outcome")
    return any(
        expected.get(field) != actual.get(field)
        for field in ("production_source", "test", "capability")
    )


def classification_error_rate(records: Iterable[Record]) -> float:
    """Return the fraction of paths with at least one classification error."""

    values = list(records)
    if not values:
        return 0.0
    return sum(path_error(record) for record in values) / len(values)


def absolute_improvement(err_legacy: float, err_configured: float) -> float:
    """Return the absolute error-rate reduction."""

    return err_legacy - err_configured


def relative_error_reduction(err_legacy: float, err_configured: float) -> float:
    """Return error reduction relative to the legacy error rate."""

    if err_legacy == 0.0:
        return 0.0
    return (err_legacy - err_configured) / err_legacy


def binary_confusion(records: Iterable[Record], field: BinaryField) -> ConfusionMatrix:
    """Return a confusion matrix for a binary detection field."""

    if field not in ("production_source", "test"):
        raise ValueError(f"unsupported binary field: {field}")
    true_positive = false_positive = true_negative = false_negative = 0
    for record in records:
        expected = bool(_outcome(record, "expected_outcome").get(field))
        actual = bool(_outcome(record, "actual_outcome").get(field))
        if expected and actual:
            true_positive += 1
        elif not expected and actual:
            false_positive += 1
        elif not expected and not actual:
            true_negative += 1
        else:
            false_negative += 1
    return ConfusionMatrix(
        true_positive,
        false_positive,
        true_negative,
        false_negative,
    )


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def precision(records: Iterable[Record], field: BinaryField) -> float:
    """Return binary precision for a source or test field."""

    counts = binary_confusion(records, field)
    return _ratio(
        counts.true_positive,
        counts.true_positive + counts.false_positive,
    )


def recall(records: Iterable[Record], field: BinaryField) -> float:
    """Return binary recall for a source or test field."""

    counts = binary_confusion(records, field)
    return _ratio(
        counts.true_positive,
        counts.true_positive + counts.false_negative,
    )


def false_positive_rate(records: Iterable[Record], field: BinaryField) -> float:
    """Return the binary false-positive rate for a source or test field."""

    counts = binary_confusion(records, field)
    return _ratio(
        counts.false_positive,
        counts.false_positive + counts.true_negative,
    )


def false_negative_rate(records: Iterable[Record], field: BinaryField) -> float:
    """Return the binary false-negative rate for a source or test field."""

    counts = binary_confusion(records, field)
    return _ratio(
        counts.false_negative,
        counts.false_negative + counts.true_positive,
    )


def capability_exact_match_accuracy(records: Iterable[Record]) -> float:
    """Return exact-match accuracy for the capability string."""

    values = list(records)
    if not values:
        return 0.0
    matches = sum(
        _outcome(record, "expected_outcome").get("capability")
        == _outcome(record, "actual_outcome").get("capability")
        for record in values
    )
    return matches / len(values)


def _fixture_name(record: Record) -> str:
    return str(record["case_id"]).split(":", 1)[0]


def _condition(record: Record) -> str:
    return str(record["condition"])


def _project_type(fixture: str) -> str:
    return fixture.rsplit("-", 1)[0]


def per_fixture_error_rates(records: Iterable[Record]) -> dict[str, dict[str, float]]:
    """Return legacy and configured error rates for every fixture."""

    groups: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for record in records:
        groups[(_fixture_name(record), _condition(record))].append(record)
    result: dict[str, dict[str, float]] = defaultdict(dict)
    for (fixture, condition), values in sorted(groups.items()):
        result[fixture][condition] = classification_error_rate(values)
    return dict(result)


def per_project_type_mean_error_rates(
    records: Iterable[Record],
) -> dict[str, dict[str, float]]:
    """Return mean fixture error rates grouped by project type and condition."""

    fixture_rates = per_fixture_error_rates(records)
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for fixture, conditions in fixture_rates.items():
        for condition, rate in conditions.items():
            grouped[(_project_type(fixture), condition)].append(rate)
    result: dict[str, dict[str, float]] = defaultdict(dict)
    for (project_type, condition), values in sorted(grouped.items()):
        result[project_type][condition] = sum(values) / len(values)
    return dict(result)


def improved_fixture_count(records: Iterable[Record]) -> int:
    """Return how many fixtures have lower configured error than legacy error."""

    rates = per_fixture_error_rates(records)
    return sum(
        conditions.get("configured", 0.0) < conditions.get("legacy", 0.0)
        for conditions in rates.values()
        if "legacy" in conditions and "configured" in conditions
    )


def scan_is_complete(records: Iterable[Record]) -> bool:
    """Return false for empty data or any explicitly incomplete result."""

    values = list(records)
    return bool(values) and all(
        _outcome(record, "actual_outcome").get("scan_complete") is True
        for record in values
    )


def scan_counts_as_pass(records: Iterable[Record], thresholds_passed: bool) -> bool:
    """Return pass only when thresholds pass and the scan is complete."""

    values = list(records)
    return thresholds_passed and scan_is_complete(values)


def aggregate_by_fixture(
    records: Iterable[Record], metric: Callable[[Iterable[Record]], float]
) -> dict[str, float]:
    """Apply a pure record metric independently to each fixture."""

    groups: dict[str, list[Record]] = defaultdict(list)
    for record in records:
        groups[_fixture_name(record)].append(record)
    return {fixture: metric(values) for fixture, values in sorted(groups.items())}

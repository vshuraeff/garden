from __future__ import annotations

import json
import unittest

from metrics import (
    absolute_improvement,
    aggregate_by_fixture,
    binary_confusion,
    capability_exact_match_accuracy,
    classification_error_rate,
    false_negative_rate,
    false_positive_rate,
    improved_fixture_count,
    path_error,
    per_fixture_error_rates,
    per_project_type_mean_error_rates,
    precision,
    recall,
    relative_error_reduction,
    scan_counts_as_pass,
    scan_is_complete,
)


def record(
    case_id: str,
    condition: str,
    expected: tuple[bool, bool, str],
    actual: tuple[bool, bool, str],
    *,
    complete: bool = True,
) -> dict[str, object]:
    def outcome(value: tuple[bool, bool, str], scan_complete: bool) -> str:
        source, test, capability = value
        return json.dumps(
            {
                "capability": capability,
                "production_source": source,
                "scan_complete": scan_complete,
                "test": test,
            },
            sort_keys=True,
        )

    return {
        "case_id": case_id,
        "condition": condition,
        "expected_outcome": outcome(expected, True),
        "actual_outcome": outcome(actual, complete),
    }


class DetectionMetricTests(unittest.TestCase):
    def test_empty_inputs_have_zero_rates_and_never_pass(self) -> None:
        self.assertEqual(0.0, classification_error_rate([]))
        self.assertEqual(0.0, capability_exact_match_accuracy([]))
        self.assertEqual(0.0, precision([], "production_source"))
        self.assertEqual(0.0, recall([], "test"))
        self.assertEqual(0.0, false_positive_rate([], "test"))
        self.assertEqual(0.0, false_negative_rate([], "production_source"))
        self.assertFalse(scan_is_complete([]))
        self.assertFalse(scan_counts_as_pass([], True))

    def test_all_correct_and_all_wrong(self) -> None:
        correct = record(
            "python-service-conventional:a.py",
            "configured",
            (True, False, "a"),
            (True, False, "a"),
        )
        wrong = record(
            "python-service-conventional:b.py",
            "configured",
            (True, False, "a"),
            (False, True, "b"),
        )

        self.assertFalse(path_error(correct))
        self.assertTrue(path_error(wrong))
        self.assertEqual(0.0, classification_error_rate([correct]))
        self.assertEqual(1.0, classification_error_rate([wrong]))
        self.assertEqual(1.0, capability_exact_match_accuracy([correct]))
        self.assertEqual(0.0, capability_exact_match_accuracy([wrong]))

    def test_mixed_binary_metrics(self) -> None:
        records = [
            record(
                "library-conventional:tp",
                "configured",
                (True, False, "a"),
                (True, False, "a"),
            ),
            record(
                "library-conventional:fp",
                "configured",
                (False, False, ""),
                (True, False, ""),
            ),
            record(
                "library-conventional:tn",
                "configured",
                (False, False, ""),
                (False, False, ""),
            ),
            record(
                "library-conventional:fn",
                "configured",
                (True, False, "a"),
                (False, False, "a"),
            ),
        ]

        self.assertEqual(
            (1, 1, 1, 1),
            tuple(binary_confusion(records, "production_source").__dict__.values()),
        )
        self.assertEqual(0.5, precision(records, "production_source"))
        self.assertEqual(0.5, recall(records, "production_source"))
        self.assertEqual(0.5, false_positive_rate(records, "production_source"))
        self.assertEqual(0.5, false_negative_rate(records, "production_source"))
        with self.assertRaises(ValueError):
            binary_confusion(records, "capability")  # type: ignore[arg-type]

    def test_improvement_edge_cases(self) -> None:
        self.assertAlmostEqual(0.2, absolute_improvement(0.3, 0.1))
        self.assertAlmostEqual(2 / 3, relative_error_reduction(0.3, 0.1))
        self.assertEqual(0.0, relative_error_reduction(0.0, 0.0))
        self.assertEqual(0.0, relative_error_reduction(0.0, 0.2))

    def test_fixture_and_project_type_aggregation(self) -> None:
        records = [
            record(
                "python-service-conventional:a",
                "legacy",
                (True, False, "orders"),
                (False, False, "src"),
            ),
            record(
                "python-service-conventional:a",
                "configured",
                (True, False, "orders"),
                (True, False, "orders"),
            ),
            record(
                "python-service-adversarial:a",
                "legacy",
                (True, False, "orders"),
                (True, False, "orders"),
            ),
            record(
                "python-service-adversarial:a",
                "configured",
                (True, False, "orders"),
                (True, False, "orders"),
            ),
        ]

        fixture_rates = per_fixture_error_rates(records)
        self.assertEqual(1.0, fixture_rates["python-service-conventional"]["legacy"])
        self.assertEqual(
            0.0, fixture_rates["python-service-conventional"]["configured"]
        )
        self.assertEqual(1, improved_fixture_count(records))
        means = per_project_type_mean_error_rates(records)
        self.assertEqual(0.5, means["python-service"]["legacy"])
        self.assertEqual(0.0, means["python-service"]["configured"])
        aggregated = aggregate_by_fixture(records, classification_error_rate)
        self.assertEqual(0.5, aggregated["python-service-conventional"])

    def test_incomplete_scan_never_counts_as_pass(self) -> None:
        incomplete = record(
            "monorepo-conventional:a",
            "configured",
            (True, False, "orders"),
            (True, False, "orders"),
            complete=False,
        )
        self.assertFalse(scan_is_complete([incomplete]))
        self.assertFalse(scan_counts_as_pass([incomplete], True))
        self.assertFalse(scan_counts_as_pass([incomplete], False))


if __name__ == "__main__":
    unittest.main()

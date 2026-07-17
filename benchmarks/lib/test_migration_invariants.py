from __future__ import annotations

import unittest

from migration_invariants import evaluate_migration_invariant


def finding(
    rule: str,
    *,
    severity: str = "advisory",
    path: str = "src/example.py",
    message: str = "example finding",
) -> dict[str, str]:
    return {
        "severity": severity,
        "rule": rule,
        "path": path,
        "message": message,
    }


def registry(rule: str, direction: str) -> list[dict[str, str]]:
    return [
        {
            "rule": rule,
            "direction": direction,
            "reason": "test reason",
            "source": "test source",
        }
    ]


class MigrationInvariantTests(unittest.TestCase):
    def test_registered_removal_passes(self) -> None:
        legacy = [finding("R-component-contract")]

        result = evaluate_migration_invariant(
            legacy, [], registry("R-component-contract", "removed-in-configured")
        )

        self.assertTrue(result.passed)
        self.assertEqual((), result.unregistered)

    def test_unregistered_removal_fails(self) -> None:
        result = evaluate_migration_invariant([finding("R-component-contract")], [], [])

        self.assertFalse(result.passed)
        self.assertEqual("removed", result.unregistered[0].direction)
        self.assertEqual("R-component-contract", result.unregistered[0].rule)

    def test_unregistered_new_error_fails(self) -> None:
        result = evaluate_migration_invariant(
            [], [finding("N-CONFIG-INVALID", severity="error")], []
        )

        self.assertFalse(result.passed)
        self.assertEqual("added", result.unregistered[0].direction)
        self.assertEqual("error", result.unregistered[0].severity)

    def test_either_registration_permits_added_removed_and_both(self) -> None:
        old = finding("R-component-contract", path="tests/old_test.py")
        new = finding("R-component-contract", path="src/new.py")
        cases = (
            ([], [new]),
            ([old], []),
            ([old], [new]),
        )

        for legacy, configured in cases:
            with self.subTest(legacy=legacy, configured=configured):
                result = evaluate_migration_invariant(
                    legacy,
                    configured,
                    registry("R-component-contract", "either"),
                )
                self.assertTrue(result.passed)
                self.assertEqual((), result.unregistered)

    def test_unregistered_new_advisory_fails(self) -> None:
        result = evaluate_migration_invariant(
            [], [finding("A-colocated-tests", severity="advisory")], []
        )

        self.assertFalse(result.passed)
        self.assertEqual("advisory", result.unregistered[0].severity)

    def test_empty_registry_is_strict_only_when_findings_differ(self) -> None:
        same = finding("R-component-contract")

        self.assertTrue(evaluate_migration_invariant([same], [same], []).passed)
        self.assertFalse(evaluate_migration_invariant([], [same], []).passed)


if __name__ == "__main__":
    unittest.main()

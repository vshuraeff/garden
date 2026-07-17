"""Pure semantic invariants for legacy-to-configured migration findings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


REGISTRY_DIRECTIONS = {
    "removed-in-configured",
    "added-in-configured",
    "either",
}
REGISTRY_FIELDS = {"rule", "direction", "reason", "source"}
FINDING_FIELDS = ("severity", "rule", "path", "message")


@dataclass(frozen=True, order=True)
class FindingDifference:
    """One unregistered finding-instance difference."""

    direction: str
    severity: str
    rule: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        """Return the original finding shape."""

        return {
            "severity": self.severity,
            "rule": self.rule,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class MigrationInvariantResult:
    """Semantic migration result with exact unregistered differences."""

    unregistered: tuple[FindingDifference, ...]

    @property
    def passed(self) -> bool:
        """Return whether every finding difference is registered."""

        return not self.unregistered


def _registry_directions(
    registry: Sequence[Mapping[str, object]],
) -> dict[str, str]:
    directions = {}
    for index, entry in enumerate(registry):
        if set(entry) != REGISTRY_FIELDS:
            raise ValueError(
                f"registry entry {index} must contain exactly {sorted(REGISTRY_FIELDS)}"
            )
        for field in REGISTRY_FIELDS:
            value = entry[field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"registry entry {index} field {field} must be non-empty"
                )
        rule = str(entry["rule"])
        direction = str(entry["direction"])
        if direction not in REGISTRY_DIRECTIONS:
            raise ValueError(
                f"registry entry {index} direction must be one of "
                f"{sorted(REGISTRY_DIRECTIONS)}"
            )
        if rule in directions:
            raise ValueError(f"registry contains duplicate rule {rule}")
        directions[rule] = direction
    return directions


def validate_intentional_changes(
    registry: Sequence[Mapping[str, object]],
) -> None:
    """Validate the intentional-changes registry shape and values."""

    _registry_directions(registry)


def _finding_key(finding: Mapping[str, object], index: int) -> tuple[str, ...]:
    values = []
    for field in FINDING_FIELDS:
        value = finding.get(field)
        if not isinstance(value, str):
            raise ValueError(f"finding {index} field {field} must be a string")
        values.append(value)
    return tuple(values)


def evaluate_migration_invariant(
    legacy_findings: Sequence[Mapping[str, object]],
    configured_findings: Sequence[Mapping[str, object]],
    registry: Sequence[Mapping[str, object]],
) -> MigrationInvariantResult:
    """Return unregistered finding-instance changes between inspection modes."""

    directions = _registry_directions(registry)
    legacy = {
        _finding_key(finding, index) for index, finding in enumerate(legacy_findings)
    }
    configured = {
        _finding_key(finding, index)
        for index, finding in enumerate(configured_findings)
    }
    unregistered = []
    for direction, differences, permitted in (
        (
            "removed",
            legacy - configured,
            {"removed-in-configured", "either"},
        ),
        (
            "added",
            configured - legacy,
            {"added-in-configured", "either"},
        ),
    ):
        for severity, rule, path, message in differences:
            if directions.get(rule) in permitted:
                continue
            unregistered.append(
                FindingDifference(direction, severity, rule, path, message)
            )
    return MigrationInvariantResult(tuple(sorted(unregistered)))

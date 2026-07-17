"""Pure cross-matrix identity checks for normalized benchmark artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class CellDifference:
    """One artifact difference between a matrix cell and the reference cell."""

    reference_cell: str
    cell: str
    artifact: str
    detail: str


@dataclass(frozen=True)
class MatrixComparisonResult:
    """Cross-matrix identity result with exact missing cells and differences."""

    missing_cells: tuple[str, ...]
    unexpected_cells: tuple[str, ...]
    differences: tuple[CellDifference, ...]

    @property
    def passed(self) -> bool:
        """Return whether the expected cells are present and identical."""

        return not (
            self.missing_cells or self.unexpected_cells or self.differences
        )


def _first_difference(reference: object, candidate: object) -> str:
    if type(reference) is not type(candidate):
        return (
            f"types differ ({type(reference).__name__} != "
            f"{type(candidate).__name__})"
        )
    if isinstance(reference, Mapping) and isinstance(candidate, Mapping):
        reference_keys = set(reference)
        candidate_keys = set(candidate)
        missing = sorted(reference_keys - candidate_keys, key=repr)
        if missing:
            return f"field {missing[0]!r} is missing"
        added = sorted(candidate_keys - reference_keys, key=repr)
        if added:
            return f"field {added[0]!r} is unexpected"
        for key in sorted(reference_keys, key=repr):
            if reference[key] != candidate[key]:
                detail = _first_difference(reference[key], candidate[key])
                return f"field {key!r} differs ({detail})"
    elif (
        isinstance(reference, Sequence)
        and isinstance(candidate, Sequence)
        and not isinstance(reference, (str, bytes, bytearray))
    ):
        if len(reference) != len(candidate):
            return f"item count differs ({len(reference)} != {len(candidate)})"
        for index, (reference_item, candidate_item) in enumerate(
            zip(reference, candidate, strict=True)
        ):
            if reference_item != candidate_item:
                detail = _first_difference(reference_item, candidate_item)
                return f"item {index + 1} differs ({detail})"
    return "values differ"


def _artifact_difference(
    artifact: str, reference: object, candidate: object
) -> str:
    detail = _first_difference(reference, candidate)
    if artifact.endswith(".jsonl") and detail.startswith("item "):
        return "record " + detail.removeprefix("item ")
    return detail


def evaluate_matrix_identity(
    expected_cells: Sequence[str],
    cell_artifacts: Mapping[str, Mapping[str, object]],
) -> MatrixComparisonResult:
    """Compare normalized artifact bundles across the expected matrix cells."""

    expected = tuple(expected_cells)
    if len(set(expected)) != len(expected):
        raise ValueError("expected cells must be unique")

    expected_set = set(expected)
    actual_set = set(cell_artifacts)
    missing_cells = tuple(cell for cell in expected if cell not in actual_set)
    unexpected_cells = tuple(sorted(actual_set - expected_set))
    present_cells = [cell for cell in expected if cell in actual_set]
    differences = []
    if present_cells:
        reference_cell = present_cells[0]
        reference_artifacts = cell_artifacts[reference_cell]
        for cell in present_cells[1:]:
            artifacts = cell_artifacts[cell]
            for artifact in sorted(set(reference_artifacts) | set(artifacts)):
                if artifact not in reference_artifacts:
                    differences.append(
                        CellDifference(
                            reference_cell,
                            cell,
                            artifact,
                            f"missing from reference cell {reference_cell}",
                        )
                    )
                    continue
                if artifact not in artifacts:
                    differences.append(
                        CellDifference(
                            reference_cell,
                            cell,
                            artifact,
                            f"missing from cell {cell}",
                        )
                    )
                    continue
                if reference_artifacts[artifact] != artifacts[artifact]:
                    differences.append(
                        CellDifference(
                            reference_cell,
                            cell,
                            artifact,
                            _artifact_difference(
                                artifact,
                                reference_artifacts[artifact],
                                artifacts[artifact],
                            ),
                        )
                    )

    return MatrixComparisonResult(
        missing_cells,
        unexpected_cells,
        tuple(sorted(differences)),
    )

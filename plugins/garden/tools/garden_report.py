"""Finding definitions and deterministic project report assembly."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    path: str
    message: str


def build_project_report(
    root: Path, active: bool, findings: Iterable[Finding]
) -> dict[str, object]:
    unique = list(
        {
            (item.severity, item.rule, item.path, item.message): item
            for item in findings
        }.values()
    )
    return {
        "active": active,
        "root": str(root),
        "findings": [asdict(item) for item in unique],
        "summary": {
            "errors": sum(item.severity == "error" for item in unique),
            "advisories": sum(item.severity == "advisory" for item in unique),
        },
    }

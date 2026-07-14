"""Pinned adapter for the deterministic GARDEN classifier.

The CLI JSON report exposes findings, activation, and scan completeness, but it
does not expose per-path source, test, or capability classifications. This is
the one pinned internal classifier adapter: it imports the current
``garden_config`` and ``garden_rules`` modules only here, and projects their
configured predicates and legacy test-name heuristic into per-path outcomes.
All gate execution still goes through ``garden_cli.py`` as a subprocess.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from .provenance import repository_root


@dataclass(frozen=True)
class CliResult:
    """Captured result of one GARDEN CLI invocation."""

    exit_code: int
    stdout: bytes
    stderr: bytes
    elapsed_ns: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class Classification:
    """One path's source, test, and capability classification."""

    production_source: bool
    test: bool
    capability: str


def garden_cli_path() -> Path:
    """Resolve the repository-local GARDEN CLI without an absolute constant."""

    return repository_root() / "plugins" / "garden" / "tools" / "garden_cli.py"


def inspect_condition(root: Path) -> CliResult:
    """Run strict project inspection and parse its JSON report."""

    command = [
        "uv",
        "run",
        "--no-project",
        str(garden_cli_path()),
        "inspect",
        "--strict",
        str(root),
    ]
    started = time.perf_counter_ns()
    completed = subprocess.run(command, capture_output=True, check=False)
    elapsed = time.perf_counter_ns() - started
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"garden inspect did not emit JSON for {root}: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"garden inspect emitted a non-object for {root}")
    return CliResult(
        completed.returncode,
        completed.stdout,
        completed.stderr,
        elapsed,
        payload,
    )


def _internal_modules() -> tuple[ModuleType, ModuleType]:
    tools = garden_cli_path().parent
    tools_text = str(tools)
    if tools_text not in sys.path:
        sys.path.insert(0, tools_text)
    return (
        importlib.import_module("garden_config"),
        importlib.import_module("garden_rules"),
    )


def classify_path(root: Path, relative_path: str) -> Classification:
    """Classify one existing path using the pinned plugin implementation."""

    garden_config, garden_rules = _internal_modules()
    relative = Path(relative_path)
    loaded = garden_config.load_config(root)
    if loaded.present:
        if loaded.errors or loaded.config is None:
            raise ValueError(f"cannot classify with invalid config at {root}")
        effective = garden_config.resolve_effective(loaded.config)
        is_test = garden_rules._matches_path_pattern(  # noqa: SLF001
            relative, effective.tests.patterns.value
        )
        is_source = not is_test and garden_rules._is_configured_source_file(  # noqa: SLF001
            relative, effective
        )
        if is_test:
            capability = garden_rules._configured_test_identity(  # noqa: SLF001
                relative, effective
            )
            return Classification(False, True, capability or "")
        if not is_source:
            return Classification(False, False, "")
        resolution = garden_config.resolve_capability(relative.as_posix(), effective)
        capability = (
            resolution.capability
            if resolution.status == "capability"
            else "shared"
            if resolution.status == "shared"
            else ""
        )
        return Classification(True, False, capability or "")

    candidate = (
        len(relative.parts) >= 2 and garden_rules._is_source_file(relative)  # noqa: SLF001
    )
    name = relative.name.lower()
    is_test = candidate and ("test" in name or "spec" in name)
    capability = relative.parts[0] if candidate else ""
    return Classification(candidate and not is_test, is_test, capability)


def scan_complete(result: CliResult) -> bool:
    """Return whether inspection was active and avoided bounded-scan errors."""

    findings = result.payload.get("findings", [])
    return result.payload.get("active") is True and not any(
        isinstance(finding, dict) and finding.get("rule") == "D-project-scan-limit"
        for finding in findings
    )


def finding_ids_for_path(result: CliResult, relative_path: str) -> list[str]:
    """Return sorted finding IDs attributed to a path or incomplete scan."""

    values = set()
    for finding in result.payload.get("findings", []):
        if not isinstance(finding, dict):
            continue
        rule = finding.get("rule")
        path = finding.get("path")
        if isinstance(rule, str) and (
            path == relative_path or rule == "D-project-scan-limit"
        ):
            values.add(rule)
    return sorted(values)

"""One-walk project index: classifies every file under configured scan roots."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from config_schema import EffectiveConfig
import garden_rules
import garden_scanner
from garden_scanner import ScanLimitExceeded


@dataclass(frozen=True)
class ProjectIndex:
    """Deterministic classification results from one bounded project walk."""

    root: Path
    complete: bool
    scan_errors: tuple[str, ...]
    exceeded_budget: str | None
    missing_roots: tuple[str, ...]
    source_files: tuple[Path, ...]
    test_files: tuple[Path, ...]
    source_by_capability: Mapping[str, tuple[Path, ...]]
    tests_by_capability: Mapping[str, tuple[Path, ...]]
    contract_artifacts: tuple[Path, ...]
    unknown_paths: tuple[Path, ...]


def build_project_index(root: Path, effective: EffectiveConfig | None) -> ProjectIndex:
    """Build a deterministic project index from exactly one bounded walk."""

    resolved = root.resolve()
    complete = True
    scan_errors: list[str] = []
    exceeded_budget: str | None = None
    missing_roots: list[str] = []
    source_files: list[Path] = []
    test_files: list[Path] = []
    source_by_capability: dict[str, list[Path]] = {}
    tests_by_capability: dict[str, list[Path]] = {}
    contract_artifacts: list[Path] = []
    unknown_paths: list[Path] = []

    contract_names = (
        {"CONTRACT.md"}
        if effective is None
        else set(effective.contracts.accepted_names.value)
    )

    try:
        if effective is None:
            paths = garden_scanner._walk_files(resolved)
        else:
            paths = garden_scanner._walk_files(
                resolved,
                roots=effective.scan.roots.value,
                exclude=effective.scan.exclude.value,
                on_missing_root=missing_roots.append,
            )
        for path in paths:
            relative = path.relative_to(resolved)
            if path.name in contract_names:
                contract_artifacts.append(path)
                continue

            if effective is not None and garden_rules._matches_path_pattern(
                relative, effective.tests.patterns.value
            ):
                test_files.append(path)
                identity = garden_rules._configured_test_identity(relative, effective)
                if identity is not None:
                    tests_by_capability.setdefault(identity, []).append(path)
                continue

            if effective is None:
                is_source = garden_rules._is_source_file(relative)
                # root-level legacy sources are indexed but have no capability identity.
                identity = relative.parts[0] if len(relative.parts) >= 2 else None
            else:
                is_source = garden_rules._is_configured_source_file(relative, effective)
                identity = garden_rules._capability_identity(
                    relative.as_posix(), effective
                )

            if is_source:
                source_files.append(path)
                if identity is not None:
                    source_by_capability.setdefault(identity, []).append(path)
            else:
                unknown_paths.append(path)
    except ScanLimitExceeded as error:
        complete = False
        exceeded_budget = error.budget
        scan_errors.append(str(error))
    except OSError as error:
        complete = False
        scan_errors.append(str(error))

    def path_key(path: Path) -> str:
        return path.as_posix()

    frozen_sources = MappingProxyType(
        {
            identity: tuple(sorted(paths, key=path_key))
            for identity, paths in sorted(source_by_capability.items())
        }
    )
    frozen_tests = MappingProxyType(
        {
            identity: tuple(sorted(paths, key=path_key))
            for identity, paths in sorted(tests_by_capability.items())
        }
    )
    return ProjectIndex(
        root=resolved,
        complete=complete,
        scan_errors=tuple(scan_errors),
        exceeded_budget=exceeded_budget,
        missing_roots=tuple(sorted(missing_roots)),
        source_files=tuple(sorted(source_files, key=path_key)),
        test_files=tuple(sorted(test_files, key=path_key)),
        source_by_capability=frozen_sources,
        tests_by_capability=frozen_tests,
        contract_artifacts=tuple(sorted(contract_artifacts, key=path_key)),
        unknown_paths=tuple(sorted(unknown_paths, key=path_key)),
    )

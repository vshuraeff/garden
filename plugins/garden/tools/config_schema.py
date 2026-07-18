"""Pure types and validation for GARDEN project configuration schemas."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Callable, Generic, TypeVar


SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = (1, 2)
MAX_PATTERNS = 200
MAX_PATTERN_LENGTH = 4096
PROJECT_TYPES = ("service", "library", "cli", "monorepo", "infra", "other")
BOUNDARY_KINDS = (
    "public-api",
    "external-integration",
    "independently-deployed",
    "persisted-schema",
    "trust-boundary",
    "internal-versioned",
    "private",
)
CAPABILITY_STRATEGIES = ("none", "explicit", "children", "markers")
TEST_ASSOCIATIONS = ("same-capability", "test-roots")
VERSIONING_POLICIES = ("none", "semver", "calendar", "schema-specific", "custom")
# this list is intentionally closed and extended only via a code change.
EVIDENCE_CATEGORIES = (
    "contract-tests",
    "compatibility-tests",
    "rollback-plan",
    "observability",
    "migration-plan",
    "security-review",
)
ORIGINS = ("default", "file")
T = TypeVar("T")


@dataclass(frozen=True)
class ConfigError:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass(frozen=True)
class ContextFilesConfig:
    any_of: tuple[str, ...] | None = None
    all_of: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ProjectConfig:
    type: str | None = None
    context_files: ContextFilesConfig | None = None


@dataclass(frozen=True)
class ScanConfig:
    roots: tuple[str, ...] | None = None
    include: tuple[str, ...] | None = None
    exclude: tuple[str, ...] | None = None


@dataclass(frozen=True)
class CapabilitiesConfig:
    strategy: str | None = None
    roots: tuple[str, ...] | None = None
    depth: int | None = None
    map: tuple[tuple[str, str], ...] | None = None
    shared_roots: tuple[str, ...] | None = None


@dataclass(frozen=True)
class TestsConfig:
    patterns: tuple[str, ...] | None = None
    association: str | None = None
    test_roots: tuple[tuple[str, str], ...] | None = None


@dataclass(frozen=True)
class ContractsConfig:
    required_for: tuple[str, ...] | None = None
    accepted_names: tuple[str, ...] | None = None


@dataclass(frozen=True)
class BoundariesConfig:
    public: tuple[str, ...] | None = None


@dataclass(frozen=True)
class BoundaryConfig:
    path: str | None = None
    kind: str | None = None
    owner: str | None = None
    versioning: str | None = None
    contracts: tuple[str, ...] | None = None
    required_evidence: tuple[str, ...] | None = None


@dataclass(frozen=True)
class NamingConfig:
    registry: str | None = None
    required: bool | None = None


@dataclass(frozen=True)
class DocumentationConfig:
    root_context_required: bool | None = None
    max_context_lines: int | None = None


@dataclass(frozen=True)
class ExceptionConfig:
    rule_id: str | None = None
    paths: tuple[str, ...] | None = None
    reason: str | None = None
    owner: str | None = None
    review_after: str | None = None


@dataclass(frozen=True)
class GardenConfig:
    schema_version: int | None = None
    project: ProjectConfig | None = None
    scan: ScanConfig | None = None
    capabilities: CapabilitiesConfig | None = None
    tests: TestsConfig | None = None
    contracts: ContractsConfig | None = None
    boundaries: BoundariesConfig | None = None
    boundary_entries: tuple[BoundaryConfig, ...] | None = None
    naming: NamingConfig | None = None
    documentation: DocumentationConfig | None = None
    exceptions: tuple[ExceptionConfig, ...] | None = None


@dataclass(frozen=True)
class ResolvedValue(Generic[T]):
    value: T
    origin: str

    def __post_init__(self) -> None:
        if self.origin not in ORIGINS:
            raise ValueError(f"unknown config origin: {self.origin}")


@dataclass(frozen=True)
class EffectiveContextFilesConfig:
    any_of: ResolvedValue[tuple[str, ...]]
    all_of: ResolvedValue[tuple[str, ...]]


@dataclass(frozen=True)
class EffectiveProjectConfig:
    type: ResolvedValue[str]
    context_files: EffectiveContextFilesConfig


@dataclass(frozen=True)
class EffectiveScanConfig:
    roots: ResolvedValue[tuple[str, ...]]
    include: ResolvedValue[tuple[str, ...]]
    exclude: ResolvedValue[tuple[str, ...]]


@dataclass(frozen=True)
class EffectiveCapabilitiesConfig:
    strategy: ResolvedValue[str]
    roots: ResolvedValue[tuple[str, ...]]
    depth: ResolvedValue[int]
    map: ResolvedValue[tuple[tuple[str, str], ...]]
    shared_roots: ResolvedValue[tuple[str, ...]]


@dataclass(frozen=True)
class EffectiveTestsConfig:
    patterns: ResolvedValue[tuple[str, ...]]
    association: ResolvedValue[str]
    test_roots: ResolvedValue[tuple[tuple[str, str], ...]]


@dataclass(frozen=True)
class EffectiveContractsConfig:
    required_for: ResolvedValue[tuple[str, ...]]
    accepted_names: ResolvedValue[tuple[str, ...]]


@dataclass(frozen=True)
class EffectiveBoundariesConfig:
    public: ResolvedValue[tuple[str, ...]]


@dataclass(frozen=True)
class EffectiveBoundaryConfig:
    path: ResolvedValue[str]
    kind: ResolvedValue[str]
    owner: ResolvedValue[str]
    versioning: ResolvedValue[str]
    contracts: ResolvedValue[tuple[str, ...]]
    required_evidence: ResolvedValue[tuple[str, ...]]


@dataclass(frozen=True)
class EffectiveNamingConfig:
    registry: ResolvedValue[str]
    required: ResolvedValue[bool]


@dataclass(frozen=True)
class EffectiveDocumentationConfig:
    root_context_required: ResolvedValue[bool]
    max_context_lines: ResolvedValue[int]


@dataclass(frozen=True)
class EffectiveExceptionConfig:
    rule_id: ResolvedValue[str]
    paths: ResolvedValue[tuple[str, ...]]
    reason: ResolvedValue[str]
    owner: ResolvedValue[str]
    review_after: ResolvedValue[str]


@dataclass(frozen=True)
class EffectiveConfig:
    schema_version: ResolvedValue[int]
    project: EffectiveProjectConfig
    scan: EffectiveScanConfig
    capabilities: EffectiveCapabilitiesConfig
    tests: EffectiveTestsConfig
    contracts: EffectiveContractsConfig
    boundaries: EffectiveBoundariesConfig
    boundary_entries: ResolvedValue[tuple[EffectiveBoundaryConfig, ...]]
    naming: EffectiveNamingConfig
    documentation: EffectiveDocumentationConfig
    exceptions: ResolvedValue[tuple[EffectiveExceptionConfig, ...]]


@dataclass(frozen=True)
class ValidationResult:
    config: GardenConfig | None
    errors: tuple[ConfigError, ...]


class _Validator:
    def __init__(self) -> None:
        self.errors: list[ConfigError] = []

    def error(self, path: str, message: str) -> None:
        self.errors.append(ConfigError(path, message))

    def table(self, value: object, path: str) -> dict[str, object] | None:
        if type(value) is not dict:
            self.error(path, "expected table")
            return None
        return value

    def known_keys(
        self, value: dict[str, object], path: str, keys: frozenset[str]
    ) -> None:
        for key in value:
            if key not in keys:
                self.error(_join(path, key), "unknown key")

    def string(self, value: object, path: str) -> str | None:
        if type(value) is not str:
            self.error(path, "expected string")
            return None
        if not value:
            self.error(path, "must not be empty")
            return None
        return value

    def boolean(self, value: object, path: str) -> bool | None:
        if type(value) is not bool:
            self.error(path, "expected boolean")
            return None
        return value

    def integer(self, value: object, path: str, *, minimum: int = 1) -> int | None:
        if type(value) is not int:
            self.error(path, "expected integer")
            return None
        if value < minimum:
            self.error(path, f"expected integer >= {minimum}")
            return None
        return value

    def choice(self, value: object, path: str, choices: tuple[str, ...]) -> str | None:
        parsed = self.string(value, path)
        if parsed is not None and parsed not in choices:
            self.error(path, f"expected one of {', '.join(choices)}")
            return None
        return parsed

    def string_list(
        self,
        value: object,
        path: str,
        item_validator: Callable[[str, str], str | None] | None = None,
        *,
        maximum: int | None = None,
    ) -> tuple[str, ...] | None:
        if type(value) is not list:
            self.error(path, "expected array of strings")
            return None
        if maximum is not None and len(value) > maximum:
            self.error(path, f"must contain at most {maximum} entries")
        parsed: list[str] = []
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"
            text = self.string(item, item_path)
            if text is None:
                continue
            normalized = item_validator(text, item_path) if item_validator else text
            if normalized is not None:
                parsed.append(normalized)
        return tuple(parsed)

    def string_map(
        self,
        value: object,
        path: str,
        *,
        key_validator: Callable[[str, str], str | None] | None = None,
        value_validator: Callable[[str, str], str | None] | None = None,
    ) -> tuple[tuple[str, str], ...] | None:
        table = self.table(value, path)
        if table is None:
            return None
        parsed: list[tuple[str, str]] = []
        seen: set[str] = set()
        for key, item in sorted(table.items()):
            item_path = _join(path, key)
            parsed_key = self.string(key, item_path)
            normalized_key = (
                key_validator(parsed_key, item_path)
                if parsed_key is not None and key_validator
                else parsed_key
            )
            text = self.string(item, item_path)
            normalized_value = (
                value_validator(text, item_path)
                if text is not None and value_validator
                else text
            )
            if normalized_key is None or normalized_value is None:
                continue
            if normalized_key in seen:
                self.error(item_path, "duplicates another normalized path")
                continue
            seen.add(normalized_key)
            parsed.append((normalized_key, normalized_value))
        return tuple(parsed)


def _join(parent: str, child: str) -> str:
    return f"{parent}.{child}" if parent else child


def _normalize_relative(value: str, path: str, errors: list[ConfigError]) -> str | None:
    normalized = value.replace("\\", "/")
    if normalized.startswith(("/", "//")) or value.startswith("\\\\"):
        errors.append(ConfigError(path, "absolute and UNC paths are not allowed"))
        return None
    if re.match(r"^[A-Za-z]:", normalized):
        errors.append(ConfigError(path, "drive-letter paths are not allowed"))
        return None
    parts = normalized.split("/")
    if ".." in parts:
        errors.append(ConfigError(path, "parent path segments are not allowed"))
        return None
    return PurePosixPath(normalized).as_posix()


def _path_validator(validator: _Validator) -> Callable[[str, str], str | None]:
    def validate(value: str, path: str) -> str | None:
        return _normalize_relative(value, path, validator.errors)

    return validate


def _glob_validator(validator: _Validator) -> Callable[[str, str], str | None]:
    def validate(value: str, path: str) -> str | None:
        if len(value) > MAX_PATTERN_LENGTH:
            validator.error(path, f"must be at most {MAX_PATTERN_LENGTH} characters")
            return None
        normalized = _normalize_relative(value, path, validator.errors)
        if normalized is None:
            return None
        parts = normalized.split("/")
        if any(left == right == "**" for left, right in zip(parts, parts[1:])):
            validator.error(path, "repeated adjacent ** segments are not allowed")
            return None
        return normalized

    return validate


def _parse_context_files(
    validator: _Validator, value: object, path: str
) -> ContextFilesConfig | None:
    table = validator.table(value, path)
    if table is None:
        return None
    validator.known_keys(table, path, frozenset({"any_of", "all_of"}))
    path_item = _path_validator(validator)
    return ContextFilesConfig(
        any_of=(
            validator.string_list(
                table["any_of"], f"{path}.any_of", path_item, maximum=MAX_PATTERNS
            )
            if "any_of" in table
            else None
        ),
        all_of=(
            validator.string_list(
                table["all_of"], f"{path}.all_of", path_item, maximum=MAX_PATTERNS
            )
            if "all_of" in table
            else None
        ),
    )


def _parse_project(
    validator: _Validator, value: object, path: str
) -> ProjectConfig | None:
    table = validator.table(value, path)
    if table is None:
        return None
    validator.known_keys(table, path, frozenset({"type", "context_files"}))
    return ProjectConfig(
        type=(
            validator.choice(table["type"], f"{path}.type", PROJECT_TYPES)
            if "type" in table
            else None
        ),
        context_files=(
            _parse_context_files(
                validator, table["context_files"], f"{path}.context_files"
            )
            if "context_files" in table
            else None
        ),
    )


def _parse_scan(validator: _Validator, value: object, path: str) -> ScanConfig | None:
    table = validator.table(value, path)
    if table is None:
        return None
    validator.known_keys(table, path, frozenset({"roots", "include", "exclude"}))
    path_item = _path_validator(validator)
    glob_item = _glob_validator(validator)
    return ScanConfig(
        roots=(
            validator.string_list(table["roots"], f"{path}.roots", path_item)
            if "roots" in table
            else None
        ),
        include=(
            validator.string_list(
                table["include"],
                f"{path}.include",
                glob_item,
                maximum=MAX_PATTERNS,
            )
            if "include" in table
            else None
        ),
        exclude=(
            validator.string_list(
                table["exclude"],
                f"{path}.exclude",
                glob_item,
                maximum=MAX_PATTERNS,
            )
            if "exclude" in table
            else None
        ),
    )


def _parse_capabilities(
    validator: _Validator, value: object, path: str
) -> CapabilitiesConfig | None:
    table = validator.table(value, path)
    if table is None:
        return None
    validator.known_keys(
        table,
        path,
        frozenset({"strategy", "roots", "depth", "map", "shared_roots"}),
    )
    path_item = _path_validator(validator)
    return CapabilitiesConfig(
        strategy=(
            validator.choice(
                table["strategy"], f"{path}.strategy", CAPABILITY_STRATEGIES
            )
            if "strategy" in table
            else None
        ),
        roots=(
            validator.string_list(table["roots"], f"{path}.roots", path_item)
            if "roots" in table
            else None
        ),
        depth=(
            validator.integer(table["depth"], f"{path}.depth")
            if "depth" in table
            else None
        ),
        map=(
            validator.string_map(table["map"], f"{path}.map", key_validator=path_item)
            if "map" in table
            else None
        ),
        shared_roots=(
            validator.string_list(
                table["shared_roots"], f"{path}.shared_roots", path_item
            )
            if "shared_roots" in table
            else None
        ),
    )


def _parse_tests(validator: _Validator, value: object, path: str) -> TestsConfig | None:
    table = validator.table(value, path)
    if table is None:
        return None
    validator.known_keys(
        table, path, frozenset({"patterns", "association", "test_roots"})
    )
    path_item = _path_validator(validator)
    return TestsConfig(
        patterns=(
            validator.string_list(
                table["patterns"],
                f"{path}.patterns",
                _glob_validator(validator),
                maximum=MAX_PATTERNS,
            )
            if "patterns" in table
            else None
        ),
        association=(
            validator.choice(
                table["association"], f"{path}.association", TEST_ASSOCIATIONS
            )
            if "association" in table
            else None
        ),
        test_roots=(
            validator.string_map(
                table["test_roots"],
                f"{path}.test_roots",
                key_validator=path_item,
                value_validator=path_item,
            )
            if "test_roots" in table
            else None
        ),
    )


def _parse_contracts(
    validator: _Validator, value: object, path: str
) -> ContractsConfig | None:
    table = validator.table(value, path)
    if table is None:
        return None
    validator.known_keys(table, path, frozenset({"required_for", "accepted_names"}))
    return ContractsConfig(
        required_for=(
            validator.string_list(table["required_for"], f"{path}.required_for")
            if "required_for" in table
            else None
        ),
        accepted_names=(
            validator.string_list(table["accepted_names"], f"{path}.accepted_names")
            if "accepted_names" in table
            else None
        ),
    )


def _parse_boundaries(
    validator: _Validator, value: object, path: str
) -> BoundariesConfig | None:
    table = validator.table(value, path)
    if table is None:
        return None
    validator.known_keys(table, path, frozenset({"public"}))
    return BoundariesConfig(
        public=(
            validator.string_list(
                table["public"], f"{path}.public", _path_validator(validator)
            )
            if "public" in table
            else None
        )
    )


def _parse_boundary_v2(
    validator: _Validator, value: object, path: str
) -> BoundaryConfig | None:
    table = validator.table(value, path)
    if table is None:
        return None
    validator.known_keys(
        table,
        path,
        frozenset(
            {"contracts", "kind", "owner", "path", "required_evidence", "versioning"}
        ),
    )

    boundary_path = None
    if "path" not in table:
        validator.error(f"{path}.path", "required key is missing")
    else:
        raw_path = validator.string(table["path"], f"{path}.path")
        if raw_path is not None:
            boundary_path = _path_validator(validator)(raw_path, f"{path}.path")

    kind = None
    if "kind" not in table:
        validator.error(f"{path}.kind", "required key is missing")
    else:
        kind = validator.choice(table["kind"], f"{path}.kind", BOUNDARY_KINDS)

    owner = None
    if "owner" in table:
        owner = validator.string(table["owner"], f"{path}.owner")
    elif kind is not None and kind != "private":
        validator.error(f"{path}.owner", "required key is missing")

    versioning = (
        validator.choice(table["versioning"], f"{path}.versioning", VERSIONING_POLICIES)
        if "versioning" in table
        else None
    )
    contracts = (
        validator.string_list(
            table["contracts"], f"{path}.contracts", _path_validator(validator)
        )
        if "contracts" in table
        else None
    )

    def evidence_category(value: str, item_path: str) -> str | None:
        return validator.choice(value, item_path, EVIDENCE_CATEGORIES)

    required_evidence = (
        validator.string_list(
            table["required_evidence"],
            f"{path}.required_evidence",
            evidence_category,
        )
        if "required_evidence" in table
        else None
    )
    return BoundaryConfig(
        path=boundary_path,
        kind=kind,
        owner=owner,
        versioning=versioning,
        contracts=contracts,
        required_evidence=required_evidence,
    )


def _parse_naming(
    validator: _Validator, value: object, path: str
) -> NamingConfig | None:
    table = validator.table(value, path)
    if table is None:
        return None
    validator.known_keys(table, path, frozenset({"registry", "required"}))
    return NamingConfig(
        registry=(
            _path_validator(validator)(table["registry"], f"{path}.registry")
            if "registry" in table
            and validator.string(table["registry"], f"{path}.registry") is not None
            else None
        ),
        required=(
            validator.boolean(table["required"], f"{path}.required")
            if "required" in table
            else None
        ),
    )


def _parse_documentation(
    validator: _Validator, value: object, path: str
) -> DocumentationConfig | None:
    table = validator.table(value, path)
    if table is None:
        return None
    validator.known_keys(
        table, path, frozenset({"root_context_required", "max_context_lines"})
    )
    return DocumentationConfig(
        root_context_required=(
            validator.boolean(
                table["root_context_required"], f"{path}.root_context_required"
            )
            if "root_context_required" in table
            else None
        ),
        max_context_lines=(
            validator.integer(table["max_context_lines"], f"{path}.max_context_lines")
            if "max_context_lines" in table
            else None
        ),
    )


def _parse_exception(
    validator: _Validator, value: object, path: str
) -> ExceptionConfig | None:
    table = validator.table(value, path)
    if table is None:
        return None
    validator.known_keys(
        table,
        path,
        frozenset({"rule_id", "paths", "reason", "owner", "review_after"}),
    )
    return ExceptionConfig(
        rule_id=(
            validator.string(table["rule_id"], f"{path}.rule_id")
            if "rule_id" in table
            else None
        ),
        paths=(
            validator.string_list(
                table["paths"],
                f"{path}.paths",
                _glob_validator(validator),
                maximum=MAX_PATTERNS,
            )
            if "paths" in table
            else None
        ),
        reason=(
            validator.string(table["reason"], f"{path}.reason")
            if "reason" in table
            else None
        ),
        owner=(
            validator.string(table["owner"], f"{path}.owner")
            if "owner" in table
            else None
        ),
        review_after=(
            validator.string(table["review_after"], f"{path}.review_after")
            if "review_after" in table
            else None
        ),
    )


def validate_config(value: object) -> ValidationResult:
    """Validate a parsed TOML value and return every schema error."""

    validator = _Validator()
    table = validator.table(value, "config")
    if table is None:
        return ValidationResult(None, tuple(validator.errors))
    validator.known_keys(
        table,
        "",
        frozenset(
            {
                "schema_version",
                "project",
                "scan",
                "capabilities",
                "tests",
                "contracts",
                "boundaries",
                "naming",
                "documentation",
                "exceptions",
            }
        ),
    )

    schema_version = None
    effective_schema_version = SCHEMA_VERSION
    if "schema_version" in table:
        schema_version = validator.integer(table["schema_version"], "schema_version")
        if schema_version is not None:
            if schema_version in SUPPORTED_SCHEMA_VERSIONS:
                effective_schema_version = schema_version
            else:
                supported = ", ".join(
                    str(version) for version in SUPPORTED_SCHEMA_VERSIONS
                )
                validator.error("schema_version", f"expected one of {supported}")

    exceptions = None
    if "exceptions" in table:
        raw_exceptions = table["exceptions"]
        if type(raw_exceptions) is not list:
            validator.error("exceptions", "expected array of tables")
        else:
            parsed_exceptions = []
            for index, item in enumerate(raw_exceptions):
                parsed = _parse_exception(validator, item, f"exceptions[{index}]")
                if parsed is not None:
                    parsed_exceptions.append(parsed)
            exceptions = tuple(parsed_exceptions)

    project = (
        _parse_project(validator, table["project"], "project")
        if "project" in table
        else None
    )
    scan = _parse_scan(validator, table["scan"], "scan") if "scan" in table else None
    capabilities = (
        _parse_capabilities(validator, table["capabilities"], "capabilities")
        if "capabilities" in table
        else None
    )
    tests = (
        _parse_tests(validator, table["tests"], "tests") if "tests" in table else None
    )
    contracts = (
        _parse_contracts(validator, table["contracts"], "contracts")
        if "contracts" in table
        else None
    )

    boundaries = None
    boundary_entries = None
    if "boundaries" in table:
        raw_boundaries = table["boundaries"]
        if effective_schema_version == 2:
            if type(raw_boundaries) is not list:
                message = "expected array of tables"
                if type(raw_boundaries) is dict:
                    message = (
                        "schema v2 uses [[boundaries]] array of tables, not a "
                        "[boundaries] table"
                    )
                validator.error("boundaries", message)
            else:
                parsed_boundary_entries = []
                seen_boundary_paths: set[str] = set()
                for index, item in enumerate(raw_boundaries):
                    path = f"boundaries[{index}]"
                    parsed = _parse_boundary_v2(validator, item, path)
                    if parsed is None:
                        continue
                    if parsed.kind == "private":
                        if parsed.versioning not in (None, "none"):
                            validator.error(
                                f"{path}.versioning",
                                "private boundaries must not declare a versioning "
                                "policy other than none",
                            )
                        if parsed.contracts:
                            validator.error(
                                f"{path}.contracts",
                                "private boundaries must not declare contracts",
                            )
                        if parsed.required_evidence:
                            validator.error(
                                f"{path}.required_evidence",
                                "private boundaries must not declare required evidence",
                            )
                    elif parsed.kind == "internal-versioned" and (
                        parsed.versioning == "none"
                        or (parsed.versioning is None and "versioning" not in item)
                    ):
                        validator.error(
                            f"{path}.versioning",
                            "internal-versioned boundaries require a non-none "
                            "versioning policy",
                        )
                    if parsed.path is not None:
                        if parsed.path in seen_boundary_paths:
                            validator.error(
                                f"{path}.path", "duplicates another normalized path"
                            )
                        else:
                            seen_boundary_paths.add(parsed.path)
                    parsed_boundary_entries.append(parsed)
                boundary_entries = tuple(parsed_boundary_entries)
        elif type(raw_boundaries) is list:
            validator.error(
                "boundaries",
                "schema v1 uses a [boundaries] table with a 'public' key",
            )
        else:
            boundaries = _parse_boundaries(validator, raw_boundaries, "boundaries")

    naming = (
        _parse_naming(validator, table["naming"], "naming")
        if "naming" in table
        else None
    )
    documentation = (
        _parse_documentation(validator, table["documentation"], "documentation")
        if "documentation" in table
        else None
    )
    config = GardenConfig(
        schema_version=schema_version,
        project=project,
        scan=scan,
        capabilities=capabilities,
        tests=tests,
        contracts=contracts,
        boundaries=boundaries,
        boundary_entries=boundary_entries,
        naming=naming,
        documentation=documentation,
        exceptions=exceptions,
    )
    if validator.errors:
        return ValidationResult(None, tuple(validator.errors))
    return ValidationResult(config, ())

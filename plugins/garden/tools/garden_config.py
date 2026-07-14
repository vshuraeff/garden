"""Load, resolve, render, and write GARDEN project configuration."""

from __future__ import annotations

import json
import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, TypeVar

from config_schema import (
    BoundariesConfig,
    CapabilitiesConfig,
    ConfigError,
    ContextFilesConfig,
    ContractsConfig,
    DocumentationConfig,
    EffectiveBoundariesConfig,
    EffectiveCapabilitiesConfig,
    EffectiveConfig,
    EffectiveContextFilesConfig,
    EffectiveContractsConfig,
    EffectiveDocumentationConfig,
    EffectiveExceptionConfig,
    EffectiveNamingConfig,
    EffectiveProjectConfig,
    EffectiveScanConfig,
    EffectiveTestsConfig,
    GardenConfig,
    NamingConfig,
    ProjectConfig,
    ResolvedValue,
    SCHEMA_VERSION,
    ScanConfig,
    TestsConfig,
    validate_config,
)
from garden_paths import is_within


CONFIG_NAME = ".garden.toml"
DEFAULT_SCAN_INCLUDE = ("**/*.py", "**/*.ts")
DEFAULT_SCAN_EXCLUDE = ("**/node_modules/**", "**/dist/**")
DEFAULT_TEST_PATTERNS = ("**/test_*.py", "tests/**")
T = TypeVar("T")


@dataclass(frozen=True)
class ConfigResult:
    root: Path
    path: Path
    present: bool
    config: GardenConfig | None
    errors: tuple[ConfigError, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class CapabilityResolution:
    status: str
    capability: str | None = None
    tag: str | None = None


@dataclass(frozen=True)
class TestAssociationResolution:
    status: str
    source_prefix: str | None = None


@dataclass(frozen=True)
class DetectedStack:
    markers: tuple[str, ...]
    project_type: str
    roots: tuple[str, ...]
    include: tuple[str, ...]
    test_patterns: tuple[str, ...]


class ConfigWriteError(RuntimeError):
    pass


def _resolved(value: T | None, default: T) -> ResolvedValue[T]:
    if value is None:
        return ResolvedValue(default, "default")
    return ResolvedValue(value, "file")


def resolve_effective(config: GardenConfig | None) -> EffectiveConfig:
    """Resolve every omitted schema value and retain its origin."""

    raw = config or GardenConfig()
    project = raw.project or ProjectConfig()
    context_files = project.context_files or ContextFilesConfig()
    scan = raw.scan or ScanConfig()
    capabilities = raw.capabilities or CapabilitiesConfig()
    tests = raw.tests or TestsConfig()
    contracts = raw.contracts or ContractsConfig()
    boundaries = raw.boundaries or BoundariesConfig()
    naming = raw.naming or NamingConfig()
    documentation = raw.documentation or DocumentationConfig()

    raw_exceptions = raw.exceptions or ()
    effective_exceptions = tuple(
        EffectiveExceptionConfig(
            rule_id=_resolved(item.rule_id, ""),
            paths=_resolved(item.paths, ()),
            reason=_resolved(item.reason, ""),
            owner=_resolved(item.owner, ""),
            review_after=_resolved(item.review_after, ""),
        )
        for item in raw_exceptions
    )
    return EffectiveConfig(
        schema_version=_resolved(raw.schema_version, SCHEMA_VERSION),
        project=EffectiveProjectConfig(
            type=_resolved(project.type, "other"),
            context_files=EffectiveContextFilesConfig(
                any_of=_resolved(context_files.any_of, ("CONTEXT.md",)),
                all_of=_resolved(context_files.all_of, ()),
            ),
        ),
        scan=EffectiveScanConfig(
            roots=_resolved(scan.roots, (".",)),
            include=_resolved(scan.include, DEFAULT_SCAN_INCLUDE),
            exclude=_resolved(scan.exclude, DEFAULT_SCAN_EXCLUDE),
        ),
        capabilities=EffectiveCapabilitiesConfig(
            strategy=_resolved(capabilities.strategy, "children"),
            roots=_resolved(capabilities.roots, (".",)),
            depth=_resolved(capabilities.depth, 1),
            map=_resolved(capabilities.map, ()),
            shared_roots=_resolved(capabilities.shared_roots, ()),
        ),
        tests=EffectiveTestsConfig(
            patterns=_resolved(tests.patterns, DEFAULT_TEST_PATTERNS),
            association=_resolved(tests.association, "same-capability"),
            test_roots=_resolved(tests.test_roots, ()),
        ),
        contracts=EffectiveContractsConfig(
            required_for=_resolved(contracts.required_for, ()),
            accepted_names=_resolved(
                contracts.accepted_names,
                ("CONTRACT.md", "openapi.yaml", "schema.graphql"),
            ),
        ),
        boundaries=EffectiveBoundariesConfig(public=_resolved(boundaries.public, ())),
        naming=EffectiveNamingConfig(
            registry=_resolved(naming.registry, "naming-registry.txt"),
            required=_resolved(naming.required, False),
        ),
        documentation=EffectiveDocumentationConfig(
            root_context_required=_resolved(documentation.root_context_required, True),
            max_context_lines=_resolved(documentation.max_context_lines, 200),
        ),
        exceptions=ResolvedValue(
            effective_exceptions, "file" if raw.exceptions is not None else "default"
        ),
    )


def _configured_paths(config: GardenConfig) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []

    def add(path: str, items: tuple[str, ...] | None) -> None:
        if items is not None:
            values.extend(
                (f"{path}[{index}]", item) for index, item in enumerate(items)
            )

    project = config.project
    if project and project.context_files:
        add("project.context_files.any_of", project.context_files.any_of)
        add("project.context_files.all_of", project.context_files.all_of)
    if config.scan:
        add("scan.roots", config.scan.roots)
        add("scan.include", config.scan.include)
        add("scan.exclude", config.scan.exclude)
    if config.capabilities:
        add("capabilities.roots", config.capabilities.roots)
        add("capabilities.shared_roots", config.capabilities.shared_roots)
        if config.capabilities.map:
            values.extend(
                (f"capabilities.map.{path}", path)
                for path, _ in config.capabilities.map
            )
    if config.tests:
        add("tests.patterns", config.tests.patterns)
        if config.tests.test_roots:
            for test_path, source_path in config.tests.test_roots:
                values.append((f"tests.test_roots.{test_path}", test_path))
                values.append((f"tests.test_roots.{test_path}", source_path))
    if config.boundaries:
        add("boundaries.public", config.boundaries.public)
    if config.naming and config.naming.registry is not None:
        values.append(("naming.registry", config.naming.registry))
    if config.exceptions:
        for index, item in enumerate(config.exceptions):
            add(f"exceptions[{index}].paths", item.paths)
    return tuple(values)


def _confinement_errors(config: GardenConfig, root: Path) -> tuple[ConfigError, ...]:
    errors = []
    for path, value in _configured_paths(config):
        if not is_within(root / value, root):
            errors.append(ConfigError(path, "path resolves outside the project root"))
    return tuple(errors)


def load_config(root: Path) -> ConfigResult:
    """Load and validate the configuration directly under a project root."""

    resolved = root.resolve()
    path = resolved / CONFIG_NAME
    if not path.is_file():
        return ConfigResult(resolved, path, False, None, ())
    try:
        with path.open("rb") as handle:
            parsed = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        return ConfigResult(
            resolved, path, True, None, (ConfigError("config", str(error)),)
        )
    validation = validate_config(parsed)
    if validation.config is None:
        return ConfigResult(resolved, path, True, None, validation.errors)
    confinement = _confinement_errors(validation.config, resolved)
    if confinement:
        return ConfigResult(resolved, path, True, None, confinement)
    return ConfigResult(resolved, path, True, validation.config, ())


def _relative_parts(value: str) -> tuple[str, ...]:
    if value == ".":
        return ()
    return PurePosixPath(value).parts


def _under(path: str, prefix: str) -> tuple[str, ...] | None:
    path_parts = _relative_parts(path)
    prefix_parts = _relative_parts(prefix)
    if path_parts[: len(prefix_parts)] != prefix_parts:
        return None
    return path_parts[len(prefix_parts) :]


def _resolve_none(relative_path: str, config: EffectiveConfig) -> CapabilityResolution:
    return CapabilityResolution("none")


def _resolve_explicit(
    relative_path: str, config: EffectiveConfig
) -> CapabilityResolution:
    mappings = sorted(
        config.capabilities.map.value,
        key=lambda item: len(_relative_parts(item[0])),
        reverse=True,
    )
    for prefix, capability in mappings:
        if _under(relative_path, prefix) is not None:
            return CapabilityResolution("capability", capability)
    return CapabilityResolution("none")


def _resolve_children(
    relative_path: str, config: EffectiveConfig
) -> CapabilityResolution:
    depth = config.capabilities.depth.value
    for root in config.capabilities.roots.value:
        remainder = _under(relative_path, root)
        if remainder is not None and len(remainder) > depth:
            return CapabilityResolution("capability", "/".join(remainder[:depth]))
    return CapabilityResolution("none")


def _resolve_markers(
    relative_path: str, config: EffectiveConfig
) -> CapabilityResolution:
    return CapabilityResolution("unknown", tag="EXPERIMENTAL")


_CAPABILITY_RESOLVERS: dict[
    str, Callable[[str, EffectiveConfig], CapabilityResolution]
] = {
    "none": _resolve_none,
    "explicit": _resolve_explicit,
    "children": _resolve_children,
    "markers": _resolve_markers,
}


def resolve_capability(
    relative_path: str, config: EffectiveConfig
) -> CapabilityResolution:
    """Resolve one relative path through the configured capability strategy."""

    normalized = PurePosixPath(relative_path.replace("\\", "/")).as_posix()
    for shared_root in config.capabilities.shared_roots.value:
        if _under(normalized, shared_root) is not None:
            return CapabilityResolution("shared")
    strategy = config.capabilities.strategy.value
    return _CAPABILITY_RESOLVERS[strategy](normalized, config)


def _associate_same_capability(
    relative_path: str, config: EffectiveConfig
) -> TestAssociationResolution:
    return TestAssociationResolution("same-capability")


def _associate_test_roots(
    relative_path: str, config: EffectiveConfig
) -> TestAssociationResolution:
    mappings = sorted(
        config.tests.test_roots.value,
        key=lambda item: len(_relative_parts(item[0])),
        reverse=True,
    )
    for test_prefix, source_prefix in mappings:
        remainder = _under(relative_path, test_prefix)
        if remainder is not None:
            source = PurePosixPath(source_prefix, *remainder).as_posix()
            return TestAssociationResolution("mapped", source)
    return TestAssociationResolution("unmapped")


_TEST_ASSOCIATION_RESOLVERS: dict[
    str, Callable[[str, EffectiveConfig], TestAssociationResolution]
] = {
    "same-capability": _associate_same_capability,
    "test-roots": _associate_test_roots,
}


def resolve_test_association(
    relative_path: str, config: EffectiveConfig
) -> TestAssociationResolution:
    """Resolve one test path through the configured association strategy."""

    normalized = PurePosixPath(relative_path.replace("\\", "/")).as_posix()
    association = config.tests.association.value
    return _TEST_ASSOCIATION_RESOLVERS[association](normalized, config)


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _show_value(value: object, *, mapping: bool = False) -> str:
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if type(value) is str:
        return _toml_string(value)
    if type(value) is tuple:
        if mapping:
            if not value:
                return "{}"
            pairs = ", ".join(
                f"{_toml_string(key)} = {_toml_string(item)}" for key, item in value
            )
            return "{ " + pairs + " }"
        return _toml_array(value)
    raise TypeError(f"unsupported effective config value: {type(value).__name__}")


def render_effective(config: EffectiveConfig) -> str:
    """Render effective values as stable dotted paths with origin comments."""

    lines: list[str] = []

    def add(path: str, value: ResolvedValue, *, mapping: bool = False) -> None:
        rendered = _show_value(value.value, mapping=mapping)
        lines.append(f"{path} = {rendered} # origin: {value.origin}")

    add("schema_version", config.schema_version)
    add("project.type", config.project.type)
    add("project.context_files.any_of", config.project.context_files.any_of)
    add("project.context_files.all_of", config.project.context_files.all_of)
    add("scan.roots", config.scan.roots)
    add("scan.include", config.scan.include)
    add("scan.exclude", config.scan.exclude)
    add("capabilities.strategy", config.capabilities.strategy)
    add("capabilities.roots", config.capabilities.roots)
    add("capabilities.depth", config.capabilities.depth)
    add("capabilities.map", config.capabilities.map, mapping=True)
    add("capabilities.shared_roots", config.capabilities.shared_roots)
    add("tests.patterns", config.tests.patterns)
    add("tests.association", config.tests.association)
    add("tests.test_roots", config.tests.test_roots, mapping=True)
    add("contracts.required_for", config.contracts.required_for)
    add("contracts.accepted_names", config.contracts.accepted_names)
    add("boundaries.public", config.boundaries.public)
    add("naming.registry", config.naming.registry)
    add("naming.required", config.naming.required)
    add(
        "documentation.root_context_required",
        config.documentation.root_context_required,
    )
    add("documentation.max_context_lines", config.documentation.max_context_lines)
    exceptions = config.exceptions.value
    lines.append(f"exceptions = {len(exceptions)} # origin: {config.exceptions.origin}")
    for index, item in enumerate(exceptions):
        add(f"exceptions[{index}].rule_id", item.rule_id)
        add(f"exceptions[{index}].paths", item.paths)
        add(f"exceptions[{index}].reason", item.reason)
        add(f"exceptions[{index}].owner", item.owner)
        add(f"exceptions[{index}].review_after", item.review_after)
    return "\n".join(lines) + "\n"


def detect_stack(root: Path) -> DetectedStack:
    """Detect supported stack markers and conservative source/test patterns."""

    marker_globs = {
        "pyproject.toml": (("**/*.py",), ("**/test_*.py", "tests/**")),
        "package.json": (
            ("**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"),
            ("**/*.test.ts", "**/*.spec.ts", "**/*.test.js", "**/*.spec.js"),
        ),
        "Cargo.toml": (("**/*.rs",), ("**/tests/**", "**/*_test.rs")),
        "go.mod": (("**/*.go",), ("**/*_test.go",)),
    }
    markers = tuple(name for name in marker_globs if (root / name).is_file())
    include: list[str] = []
    tests: list[str] = []
    for marker in markers:
        source_globs, test_globs = marker_globs[marker]
        include.extend(value for value in source_globs if value not in include)
        tests.extend(value for value in test_globs if value not in tests)
    if not include:
        include.extend(DEFAULT_SCAN_INCLUDE)
    if not tests:
        tests.extend(DEFAULT_TEST_PATTERNS)

    roots = tuple(
        name for name in ("src", "lib", "app", "packages") if (root / name).is_dir()
    ) or (".",)
    project_type = "monorepo" if len(markers) > 1 or "packages" in roots else "other"
    return DetectedStack(markers, project_type, roots, tuple(include), tuple(tests))


def render_init_config(root: Path) -> str:
    """Render a conservative initialized configuration for an existing project."""

    detected = detect_stack(root)
    markers = ", ".join(detected.markers) if detected.markers else "none"
    return (
        f"# detected stack markers: {markers}\n"
        f"schema_version = {SCHEMA_VERSION}\n\n"
        "[project]\n"
        f"type = {_toml_string(detected.project_type)}\n"
        'context_files = { any_of = ["CONTEXT.md", "AGENTS.md"] }\n\n'
        "[scan]\n"
        f"roots = {_toml_array(detected.roots)}\n"
        f"include = {_toml_array(detected.include)}\n"
        f"exclude = {_toml_array(DEFAULT_SCAN_EXCLUDE)}\n\n"
        "[capabilities]\n"
        'strategy = "children"\n'
        f"roots = {_toml_array(detected.roots)}\n"
        "depth = 1\n"
        "shared_roots = []\n\n"
        "# map = {}\n\n"
        "[tests]\n"
        f"patterns = {_toml_array(detected.test_patterns)}\n"
        'association = "same-capability"\n\n'
        "# test_roots = {}\n\n"
        "[documentation]\n"
        "root_context_required = true\n"
        "max_context_lines = 200\n\n"
        "# [contracts]\n"
        "# required_for = []\n"
        '# accepted_names = ["CONTRACT.md", "openapi.yaml", "schema.graphql"]\n\n'
        "# [boundaries]\n"
        "# public = []\n\n"
        "# [naming]\n"
        '# registry = "naming-registry.txt"\n'
        "# required = false\n\n"
        "# [[exceptions]]\n"
        '# rule_id = ""\n'
        "# paths = []\n"
        '# reason = ""\n'
        '# owner = ""\n'
        '# review_after = ""\n'
    )


def _migrated_raw_config(registry_name: str) -> GardenConfig:
    return GardenConfig(
        schema_version=SCHEMA_VERSION,
        naming=NamingConfig(registry=registry_name, required=True),
    )


def render_migrated_config(registry_name: str = "naming-registry.txt") -> str:
    """Render the fixed v1 migration shape for a legacy naming registry."""

    return (
        f"schema_version = {SCHEMA_VERSION}\n\n"
        "# TODO: set project.type and context_files for this project.\n"
        "# TODO: set scan roots and source globs for this project.\n"
        "# TODO: choose a capability strategy and test association.\n\n"
        "[naming]\n"
        f"registry = {_toml_string(registry_name)}\n"
        "required = true\n\n"
        "# TODO: declare public boundaries, contract policy, and structured exceptions.\n"
    )


def _check_rendered_config(text: str, intended: GardenConfig) -> None:
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigWriteError(
            f"generated configuration is invalid TOML: {error}"
        ) from error
    validation = validate_config(parsed)
    if validation.errors or validation.config is None:
        rendered = "; ".join(str(error) for error in validation.errors)
        raise ConfigWriteError(f"generated configuration is invalid: {rendered}")
    if resolve_effective(validation.config) != resolve_effective(intended):
        raise ConfigWriteError("generated configuration changed its intended meaning")


def _atomic_write(path: Path, content: str) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_config(root: Path, content: str, *, force: bool) -> Path:
    resolved = root.resolve()
    if not resolved.is_dir():
        raise ConfigWriteError(f"project root is not a directory: {resolved}")
    destination = resolved / CONFIG_NAME
    if destination.exists() and not force:
        raise ConfigWriteError(f"configuration already exists: {destination}")
    _atomic_write(destination, content)
    return destination


def initialize_config(root: Path, *, force: bool = False) -> Path:
    """Write a conservative v1 configuration without restructuring the project."""

    resolved = root.resolve()
    content = render_init_config(resolved)
    parsed = tomllib.loads(content)
    validation = validate_config(parsed)
    if validation.errors:
        rendered = "; ".join(str(error) for error in validation.errors)
        raise ConfigWriteError(f"generated configuration is invalid: {rendered}")
    return _write_config(resolved, content, force=force)


def migrate_config(root: Path, *, force: bool = False) -> Path:
    """Migrate legacy naming-registry activation to a checked v1 config."""

    resolved = root.resolve()
    registry = resolved / "naming-registry.txt"
    if not registry.is_file():
        raise ConfigWriteError(f"legacy naming registry not found: {registry}")
    try:
        registry.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ConfigWriteError(
            f"cannot read legacy naming registry: {error}"
        ) from error
    intended = _migrated_raw_config(registry.name)
    content = render_migrated_config(registry.name)
    _check_rendered_config(content, intended)
    return _write_config(resolved, content, force=force)

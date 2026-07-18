"""Load and validate the canonical GARDEN rule registry."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent / "rules" / "garden-rules.toml"
)
LEVELS = frozenset({"REQUIRED", "DEFAULT", "EXPERIMENTAL"})
IMPLEMENTATIONS = frozenset(
    {"automated", "partial", "manual-with-owner", "planned", "experimental"}
)
RULE_FIELDS = frozenset(
    {
        "id",
        "principle",
        "title",
        "level",
        "scope",
        "implementation",
        "runtime_aliases",
        "configuration_keys",
        "exception_policy",
        "exception_allowed",
    }
)
OPTIONAL_RULE_FIELDS = frozenset({"digest"})
RUNTIME_CHECK_FIELDS = frozenset({"id", "principle", "level", "title"})
PRINCIPLE_FIELDS = frozenset({"letter", "name", "digest_notes"})


class RegistryError(ValueError):
    """Raised when the rule registry is malformed or internally inconsistent."""


@dataclass(frozen=True)
class RuleEntry:
    id: str
    principle: str
    title: str
    level: str
    scope: str
    implementation: str
    runtime_aliases: tuple[str, ...]
    configuration_keys: tuple[str, ...]
    exception_policy: str
    exception_allowed: bool
    digest: str | None = None


@dataclass(frozen=True)
class RuntimeCheckEntry:
    id: str
    principle: str
    level: str
    title: str


@dataclass(frozen=True)
class PrincipleEntry:
    letter: str
    name: str
    digest_notes: tuple[str, ...]


@dataclass(frozen=True)
class Registry:
    rules: tuple[RuleEntry, ...]
    runtime_checks: tuple[RuntimeCheckEntry, ...]
    principles: tuple[PrincipleEntry, ...]
    _rules_by_id: Mapping[str, RuleEntry] = field(init=False, repr=False, compare=False)
    _runtime_checks_by_id: Mapping[str, RuntimeCheckEntry] = field(
        init=False, repr=False, compare=False
    )
    _principles_by_letter: Mapping[str, PrincipleEntry] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        rules_by_id = _index_entries(self.rules, "rules")
        runtime_checks_by_id = _index_entries(self.runtime_checks, "runtime_checks")
        collisions = set(rules_by_id) & set(runtime_checks_by_id)
        if collisions:
            joined = ", ".join(sorted(collisions))
            raise RegistryError(f"registry IDs appear in both sections: {joined}")
        principles_by_letter = _index_principles(self.principles)
        used_principles = {rule.principle for rule in self.rules}
        missing_principles = used_principles - set(principles_by_letter)
        if missing_principles:
            joined = ", ".join(sorted(missing_principles))
            raise RegistryError(
                f"rule principles lack [[principles]] entries: {joined}"
            )
        unused_principles = set(principles_by_letter) - used_principles
        if unused_principles:
            joined = ", ".join(sorted(unused_principles))
            raise RegistryError(f"unused [[principles]] entries: {joined}")
        object.__setattr__(self, "_rules_by_id", MappingProxyType(rules_by_id))
        object.__setattr__(
            self,
            "_runtime_checks_by_id",
            MappingProxyType(runtime_checks_by_id),
        )
        object.__setattr__(
            self,
            "_principles_by_letter",
            MappingProxyType(principles_by_letter),
        )

    def rule(self, identifier: str) -> RuleEntry | None:
        """Return a canonical rule by ID."""

        return self._rules_by_id.get(identifier)

    def runtime_check(self, identifier: str) -> RuntimeCheckEntry | None:
        """Return a runtime-only check by ID."""

        return self._runtime_checks_by_id.get(identifier)

    def principle(self, letter: str) -> PrincipleEntry | None:
        """Return principle metadata by letter."""

        return self._principles_by_letter.get(letter)


def _index_entries(
    entries: tuple[RuleEntry, ...] | tuple[RuntimeCheckEntry, ...],
    section: str,
) -> dict[str, RuleEntry] | dict[str, RuntimeCheckEntry]:
    indexed: dict[str, RuleEntry] | dict[str, RuntimeCheckEntry] = {}
    for entry in entries:
        if entry.id in indexed:
            raise RegistryError(f"duplicate ID in [[{section}]]: {entry.id}")
        indexed[entry.id] = entry
    return indexed


def _index_principles(
    entries: tuple[PrincipleEntry, ...],
) -> dict[str, PrincipleEntry]:
    indexed: dict[str, PrincipleEntry] = {}
    for entry in entries:
        if entry.letter in indexed:
            raise RegistryError(f"duplicate letter in [[principles]]: {entry.letter}")
        indexed[entry.letter] = entry
    return indexed


def _table(
    value: object,
    section: str,
    index: int,
    expected_fields: frozenset[str],
    optional_fields: frozenset[str] = frozenset(),
) -> dict[str, object]:
    location = f"[[{section}]][{index}]"
    if not isinstance(value, dict):
        raise RegistryError(f"{location} must be a table")
    missing = expected_fields - set(value)
    if missing:
        raise RegistryError(
            f"{location} misses required fields: {', '.join(sorted(missing))}"
        )
    unknown = set(value) - expected_fields - optional_fields
    if unknown:
        raise RegistryError(
            f"{location} has unknown fields: {', '.join(sorted(unknown))}"
        )
    return value


def _string(table: dict[str, object], field_name: str, location: str) -> str:
    value = table[field_name]
    if not isinstance(value, str) or not value:
        raise RegistryError(f"{location}.{field_name} must be a non-empty string")
    return value


def _string_tuple(
    table: dict[str, object], field_name: str, location: str
) -> tuple[str, ...]:
    value = table[field_name]
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise RegistryError(
            f"{location}.{field_name} must be an array of non-empty strings"
        )
    return tuple(value)


def _principle(identifier: str, principle: str, location: str) -> None:
    if re.fullmatch(r"[A-Z]", principle) is None:
        raise RegistryError(f"{location}.principle must be a single uppercase letter")
    identifier_principle, separator, _ = identifier.partition("-")
    if not separator or identifier_principle != principle:
        raise RegistryError(
            f"{location}.principle {principle!r} does not match ID {identifier!r}"
        )


def _level(table: dict[str, object], location: str) -> str:
    level = _string(table, "level", location)
    if level not in LEVELS:
        raise RegistryError(
            f"{location}.level must be one of {', '.join(sorted(LEVELS))}; got {level!r}"
        )
    return level


def _rule_entry(value: object, index: int) -> RuleEntry:
    location = f"[[rules]][{index}]"
    table = _table(value, "rules", index, RULE_FIELDS, OPTIONAL_RULE_FIELDS)
    identifier = _string(table, "id", location)
    principle = _string(table, "principle", location)
    _principle(identifier, principle, location)
    level = _level(table, location)
    implementation = _string(table, "implementation", location)
    if implementation not in IMPLEMENTATIONS:
        raise RegistryError(
            f"{location}.implementation must be one of "
            f"{', '.join(sorted(IMPLEMENTATIONS))}; got {implementation!r}"
        )
    exception_policy = _string(table, "exception_policy", location)
    exception_allowed = table["exception_allowed"]
    if not isinstance(exception_allowed, bool):
        raise RegistryError(f"{location}.exception_allowed must be a boolean")
    if exception_allowed != (exception_policy != "not-allowed"):
        raise RegistryError(
            f"{location}.exception_allowed is inconsistent with exception_policy"
        )
    if level in {"REQUIRED", "DEFAULT"}:
        if "digest" not in table:
            raise RegistryError(f"{location}.digest is required for {level} rules")
        digest = _string(table, "digest", location)
    else:
        if "digest" in table:
            raise RegistryError(
                f"{location}.digest must be absent for EXPERIMENTAL rules"
            )
        digest = None
    return RuleEntry(
        id=identifier,
        principle=principle,
        title=_string(table, "title", location),
        level=level,
        scope=_string(table, "scope", location),
        implementation=implementation,
        runtime_aliases=_string_tuple(table, "runtime_aliases", location),
        configuration_keys=_string_tuple(table, "configuration_keys", location),
        exception_policy=exception_policy,
        exception_allowed=exception_allowed,
        digest=digest,
    )


def _runtime_check_entry(value: object, index: int) -> RuntimeCheckEntry:
    location = f"[[runtime_checks]][{index}]"
    table = _table(value, "runtime_checks", index, RUNTIME_CHECK_FIELDS)
    identifier = _string(table, "id", location)
    principle = _string(table, "principle", location)
    _principle(identifier, principle, location)
    return RuntimeCheckEntry(
        id=identifier,
        principle=principle,
        level=_level(table, location),
        title=_string(table, "title", location),
    )


def _principle_entry(value: object, index: int) -> PrincipleEntry:
    location = f"[[principles]][{index}]"
    table = _table(value, "principles", index, PRINCIPLE_FIELDS)
    letter = _string(table, "letter", location)
    if re.fullmatch(r"[A-Z]", letter) is None:
        raise RegistryError(f"{location}.letter must be a single uppercase letter")
    return PrincipleEntry(
        letter=letter,
        name=_string(table, "name", location),
        digest_notes=_string_tuple(table, "digest_notes", location),
    )


def _section(document: dict[str, object], name: str) -> list[object]:
    value = document.get(name)
    if not isinstance(value, list):
        raise RegistryError(f"registry must define [[{name}]] entries")
    return value


@lru_cache(maxsize=None)
def _load_registry(resolved_path: str) -> Registry:
    path = Path(resolved_path)
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise RegistryError(f"cannot load registry {path}: {error}") from error
    unknown_sections = set(document) - {"rules", "runtime_checks", "principles"}
    if unknown_sections:
        raise RegistryError(
            "registry has unknown top-level sections: "
            + ", ".join(sorted(unknown_sections))
        )
    rules = tuple(
        _rule_entry(value, index)
        for index, value in enumerate(_section(document, "rules"), start=1)
    )
    runtime_checks = tuple(
        _runtime_check_entry(value, index)
        for index, value in enumerate(_section(document, "runtime_checks"), start=1)
    )
    principles = tuple(
        _principle_entry(value, index)
        for index, value in enumerate(_section(document, "principles"), start=1)
    )
    return Registry(
        rules=rules,
        runtime_checks=runtime_checks,
        principles=principles,
    )


def load_registry(path: Path | None = None) -> Registry:
    """Load the canonical registry or an explicitly supplied registry path."""

    resolved = (path or DEFAULT_REGISTRY_PATH).resolve()
    return _load_registry(str(resolved))

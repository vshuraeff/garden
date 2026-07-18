#!/usr/bin/env -S uv run --no-project
"""Run the preregistered GARDEN agent-value benchmark v2 matrix."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


AGENT_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = AGENT_ROOT.parents[1]
FIXTURE_ROOT = AGENT_ROOT / "fixture"
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "garden"
PROTOCOL_PATH = AGENT_ROOT / "protocol-v2.toml"
PRICING_PATH = AGENT_ROOT / "pricing.toml"
RESULT_SCHEMA_PATH = AGENT_ROOT / "schemas" / "result.schema.json"
FIXTURE_EXCLUDES = frozenset({"prompts", "verify", "__pycache__"})


T1_REGRESSION_TEST = '''from __future__ import annotations

import unittest

from capabilities.pricing.api import discount_percent


class CouponNormalizationRegressionTests(unittest.TestCase):
    def test_coupon_lookup_ignores_case_and_surrounding_whitespace(self) -> None:
        self.assertEqual(10, discount_percent("  save10 "))


if __name__ == "__main__":
    unittest.main()
'''


class BenchmarkError(RuntimeError):
    """One runner failure with a user-facing explanation."""


class SchemaValidationError(ValueError):
    """One result-record schema violation."""


@dataclass(frozen=True)
class TokenUsage:
    """Normalized billable token counts."""

    input: int
    output: int
    cache: int

    def as_dict(self) -> dict[str, int]:
        """Return the result-schema representation."""

        return {"input": self.input, "output": self.output, "cache": self.cache}


@dataclass(frozen=True)
class Telemetry:
    """Harness-independent telemetry used by metrics."""

    tokens: TokenUsage
    wall_clock_seconds: float
    model_ids: tuple[str, ...]
    per_model_tokens: dict[str, TokenUsage]


@dataclass(frozen=True)
class Cell:
    """One matrix cell repetition."""

    harness: str
    condition: str
    task_id: str
    repetition: int

    @property
    def identifier(self) -> str:
        """Return a filesystem-safe stable cell identifier."""

        return (
            f"{self.harness}__{self.condition}__{self.task_id}"
            f"__r{self.repetition}"
        )


def load_toml(path: Path) -> dict[str, Any]:
    """Load one TOML object."""

    value = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BenchmarkError(f"TOML root is not a table: {path}")
    return value


def _integer(mapping: Mapping[str, Any], *names: str) -> int:
    for name in names:
        value = mapping.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return 0


def _number(mapping: Mapping[str, Any], *names: str) -> float:
    for name in names:
        value = mapping.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return 0.0


def _claude_model_tokens(value: Mapping[str, Any]) -> TokenUsage:
    return TokenUsage(
        input=_integer(value, "inputTokens", "input_tokens"),
        output=_integer(value, "outputTokens", "output_tokens"),
        cache=_integer(value, "cacheReadInputTokens", "cache_read_input_tokens")
        + _integer(
            value,
            "cacheCreationInputTokens",
            "cache_creation_input_tokens",
        ),
    )


def parse_claude_code_telemetry(raw: Mapping[str, Any]) -> Telemetry:
    """Normalize a Claude Code single-result JSON object."""

    usage_value = raw.get("usage", {})
    usage = usage_value if isinstance(usage_value, Mapping) else {}
    model_usage_value = raw.get("modelUsage", raw.get("model_usage", {}))
    model_usage = (
        model_usage_value if isinstance(model_usage_value, Mapping) else {}
    )
    per_model: dict[str, TokenUsage] = {}
    for model, value in model_usage.items():
        if isinstance(model, str) and isinstance(value, Mapping):
            per_model[model] = _claude_model_tokens(value)

    tokens = TokenUsage(
        input=_integer(usage, "input_tokens", "inputTokens"),
        output=_integer(usage, "output_tokens", "outputTokens"),
        cache=_integer(usage, "cache_read_input_tokens", "cacheReadInputTokens")
        + _integer(
            usage,
            "cache_creation_input_tokens",
            "cacheCreationInputTokens",
        ),
    )
    if tokens == TokenUsage(0, 0, 0) and per_model:
        tokens = _sum_tokens(per_model.values())

    model_ids: list[str] = list(per_model)
    raw_model = raw.get("model")
    if isinstance(raw_model, str):
        model_ids.append(raw_model)
    raw_model_ids = raw.get("model_ids")
    if isinstance(raw_model_ids, list):
        model_ids.extend(value for value in raw_model_ids if isinstance(value, str))
    return Telemetry(
        tokens=tokens,
        wall_clock_seconds=_number(raw, "duration_ms", "duration_api_ms") / 1000,
        model_ids=tuple(dict.fromkeys(model_ids)),
        per_model_tokens=per_model,
    )


def _codex_model_tokens(value: Mapping[str, Any]) -> TokenUsage:
    total_input = _integer(value, "input_tokens", "inputTokens")
    cache = _integer(value, "cached_input_tokens", "cachedInputTokens")
    return TokenUsage(
        input=max(total_input - cache, 0),
        output=_integer(value, "output_tokens", "outputTokens"),
        cache=cache,
    )


def parse_codex_telemetry(events: Sequence[Mapping[str, Any]]) -> Telemetry:
    """Normalize a Codex exec JSONL event stream."""

    completed: Mapping[str, Any] | None = None
    model_ids: list[str] = []
    for event in events:
        if event.get("type") == "turn.completed":
            completed = event
        model = event.get("model")
        if isinstance(model, str):
            model_ids.append(model)
        for field in ("model_ids", "subagent_models"):
            values = event.get(field)
            if isinstance(values, list):
                model_ids.extend(value for value in values if isinstance(value, str))
    if completed is None:
        raise BenchmarkError("Codex telemetry has no turn.completed event")

    usage_value = completed.get("usage", {})
    usage = usage_value if isinstance(usage_value, Mapping) else {}
    tokens = _codex_model_tokens(usage)
    per_model_value = completed.get("model_usage", {})
    per_model: dict[str, TokenUsage] = {}
    if isinstance(per_model_value, Mapping):
        for model, value in per_model_value.items():
            if isinstance(model, str) and isinstance(value, Mapping):
                per_model[model] = _codex_model_tokens(value)
                model_ids.append(model)
    return Telemetry(
        tokens=tokens,
        wall_clock_seconds=_number(completed, "duration_ms") / 1000,
        model_ids=tuple(dict.fromkeys(model_ids)),
        per_model_tokens=per_model,
    )


def _sum_tokens(values: Sequence[TokenUsage] | Any) -> TokenUsage:
    items = list(values)
    return TokenUsage(
        input=sum(item.input for item in items),
        output=sum(item.output for item in items),
        cache=sum(item.cache for item in items),
    )


def calculate_cost(tokens: TokenUsage, rates: Mapping[str, Any]) -> float:
    """Calculate USD cost for one model's normalized tokens."""

    input_rate = float(rates["input_per_million_usd"])
    output_rate = float(rates["output_per_million_usd"])
    cache_rate = float(rates["cache_per_million_usd"])
    return (
        tokens.input * input_rate
        + tokens.output * output_rate
        + tokens.cache * cache_rate
    ) / 1_000_000


def calculate_telemetry_cost(
    telemetry: Telemetry,
    pricing: Mapping[str, Mapping[str, Any]],
    main_model: str,
) -> float:
    """Price per-model telemetry, falling back to aggregate main-model rates."""

    per_model_total = _sum_tokens(telemetry.per_model_tokens.values())
    if telemetry.per_model_tokens and per_model_total == telemetry.tokens:
        missing = sorted(set(telemetry.per_model_tokens) - set(pricing))
        if missing:
            raise BenchmarkError(f"pricing is missing model ids: {missing}")
        return sum(
            calculate_cost(tokens, pricing[model])
            for model, tokens in telemetry.per_model_tokens.items()
        )
    if main_model not in pricing:
        raise BenchmarkError(f"pricing is missing main model {main_model}")
    return calculate_cost(telemetry.tokens, pricing[main_model])


def mock_claude_code_telemetry(models: Mapping[str, Any]) -> dict[str, Any]:
    """Return representative Claude Code result telemetry."""

    main_model = str(models["main_model"])
    subagent_model = str(models["subagent_models"][0])
    return {
        "type": "result",
        "subtype": "success",
        "duration_ms": 1250,
        "usage": {
            "input_tokens": 1100,
            "output_tokens": 240,
            "cache_read_input_tokens": 600,
            "cache_creation_input_tokens": 50,
        },
        "modelUsage": {
            main_model: {
                "inputTokens": 1000,
                "outputTokens": 200,
                "cacheReadInputTokens": 550,
                "cacheCreationInputTokens": 50,
            },
            subagent_model: {
                "inputTokens": 100,
                "outputTokens": 40,
                "cacheReadInputTokens": 50,
                "cacheCreationInputTokens": 0,
            },
        },
    }


def mock_codex_telemetry(models: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return representative Codex exec JSONL events."""

    main_model = str(models["main_model"])
    subagents = [str(value) for value in models["subagent_models"]]
    return [
        {
            "type": "thread.started",
            "thread_id": "dry-run-thread",
            "model": main_model,
            "subagent_models": subagents,
        },
        {"type": "turn.started"},
        {
            "type": "turn.completed",
            "duration_ms": 1500,
            "usage": {
                "input_tokens": 1500,
                "cached_input_tokens": 500,
                "output_tokens": 300,
                "reasoning_output_tokens": 80,
            },
            "model_usage": {
                main_model: {
                    "input_tokens": 1200,
                    "cached_input_tokens": 400,
                    "output_tokens": 220,
                },
                subagents[0]: {
                    "input_tokens": 200,
                    "cached_input_tokens": 50,
                    "output_tokens": 50,
                },
                subagents[1]: {
                    "input_tokens": 100,
                    "cached_input_tokens": 50,
                    "output_tokens": 30,
                },
            },
        },
    ]


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    raise SchemaValidationError(f"unsupported schema type {expected!r}")


def _resolve_ref(
    root_schema: Mapping[str, Any], reference: str
) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        raise SchemaValidationError(f"unsupported schema reference {reference!r}")
    value: Any = root_schema
    for component in reference[2:].split("/"):
        value = value[component.replace("~1", "/").replace("~0", "~")]
    if not isinstance(value, Mapping):
        raise SchemaValidationError(f"schema reference is not an object: {reference}")
    return value


def validate_against_schema(
    value: Any,
    schema: Mapping[str, Any],
    root_schema: Mapping[str, Any] | None = None,
    location: str = "$",
) -> None:
    """Validate the result-schema subset used by this benchmark."""

    root = root_schema or schema
    if "$ref" in schema:
        validate_against_schema(
            value,
            _resolve_ref(root, str(schema["$ref"])),
            root,
            location,
        )
        return
    if "const" in schema and value != schema["const"]:
        raise SchemaValidationError(
            f"{location}: expected constant {schema['const']!r}"
        )
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(f"{location}: value {value!r} is outside enum")
    expected_types = schema.get("type")
    if isinstance(expected_types, str):
        expected_types = [expected_types]
    if isinstance(expected_types, list) and not any(
        _json_type_matches(value, str(expected)) for expected in expected_types
    ):
        raise SchemaValidationError(
            f"{location}: expected type {' or '.join(map(str, expected_types))}"
        )

    if isinstance(value, dict):
        for field in schema.get("required", []):
            if field not in value:
                raise SchemaValidationError(
                    f"{location}: missing required field {field}"
                )
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            raise SchemaValidationError(f"{location}: invalid schema properties")
        for field, field_value in value.items():
            if field in properties:
                field_schema = properties[field]
            else:
                additional = schema.get("additionalProperties", True)
                if additional is False:
                    raise SchemaValidationError(
                        f"{location}: unexpected field {field}"
                    )
                if additional is True:
                    continue
                field_schema = additional
            if not isinstance(field_schema, Mapping):
                raise SchemaValidationError(f"{location}.{field}: invalid schema")
            validate_against_schema(
                field_value, field_schema, root, f"{location}.{field}"
            )

    if isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            raise SchemaValidationError(f"{location}: array is too short")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                validate_against_schema(
                    item, item_schema, root, f"{location}[{index}]"
                )
        if schema.get("uniqueItems") is True:
            rendered = [json.dumps(item, sort_keys=True) for item in value]
            if len(rendered) != len(set(rendered)):
                raise SchemaValidationError(f"{location}: array items are not unique")

    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            raise SchemaValidationError(f"{location}: string is too short")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            raise SchemaValidationError(
                f"{location}: value does not match {pattern}"
            )
        if schema.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise SchemaValidationError(
                    f"{location}: invalid date-time"
                ) from error
            if parsed.tzinfo is None:
                raise SchemaValidationError(f"{location}: date-time has no timezone")

    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and "minimum" in schema
        and value < schema["minimum"]
    ):
        raise SchemaValidationError(f"{location}: value is below minimum")


def validate_result_record(
    record: Mapping[str, Any], schema_path: Path = RESULT_SCHEMA_PATH
) -> None:
    """Load the committed schema and validate one result record."""

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(schema, Mapping):
        raise SchemaValidationError("result schema root is not an object")
    validate_against_schema(record, schema)


def _copy_ignore(_: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in FIXTURE_EXCLUDES or name.endswith((".pyc", ".pyo"))
    }


def copy_fixture(target: Path) -> None:
    """Copy only agent-visible fixture project files."""

    shutil.copytree(FIXTURE_ROOT, target, ignore=_copy_ignore)


def fixture_hash() -> str:
    """Hash the condition-independent agent-visible fixture source."""

    digest = hashlib.sha256()
    for path in sorted(FIXTURE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(FIXTURE_ROOT)
        if any(part in FIXTURE_EXCLUDES for part in relative.parts):
            continue
        if path.suffix in (".pyc", ".pyo"):
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def prepare_task(target: Path, task_id: str) -> None:
    """Apply a preregistered task precondition before the baseline commit."""

    if task_id == "T1":
        (target / "tests" / "test_t1_regression.py").write_text(
            T1_REGRESSION_TEST, encoding="utf-8"
        )


def _run_checked(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise BenchmarkError(f"command failed ({' '.join(command)}): {detail}")
    return completed


def install_garden_locally(target: Path) -> Path:
    """Copy the local plugin and install its project-scoped surfaces."""

    plugin_copy = target / "plugins" / "garden"
    shutil.copytree(PLUGIN_ROOT, plugin_copy, ignore=_copy_ignore)
    marketplace = target / ".agents" / "plugins" / "marketplace.json"
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "agent-benchmark-local",
                "plugins": [
                    {
                        "name": "garden",
                        "source": {"source": "local", "path": "./plugins/garden"},
                        "policy": {
                            "installation": "AVAILABLE",
                            "authentication": "ON_INSTALL",
                        },
                        "category": "Developer Tools",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    cli = plugin_copy / "tools" / "garden_cli.py"
    _run_checked([sys.executable, str(cli), "init", str(target)], target)
    _run_checked(
        [
            sys.executable,
            str(cli),
            "install-project",
            str(target),
            "--harness",
            "both",
        ],
        target,
    )
    return plugin_copy


def initialize_git_baseline(target: Path) -> None:
    """Create the per-cell pristine commit used for diff metrics."""

    _run_checked(["git", "init", "-q", "--initial-branch", "master"], target)
    _run_checked(["git", "add", "."], target)
    _run_checked(
        [
            "git",
            "-c",
            "user.name=GARDEN benchmark",
            "-c",
            "user.email=benchmark@garden.invalid",
            "commit",
            "-q",
            "-m",
            "fixture baseline",
        ],
        target,
    )


def compute_diff_size(target: Path) -> dict[str, int]:
    """Count tracked and untracked line changes against the baseline commit."""

    _run_checked(["git", "add", "--intent-to-add", "."], target)
    output = _run_checked(
        ["git", "diff", "--numstat", "HEAD", "--"], target
    ).stdout
    lines_added = 0
    lines_removed = 0
    files_changed = 0
    for line in output.splitlines():
        added, removed, separator = line.partition("\t")
        removed_value, second_separator, _ = separator.partition("\t")
        if not separator or not second_separator:
            raise BenchmarkError(f"cannot parse git numstat line: {line!r}")
        lines_added += int(added) if added.isdigit() else 0
        lines_removed += int(removed_value) if removed_value.isdigit() else 0
        files_changed += 1
    return {
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "files_changed": files_changed,
    }


def build_cells(
    protocol: Mapping[str, Any], subsets: Sequence[str] | None = None
) -> list[Cell]:
    """Expand protocol matrix data and optional exact triple filters."""

    matrix = protocol["matrix"]
    if not isinstance(matrix, Mapping):
        raise BenchmarkError("protocol matrix is not a table")
    harnesses = [str(value) for value in matrix["harnesses"]]
    conditions = [str(value) for value in matrix["conditions"]]
    tasks = [str(value) for value in matrix["tasks"]]
    repetitions = int(protocol["repetitions"]["count"])
    selected: set[tuple[str, str, str]] | None = None
    if subsets:
        selected = set()
        for subset in subsets:
            parts = tuple(subset.split(":"))
            if len(parts) != 3:
                raise BenchmarkError(
                    "matrix subset must be HARNESS:CONDITION:TASK"
                )
            if parts[0] not in harnesses or parts[1] not in conditions or parts[2] not in tasks:
                raise BenchmarkError(f"matrix subset is outside the protocol: {subset}")
            selected.add((parts[0], parts[1], parts[2]))

    cells = [
        Cell(harness, condition, task_id, repetition)
        for harness in harnesses
        for condition in conditions
        for task_id in tasks
        if selected is None or (harness, condition, task_id) in selected
        for repetition in range(1, repetitions + 1)
    ]
    if selected is None and len(cells) != int(matrix["total_cell_runs"]):
        raise BenchmarkError(
            f"expanded matrix has {len(cells)} runs, expected {matrix['total_cell_runs']}"
        )
    return cells


def _parse_claude_stdout(stdout: str) -> dict[str, Any]:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise BenchmarkError(f"Claude Code emitted invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise BenchmarkError("Claude Code telemetry root is not an object")
    return value


def _parse_codex_stdout(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise BenchmarkError(
                f"Codex emitted invalid JSONL at line {line_number}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise BenchmarkError(f"Codex event {line_number} is not an object")
        events.append(value)
    return events


def invoke_live_harness(
    harness: str,
    harness_config: Mapping[str, Any],
    prompt: str,
    target: Path,
    plugin_copy: Path | None,
    timeout_seconds: int,
) -> tuple[dict[str, Any] | list[dict[str, Any]], float]:
    """Invoke one paid harness call after explicit live-mode selection."""

    command = [str(value) for value in harness_config["command"]]
    main_model = str(harness_config["main_model"])
    if harness == "claude_code":
        command.extend(["--model", main_model, "--permission-mode", "acceptEdits"])
        if plugin_copy is not None:
            command.extend(["--plugin-dir", str(plugin_copy)])
        command.append(prompt)
    elif harness == "codex":
        effort = str(harness_config["model_reasoning_effort"])
        command.extend(
            [
                "--model",
                main_model,
                "-c",
                f'model_reasoning_effort="{effort}"',
                "--sandbox",
                "workspace-write",
                "-C",
                str(target),
                prompt,
            ]
        )
    else:
        raise BenchmarkError(f"unsupported harness: {harness}")

    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=target,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    elapsed = time.monotonic() - started
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise BenchmarkError(f"{harness} exited {completed.returncode}: {detail}")
    if harness == "claude_code":
        return _parse_claude_stdout(completed.stdout), elapsed
    return _parse_codex_stdout(completed.stdout), elapsed


def parse_harness_telemetry(
    harness: str, raw: dict[str, Any] | list[dict[str, Any]]
) -> Telemetry:
    """Dispatch raw telemetry to the harness-specific pure parser."""

    if harness == "claude_code" and isinstance(raw, dict):
        return parse_claude_code_telemetry(raw)
    if harness == "codex" and isinstance(raw, list):
        return parse_codex_telemetry(raw)
    raise BenchmarkError(f"telemetry shape does not match harness {harness}")


def run_verifier(verifier: Path, target: Path) -> bool:
    """Run one garden-agnostic task verifier and validate its JSON summary."""

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, str(verifier), str(target)],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    try:
        summary = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise BenchmarkError(f"verifier emitted invalid JSON: {verifier}") from error
    if not isinstance(summary, dict) or summary.get("pass") != (
        completed.returncode == 0
    ):
        raise BenchmarkError(f"verifier result disagrees with exit code: {verifier}")
    return completed.returncode == 0


def cli_version(harness: str, dry_run: bool) -> str:
    """Return mock or installed CLI provenance without invoking a model."""

    if dry_run:
        return f"dry-run-mock/{harness}-v1"
    binary = "claude" if harness == "claude_code" else "codex"
    completed = subprocess.run(
        [binary, "--version"], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise BenchmarkError(f"cannot read {binary} version")
    return completed.stdout.strip()


def _raw_suffix(harness: str) -> str:
    return ".json" if harness == "claude_code" else ".jsonl"


def write_raw_telemetry(
    path: Path, raw: dict[str, Any] | list[dict[str, Any]]
) -> None:
    """Write the harness-native JSON or JSONL telemetry capture."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(raw, dict):
        path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        path.write_text(
            "".join(json.dumps(event, sort_keys=True) + "\n" for event in raw),
            encoding="utf-8",
        )


def run_cell(
    cell: Cell,
    protocol: Mapping[str, Any],
    pricing: Mapping[str, Mapping[str, Any]],
    output_dir: Path,
    source_hash: str,
    dry_run: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Execute one isolated matrix cell and persist its audited result."""

    harness_config = protocol["harnesses"][cell.harness]
    task_config = protocol["tasks"][cell.task_id]
    if not isinstance(harness_config, Mapping) or not isinstance(task_config, Mapping):
        raise BenchmarkError(f"invalid protocol entry for {cell.identifier}")
    prompt_path = AGENT_ROOT / str(task_config["prompt"])
    verifier_path = AGENT_ROOT / str(task_config["verifier"])
    prompt = prompt_path.read_text(encoding="utf-8")
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    with tempfile.TemporaryDirectory(prefix=f"agent-benchmark-{cell.identifier}-") as temporary:
        target = Path(temporary) / "fixture"
        copy_fixture(target)
        plugin_copy = (
            install_garden_locally(target)
            if cell.condition == "garden_on"
            else None
        )
        prepare_task(target, cell.task_id)
        initialize_git_baseline(target)

        if dry_run:
            raw = (
                mock_claude_code_telemetry(harness_config)
                if cell.harness == "claude_code"
                else mock_codex_telemetry(harness_config)
            )
            measured_elapsed: float | None = None
        else:
            raw, measured_elapsed = invoke_live_harness(
                cell.harness,
                harness_config,
                prompt,
                target,
                plugin_copy,
                timeout_seconds,
            )
        telemetry = parse_harness_telemetry(cell.harness, raw)
        if measured_elapsed is not None:
            telemetry = dataclasses.replace(
                telemetry, wall_clock_seconds=measured_elapsed
            )

        passed = run_verifier(verifier_path, target)
        diff_size = compute_diff_size(target)
        main_model = str(harness_config["main_model"])
        subagents = [str(value) for value in harness_config["subagent_models"]]
        model_ids = list(dict.fromkeys([main_model, *subagents]))
        cost = calculate_telemetry_cost(telemetry, pricing, main_model)

        raw_relative = Path("raw") / f"{cell.identifier}{_raw_suffix(cell.harness)}"
        raw_path = output_dir / raw_relative
        write_raw_telemetry(raw_path, raw)
        record: dict[str, Any] = {
            "schema_version": "2",
            "benchmark_version": "2",
            "harness": cell.harness,
            "condition": cell.condition,
            "task_id": cell.task_id,
            "repetition": cell.repetition,
            "models": {"main": main_model, "subagents": subagents},
            "pass": passed,
            "wall_clock_seconds": telemetry.wall_clock_seconds,
            "tokens": telemetry.tokens.as_dict(),
            "cost_usd": round(cost, 12),
            "diff_size": diff_size,
            "provenance": {
                "cli_version": cli_version(cell.harness, dry_run),
                "model_ids": model_ids,
                "fixture_hash": source_hash,
                "prompt_hash": prompt_hash,
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
            "raw_telemetry_ref": raw_relative.as_posix(),
        }
        validate_result_record(record)
        output_dir.mkdir(parents=True, exist_ok=True)
        result_path = output_dir / f"{cell.identifier}.json"
        result_path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return record


def run_benchmark(
    *,
    dry_run: bool,
    output_dir: Path,
    matrix_subsets: Sequence[str] | None = None,
    timeout_seconds: int = 1800,
) -> list[dict[str, Any]]:
    """Run the selected protocol matrix."""

    protocol = load_toml(PROTOCOL_PATH)
    pricing_data = load_toml(PRICING_PATH)
    pricing_value = pricing_data.get("models")
    if not isinstance(pricing_value, Mapping):
        raise BenchmarkError("pricing.toml has no models table")
    pricing = {
        str(model): rates
        for model, rates in pricing_value.items()
        if isinstance(rates, Mapping)
    }
    cells = build_cells(protocol, matrix_subsets)
    source_hash = fixture_hash()
    return [
        run_cell(
            cell,
            protocol,
            pricing,
            output_dir,
            source_hash,
            dry_run,
            timeout_seconds,
        )
        for cell in cells
    ]


def build_parser() -> argparse.ArgumentParser:
    """Return the runner command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="use mock telemetry and make no LLM harness calls",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="invoke paid harness calls; never use this mode in CI",
    )
    parser.add_argument(
        "--matrix-subset",
        action="append",
        metavar="HARNESS:CONDITION:TASK",
        help="run one exact matrix triple; repeat for more triples",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="result directory; defaults under benchmarks/agent/results",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=1800,
        help="per-harness timeout for live mode",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected matrix and print one machine-readable summary."""

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    dry_run = bool(args.dry_run)
    output_dir = args.out_dir or (
        AGENT_ROOT / "results" / ("v2-dry-run" if dry_run else "v2-live")
    )
    try:
        records = run_benchmark(
            dry_run=dry_run,
            output_dir=output_dir.resolve(),
            matrix_subsets=args.matrix_subset,
            timeout_seconds=args.timeout_seconds,
        )
    except (BenchmarkError, OSError, SchemaValidationError) as error:
        print(f"agent benchmark failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "cell_runs": len(records),
                "dry_run": dry_run,
                "out_dir": str(output_dir.resolve()),
                "verifier_failures": sum(not record["pass"] for record in records),
                "verifier_passes": sum(record["pass"] for record in records),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

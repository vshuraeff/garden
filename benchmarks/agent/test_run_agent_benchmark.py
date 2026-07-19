from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from run_agent_benchmark import (
    FIXTURE_ROOT,
    PRICING_PATH,
    PROTOCOL_PATH,
    RESULT_SCHEMA_PATH,
    SchemaValidationError,
    TokenUsage,
    build_cells,
    calculate_cost,
    calculate_telemetry_cost,
    copy_fixture,
    install_garden_locally,
    load_toml,
    mock_claude_code_telemetry,
    mock_codex_telemetry,
    parse_claude_code_telemetry,
    parse_codex_telemetry,
    run_benchmark,
    validate_result_record,
)


def sample_record() -> dict[str, object]:
    return {
        "schema_version": "2",
        "benchmark_version": "2",
        "harness": "claude_code",
        "condition": "garden_off",
        "task_id": "T1",
        "repetition": 1,
        "models": {"main": "claude-opus-4-8", "subagents": ["claude-sonnet-5"]},
        "pass": False,
        "wall_clock_seconds": 1.25,
        "tokens": {"input": 1100, "output": 240, "cache": 650},
        "cost_usd": 0.031815,
        "diff_size": {
            "lines_added": 0,
            "lines_removed": 0,
            "files_changed": 0,
        },
        "provenance": {
            "cli_version": "dry-run-mock/claude_code-v1",
            "model_ids": ["claude-opus-4-8", "claude-sonnet-5"],
            "fixture_hash": "a" * 64,
            "prompt_hash": "b" * 64,
            "timestamp": "2026-07-18T10:00:00Z",
        },
        "raw_telemetry_ref": "raw/sample.json",
    }


class TelemetryParsingTests(unittest.TestCase):
    def test_claude_code_result_usage_is_normalized(self) -> None:
        models = {"main_model": "claude-opus-4-8", "subagent_models": ["claude-sonnet-5"]}

        telemetry = parse_claude_code_telemetry(
            mock_claude_code_telemetry(models)
        )

        self.assertEqual(TokenUsage(1100, 240, 650), telemetry.tokens)
        self.assertEqual(1.25, telemetry.wall_clock_seconds)
        self.assertEqual(("claude-opus-4-8", "claude-sonnet-5"), telemetry.model_ids)
        self.assertEqual(TokenUsage(1000, 200, 600), telemetry.per_model_tokens["claude-opus-4-8"])

    def test_codex_completed_turn_separates_cached_input(self) -> None:
        models = {
            "main_model": "gpt-5.6-sol",
            "subagent_models": ["gpt-5.6-terra", "gpt-5.6-luna"],
        }

        telemetry = parse_codex_telemetry(mock_codex_telemetry(models))

        self.assertEqual(TokenUsage(1000, 300, 500), telemetry.tokens)
        self.assertEqual(1.5, telemetry.wall_clock_seconds)
        self.assertEqual(
            ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"),
            telemetry.model_ids,
        )


class PricingTests(unittest.TestCase):
    def test_million_token_arithmetic_uses_all_three_rates(self) -> None:
        pricing = load_toml(PRICING_PATH)["models"]

        cost = calculate_cost(
            TokenUsage(1_000_000, 1_000_000, 1_000_000),
            pricing["claude-opus-4-8"],
        )

        self.assertEqual(91.5, cost)

    def test_per_model_mock_cost_uses_main_and_subagent_rates(self) -> None:
        pricing = load_toml(PRICING_PATH)["models"]
        models = {"main_model": "claude-opus-4-8", "subagent_models": ["claude-sonnet-5"]}
        telemetry = parse_claude_code_telemetry(
            mock_claude_code_telemetry(models)
        )

        cost = calculate_telemetry_cost(telemetry, pricing, "claude-opus-4-8")

        self.assertAlmostEqual(0.031815, cost)


class ProtocolAndSchemaTests(unittest.TestCase):
    def test_protocol_expands_to_preregistered_36_runs(self) -> None:
        protocol = load_toml(PROTOCOL_PATH)

        cells = build_cells(protocol)

        self.assertEqual(36, len(cells))
        self.assertEqual(2, len(protocol["matrix"]["harnesses"]))
        self.assertEqual(2, len(protocol["matrix"]["conditions"]))
        self.assertEqual(3, len(protocol["matrix"]["tasks"]))
        self.assertEqual("pricing.toml", protocol["pricing_file"])
        self.assertEqual("schemas/result.schema.json", protocol["result_schema"])

    def test_pricing_contains_every_registered_model(self) -> None:
        pricing = load_toml(PRICING_PATH)

        self.assertEqual(
            {
                "claude-opus-4-8",
                "claude-sonnet-5",
                "gpt-5.6-sol",
                "gpt-5.6-terra",
                "gpt-5.6-luna",
            },
            set(pricing["models"]),
        )

    def test_sample_result_matches_committed_schema(self) -> None:
        json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))

        validate_result_record(sample_record())

    def test_schema_rejects_unknown_fields_and_invalid_hashes(self) -> None:
        record = sample_record()
        record["unexpected"] = True
        with self.assertRaises(SchemaValidationError):
            validate_result_record(record)

        record = sample_record()
        record["provenance"]["fixture_hash"] = "not-a-hash"
        with self.assertRaises(SchemaValidationError):
            validate_result_record(record)


class FixtureAndPipelineTests(unittest.TestCase):
    def test_pristine_fixture_suite_passes_without_t1_injection(self) -> None:
        self.assertFalse((FIXTURE_ROOT / "tests" / "test_t1_regression.py").exists())
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
                "-v",
            ],
            cwd=FIXTURE_ROOT,
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_garden_on_setup_installs_local_project_surfaces(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agent-benchmark-garden-") as temporary:
            target = Path(temporary) / "fixture"
            copy_fixture(target)

            plugin_copy = install_garden_locally(target)

            self.assertEqual(target / "plugins" / "garden", plugin_copy)
            self.assertTrue((plugin_copy / "hooks" / "hooks.json").is_file())
            self.assertTrue((target / ".garden.toml").is_file())
            self.assertTrue((target / ".claude" / "rules" / "garden.md").is_file())
            self.assertTrue((target / "AGENTS.md").is_file())
            self.assertTrue(
                (target / ".codex" / "agents" / "garden-reviewer.toml").is_file()
            )
            self.assertTrue(
                (target / ".agents" / "plugins" / "marketplace.json").is_file()
            )

    def test_dry_run_subset_writes_three_schema_valid_records(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agent-benchmark-test-") as temporary:
            output_dir = Path(temporary) / "results"

            records = run_benchmark(
                dry_run=True,
                output_dir=output_dir,
                matrix_subsets=["claude_code:garden_off:T1"],
            )

            self.assertEqual(3, len(records))
            self.assertTrue(all(record["pass"] is False for record in records))
            result_paths = sorted(output_dir.glob("*.json"))
            self.assertEqual(3, len(result_paths))
            for result_path in result_paths:
                record = json.loads(result_path.read_text(encoding="utf-8"))
                validate_result_record(record)
                self.assertTrue((output_dir / record["raw_telemetry_ref"]).is_file())


if __name__ == "__main__":
    unittest.main()

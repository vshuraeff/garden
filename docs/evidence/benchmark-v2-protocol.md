# GARDEN agent-value benchmark v2 protocol

Benchmark v2 measures the functional result, time, token use, estimated cost, and diff size of agent changes with and without the GARDEN plugin. This file preregisters the infrastructure protocol; [`protocol-v2.toml`](../../benchmarks/agent/protocol-v2.toml) is the machine-readable source.

## Why this design

The paired design isolates the causal effect of the GARDEN plugin. For a given harness, task, and repetition, garden-on and garden-off receive the same prompt, fixture source, task precondition, verifier, model configuration, and repetition count. The only condition difference is that garden-on has the repository-local plugin, `.garden.toml`, and its project hook and instruction surfaces, while garden-off has none of them.

## Matrix

A cell is one `(harness, condition, task)` triple. The matrix has 2 harnesses, 2 conditions, and 3 tasks, producing 12 cells. Each cell runs 3 times, for 36 total cell-runs.

| Dimension | Registered values |
| --- | --- |
| Harness | `claude_code`, `codex` |
| Condition | `garden_on`, `garden_off` |
| Task | `T1`, `T2`, `T3` |
| Repetitions per cell | 3 |
| Cells | 12 |
| Total cell-runs | 36 |

## Harnesses

`claude_code` runs in headless mode with `claude -p --output-format json`. Its main model is `claude-opus-4-8`, and its registered subagent model is `claude-sonnet-5`. The runner adds the explicit main-model and local-plugin arguments when it constructs a live command.

`codex` runs in headless mode with `codex exec --json`. Its main model is `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"`; its registered subagent models are `gpt-5.6-terra` and `gpt-5.6-luna`.

These forward model IDs are protocol inputs, not claims of current public availability. A real run must first confirm CLI support and replace estimated pricing from one dated source.

## Conditions

For `garden_on`, the runner copies `plugins/garden` into the ephemeral fixture, initializes `.garden.toml`, and installs the plugin's Claude and Codex project surfaces. The copied package contains the plugin hooks. For `garden_off`, the runner makes no garden-related additions: no installed package, `.garden.toml`, hook wiring, or GARDEN project instructions.

Condition setup is committed into the cell's initial git baseline before the harness runs. This prevents condition scaffolding from being counted as an agent-authored diff. The fixture source, prompt, verifier, task precondition, harness model settings, and repetition count remain identical between the two conditions.

## Fixture and task isolation

Every cell-run starts from a new copy of the project described by [`fixture/CONTEXT.md`](../../benchmarks/agent/fixture/CONTEXT.md). The runner excludes benchmark-only prompt and verifier files from the agent workdir, applies condition setup, applies the task precondition, and creates a fresh git commit.

The checked-in fixture has a passing stdlib `unittest` suite. T1 requires a pre-existing failing reproducer, so the runner injects `tests/test_t1_regression.py` before the T1 baseline commit. The same injected file is used in both conditions. T2 and T3 use the clean fixture baseline. This keeps the fixture clean for tasks that do not require a failing starting test while satisfying T1's reproduce-first contract.

## Tasks

| Task | Difficulty | Registered change | Prompt | Verifier |
| --- | --- | --- | --- | --- |
| `T1` | Easy | Point bugfix for coupon-code normalization inside pricing. | [`T1.md`](../../benchmarks/agent/fixture/prompts/T1.md) | [`T1.py`](../../benchmarks/agent/fixture/verify/T1.py) |
| `T2` | Medium | Reserved-order feature crossing exactly the orders-to-inventory capability boundary. | [`T2.md`](../../benchmarks/agent/fixture/prompts/T2.md) | [`T2.py`](../../benchmarks/agent/fixture/verify/T2.py) |
| `T3` | Hard | Checkout migration across orders, inventory, pricing, and notify while preserving the public `checkout` signature and CLI JSON format. | [`T3.md`](../../benchmarks/agent/fixture/prompts/T3.md) | [`T3.py`](../../benchmarks/agent/fixture/verify/T3.py) |

Prompt text is read verbatim from these files for every matching harness and condition. Each verifier is deterministic, stdlib-only, garden-agnostic, and determines pass/fail solely from functional and structural task requirements.

## Metrics and result contract

One result record follows [`schemas/result.schema.json`](../../benchmarks/agent/schemas/result.schema.json). It contains the harness, condition, task, repetition, main and subagent model IDs, verifier pass/fail, wall-clock seconds, token counts, estimated cost, diff size, provenance, and a relative reference to captured raw telemetry.

| Metric | Registered source |
| --- | --- |
| `pass` | Verifier exit code; zero passes and nonzero fails. |
| `wall_clock_seconds` | Measured harness subprocess duration; dry-run uses the duration in mock telemetry. |
| `tokens.input` | Claude result `usage.input_tokens` or per-model `modelUsage.<model>.inputTokens`; Codex `turn.completed.usage.input_tokens` minus cached input when cache is a reported subset. |
| `tokens.output` | Claude result `usage.output_tokens` or per-model `modelUsage.<model>.outputTokens`; Codex `turn.completed.usage.output_tokens`, with `reasoning_output_tokens` retained in raw telemetry. |
| `tokens.cache` | Claude result `usage.cache_read_input_tokens` plus `usage.cache_creation_input_tokens`, or corresponding camel-case per-model fields; Codex `turn.completed.usage.cached_input_tokens`. |
| `diff_size` | Added lines, removed lines, and changed files from `git diff --numstat HEAD` after intent-to-add exposes untracked files. |
| `cost_usd` | Parsed per-model token counts multiplied by the input, output, and cache USD-per-million rates in [`pricing.toml`](../../benchmarks/agent/pricing.toml). Aggregate telemetry falls back to the registered main-model rate. |

Claude telemetry is a single `--output-format json` result object. Codex telemetry is the `exec --json` JSONL event stream, with aggregate usage read from `turn.completed`. The named fields are best-effort preregistration against the CLI formats checked while scaffolding; raw telemetry is retained so a version-specific parser adjustment remains auditable.

The pricing snapshot date is `2026-07-18`. Every rate is explicitly estimated because no public pricing source exists for the registered forward IDs. The notes in `pricing.toml` record the flagship, large, mid, and small tier extrapolation and require replacement before a real run.

## Garden inspection

Running the deterministic GARDEN inspector against an agent diff is not part of task success. Pass/fail comes only from the functional verifier. A later result extension may record garden inspection fields for observational analysis, but those fields must not change `pass`.

## Execution and out of scope

`run_agent_benchmark.py --dry-run` exercises all 36 cells with representative mock telemetry, task verifiers, diff measurement, pricing, and result-schema validation. Mock harnesses do not edit the fixture, so verifier failures in dry-run records describe the unchanged task baseline and do not make the infrastructure run fail.

Real Claude Code or Codex benchmark calls, public model and price confirmation, paid execution, statistical analysis, and conclusions about agent value are out of scope. They require a separate future task and must not run in CI.

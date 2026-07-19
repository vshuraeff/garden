# GARDEN agent-value benchmark v2

The live run on 2026-07-19 executed all 36 registered cell-runs. Every task
passed under both `garden_on` and `garden_off`. The run confirms the benchmark
mechanics end to end, but the all-pass result shows no task-success advantage
for either condition on this corpus.

## Pinned revision and toolchain

[`benchmarks/agent/protocol-v2.toml`](../../benchmarks/agent/protocol-v2.toml)
and
[`docs/evidence/benchmark-v2-protocol.md`](benchmark-v2-protocol.md)
are the preregistered machine-readable and narrative protocols. The result
records identify benchmark and schema version `2`, fixture hash
`e06303c30bb871da1509f22ed9476372a44e599eb82429e35c5a6537d8e818d4`,
and one task-specific prompt hash for each of T1, T2, and T3.

The `claude_code` cells used Claude Code CLI `2.1.215`, main model
`claude-opus-4-8`, and registered subagent model `claude-sonnet-5`. The `codex`
cells used Codex CLI `0.144.5`, main model `gpt-5.6-sol`, and registered
subagent models `gpt-5.6-terra` and `gpt-5.6-luna`. These values come from the
committed result records.

The result schema does not record a repository commit or plugin manifest
version. This publication therefore pins the result bytes through
`benchmarks/results/v2-live/sha256sums.txt` and records the embedded fixture,
prompt, CLI, and model provenance; it does not retrospectively claim an
executable repository revision for the live run.

The `codex` cells were run before the amendment to PR #28 that fixed invalid
Claude model IDs in the protocol. That amendment did not touch the Codex side
of the protocol, so this is a provenance and timing note, not a validity
concern for the Codex results. The `claude_code` cells were run after the
amendment.

## Matrix and measurement

The matrix contains two harnesses (`claude_code`, `codex`), two conditions
(`garden_on`, `garden_off`), three tasks (T1, T2, T3), and three repetitions per
cell: `2 x 2 x 3 x 3 = 36` cell-runs. Pass/fail comes from the registered task
verifier. Token totals below add each result's input, output, and cache tokens.
Wall-clock time is the measured harness duration.

`cost_usd` is extrapolated from
[`benchmarks/agent/pricing.toml`](../../benchmarks/agent/pricing.toml). Every
cost in this report is estimated and is not an actual billing figure.

## Results

Each row reports the pass fraction and median of its three repetitions. Token
and wall-clock values are computed from the committed JSON records; estimated
cost is rounded to three decimal places.

| Harness | Condition | Task | Pass | Wall-clock median (s) | Token total median | Estimated cost median (USD) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `claude_code` | `garden_off` | T1 | 3/3 | 30.6 | 171,885 | 0.336 |
| `claude_code` | `garden_off` | T2 | 3/3 | 61.8 | 473,345 | 0.925 |
| `claude_code` | `garden_off` | T3 | 3/3 | 112.3 | 443,316 | 1.225 |
| `claude_code` | `garden_on` | T1 | 3/3 | 46.2 | 192,423 | 0.416 |
| `claude_code` | `garden_on` | T2 | 3/3 | 70.9 | 554,498 | 1.121 |
| `claude_code` | `garden_on` | T3 | 3/3 | 130.0 | 641,243 | 1.543 |
| `codex` | `garden_off` | T1 | 3/3 | 101.7 | 340,357 | 0.693 |
| `codex` | `garden_off` | T2 | 3/3 | 100.6 | 229,404 | 0.684 |
| `codex` | `garden_off` | T3 | 3/3 | 156.8 | 306,616 | 0.835 |
| `codex` | `garden_on` | T1 | 3/3 | 166.9 | 471,302 | 1.031 |
| `codex` | `garden_on` | T2 | 3/3 | 283.9 | 699,005 | 1.543 |
| `codex` | `garden_on` | T3 | 3/3 | 456.6 | 1,322,160 | 2.492 |

Aggregate values sum all nine cell-runs for each harness and condition. The
overhead column is `(garden_on / garden_off - 1) x 100`, computed before the
displayed values are rounded.

| Harness | Metric | `garden_off` sum | `garden_on` sum | `garden_on` overhead |
| --- | --- | ---: | ---: | ---: |
| `claude_code` | Tokens | 3,395,252 | 4,049,700 | +19.3% |
| `claude_code` | Wall-clock seconds | 594.1 | 722.1 | +21.5% |
| `claude_code` | Estimated cost (USD) | 7.55 | 9.13 | +20.9% |
| `codex` | Tokens | 3,037,102 | 6,869,327 | +126.2% |
| `codex` | Wall-clock seconds | 1,228.0 | 2,647.8 | +115.6% |
| `codex` | Estimated cost (USD) | 7.64 | 14.36 | +87.9% |

## Result integrity

`benchmarks/results/v2-live/` contains the 36 committed result JSON files. Its
`sha256sums.txt` lists one SHA-256 digest for each result file, sorted by
filename. The pass fractions, medians, sums, and overhead percentages in this
report were recomputed from those committed files rather than copied from
harness narration. The JSON files and checksum list are the committed raw
evidence for this report.

## Negative results and deviations

No task-outcome delta was observed: all 18 `garden_on` and all 18 `garden_off`
cell-runs passed. The benchmark therefore does not demonstrate that GARDEN
improves task success on T1-T3. This is a ceiling result, not evidence that the
conditions are equivalent on other tasks or repositories.

The protocol amendment timing differs by harness, as recorded above: Codex ran
before the PR #28 Claude-model-ID amendment and Claude Code ran after it. The
changed fields were confined to the Claude side, so the timing difference does
not invalidate the Codex cells.

Cost is a protocol-rate extrapolation, not observed billing. It remains useful
for consistent within-protocol comparison, but it must not be read as the
amount charged by a provider.

## Limitations

Each cell has only three repetitions, and every run uses one synthetic fixture
codebase. Every cell passes in both conditions, producing a ceiling effect.
This benchmark cannot show an outcome advantage for GARDEN on these tasks; it
can only measure enforcement overhead when the tasks are already solvable in
both conditions. The sample is too small and narrow to estimate effects for
other repositories, task distributions, harness versions, or models.

The benchmark mechanics worked end to end: harness invocation, condition
setup, telemetry capture, cost calculation, verifiers, and result-schema
validation. This run demonstrates no task-outcome advantage for `garden_on`
over `garden_off`; what it measures is enforcement overhead in tokens,
wall-clock time, and estimated cost.

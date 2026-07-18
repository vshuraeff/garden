# GARDEN Benchmark v1

Benchmark v1 records deterministic GARDEN plugin behavior on fixed, checked-in
corpora. It contains no LLM or agent runs. Results apply to the listed fixtures,
operators, revision, and toolchain.

## Pinned revision and toolchain

[`benchmarks/toolchain.toml`](../../benchmarks/toolchain.toml) records repository
commit `e8d5bc838ae40ba5c76fbe79c895c55da748e896` as the revision against which the
corpus and labels were authored. Runtime identity is pinned separately to the
`plugins` subtree tree hash `817bdf4b195bf93b421f43dca9836215f5c42eaf`, GARDEN
plugin version `0.7.2`, and seed `20260714`. The declared portability matrix is
Ubuntu and macOS with Python 3.11 and 3.14. The committed run records its locally
observed platform and Python version in `metadata.json` and `summary.json`.

### v1.1 protocol (2026-07-17)

The active toolchain sets `benchmark_version = "1.1"` and
`protocol_file = "protocol-v1.1.toml"`; it retains the pinned `plugins` subtree
tree hash `817bdf4b195bf93b421f43dca9836215f5c42eaf` and plugin version `0.7.2`.
[`benchmarks/protocol-v1.1.toml`](../../benchmarks/protocol-v1.1.toml) is the
v1.1 protocol, while [`benchmarks/protocol-v1.toml`](../../benchmarks/protocol-v1.toml)
remains the historical v1 protocol.

## Hypotheses and preregistered thresholds

The thresholds below were fixed in
[`benchmarks/protocol-v1.toml`](../../benchmarks/protocol-v1.toml) during phase 1,
before the committed Benchmark v1 run. They were not changed in response to the
measured results.

| Suite | Preregistered requirement |
| --- | --- |
| Detection | Configured classification error no greater than `0.05`; absolute error reduction at least `0.10`; relative error reduction at least `0.50`; no project-type mean regression; at least 6 of 12 repositories improve. |
| Detection classes | Source and test false-positive and false-negative rates each no greater than `0.05`; capability exact accuracy at least `0.95`; an incomplete scan cannot pass. |
| Evidence | All 32 supported defect cases detected with their expected diagnostic family; none of 16 clean controls blocked. |
| Mutations | All 48 must-block mutations killed; none of 12 clean controls blocked; all 8 preregistered gap probes reported separately. |
| Migration | All 12 fixtures pass each of five properties; all 4 invalid fixtures satisfy their preregistered failure behavior and atomicity check; normalized output is identical across the four declared platform and Python combinations. |

The detection hypothesis is that configured project metadata reduces
classification error on this corpus while satisfying the class-specific limits.
The other hypotheses are that the enumerated evidence defects and must-block
mutations meet their exact corpus thresholds, and that migration meets every
listed reproducibility property. A failed hypothesis remains a reported result.

### v1.1 migration and matrix requirements (2026-07-17)

Protocol v1.1 adds
`semantic_migration_invariant_required = true` under `[migration]` and a
`[matrix_identity]` section with `required_combinations = 4` and
`enforced_in = "ci-matrix-comparison"`. Intentional classification changes are
declared in
[`benchmarks/corpus/migration-intentional-changes.json`](../../benchmarks/corpus/migration-intentional-changes.json),
which currently contains the reviewed `N-LEGACY-NAMING-REGISTRY`,
`R-component-contract`, and `A-colocated-tests` entries.

The v1.1 migration requirement has three invariants:

1. (a) `semantic-migration-invariant` computes the symmetric difference of
   normalized `(severity, rule, path, message)` finding-instance keys from
   legacy and configured inspection. Every difference fails unless its rule is
   in the registry with a direction that permits it: `removed-in-configured`,
   `added-in-configured`, or `either` as applicable.
2. (b) The intentional-changes registry is valid only when every entry has
   exactly the non-empty string fields `rule`, `direction`, `reason`, and
   `source`; its direction is one of those three values; and no rule appears
   more than once.
3. (c) `tree-atomicity` passes only when the migrated tree preserves the hashes
   of every source-tree file other than configuration and contains exactly the
   original file set plus `.garden.toml`.

## Corpus and label procedure

The detection corpus contains 12 synthetic repositories: six project types,
each with conventional and adversarial layouts. Each repository has 12 labels
shared by legacy and configured conditions: six production paths, two test
paths, and four negatives. Labels were hand-authored before running GARDEN and
were not derived from its classifications. One representative label file is
[`python-service-conventional/labels.json`](../../benchmarks/corpus/detection/python-service-conventional/labels.json).

The evidence corpus has 48 isolated cases: four defects and two clean controls
for each of eight operators. Case expectations and diagnostic families are in
[`cases.json`](../../benchmarks/corpus/evidence/cases.json). The mutation corpus
has 68 explicit rows: 48 must-block mutations, 8 gap probes, and 12 clean
controls. Their owning gates and fixed signatures are in
[`manifest.json`](../../benchmarks/mutations/manifest.json). Migration reuses
the 12 legacy detection trees and adds four invalid cases registered in
[`migration-invalid/cases.json`](../../benchmarks/corpus/migration-invalid/cases.json).

Corpus labels, mutation classifications, expected signatures, and invalid-case
expectations are checked-in inputs. The runners compare measured behavior with
those inputs without rewriting them.

## Reproduction

Run the complete benchmark and validate its committed artifacts:

```sh
uv run --no-project benchmarks/run.py
uv run --no-project benchmarks/run.py --check
uv run --no-project benchmarks/validate_results.py
```

The `--check` command permits the full repository commit to advance, but fails
closed if the current `plugins` subtree differs from its pinned tree hash. It
ignores historical repository and run-commit provenance fields when comparing
behavioral results.

Run individual suites when investigating one result surface:

```sh
uv run --no-project benchmarks/run_detection.py
uv run --no-project benchmarks/run_evidence.py
uv run --no-project benchmarks/run_mutations.py
uv run --no-project benchmarks/run_migration.py
```

For v1.1, the intentional-changes registry is
[`benchmarks/corpus/migration-intentional-changes.json`](../../benchmarks/corpus/migration-intentional-changes.json)
and the protocol is
[`benchmarks/protocol-v1.1.toml`](../../benchmarks/protocol-v1.1.toml). The
`validate` job runs `uv run --no-project benchmarks/run.py --check` on the
authoritative Ubuntu and Python 3.14 cell. Each of the four Ubuntu/macOS and
Python 3.11/3.14 cells runs `benchmarks/run.py --out-dir`, normalizes its
results with `benchmarks/compare_matrix.py normalize`, and uploads its bundle.
The `benchmark-matrix-compare` job downloads all four normalized bundles and
runs `benchmarks/compare_matrix.py compare` with all four `--cell-dir`
arguments to assert cross-matrix identity.

## Results

<!-- BEGIN GENERATED RESULTS -->
### Suite status

| Suite | Status | Records | Passed records | Failed records | Incomplete |
| --- | --- | ---: | ---: | ---: | ---: |
| detection | pass | 288 | 181 | 107 | 0 |
| evidence | pass | 48 | 48 | 0 | 0 |
| mutations | pass | 68 | 68 | 0 | 0 |
| migration | pass | 64 | 64 | 0 | 0 |

Top-level result: **pass**.

### Matrix identity

| Property | Value |
| --- | --- |
| `required_combinations` | 4 |
| `observed_combinations` | 1 |
| `identical` | not applicable |
| `enforced_in` | ci-matrix-comparison |

### Thresholds and actual values

#### Detection

| Protocol key | Preregistered value | Actual metric | Actual value |
| --- | ---: | --- | ---: |
| `configured_max_error_rate` | 0.05 | `configured_error_rate` | 0 |
| `min_absolute_error_reduction` | 0.1 | `absolute_error_reduction` | 0.743056 |
| `min_relative_error_reduction` | 0.5 | `relative_error_reduction` | 1 |
| `allow_project_type_mean_regression` | false | `project_type_mean_regression_present` | false |
| `min_improved_repositories` | 6 | `improved_repositories` | 12 |
| `repository_count` | 12 | `repository_count` | 12 |
| `source_max_false_positive_rate` | 0.05 | `source_false_positive_rate` | 0 |
| `source_max_false_negative_rate` | 0.05 | `source_false_negative_rate` | 0 |
| `test_max_false_positive_rate` | 0.05 | `test_false_positive_rate` | 0 |
| `test_max_false_negative_rate` | 0.05 | `test_false_negative_rate` | 0 |
| `capability_min_exact_accuracy` | 0.95 | `capability_exact_accuracy` | 1 |
| `incomplete_scan_counts_as_pass` | false | `incomplete_scan_present` | false |

#### Evidence

| Protocol key | Preregistered value | Actual metric | Actual value |
| --- | ---: | --- | ---: |
| `defect_recall_required` | 32 | `defects_detected` | 32 |
| `defect_total` | 32 | `defect_total` | 32 |
| `false_blocks_allowed` | 0 | `clean_false_blocks` | 0 |
| `clean_total` | 16 | `clean_total` | 16 |

#### Mutations

| Protocol key | Preregistered value | Actual metric | Actual value |
| --- | ---: | --- | ---: |
| `killed_required` | 51 | `must_block_killed` | 51 |
| `mutation_total` | 51 | `must_block_total` | 51 |
| `clean_blocked_allowed` | 0 | `clean_blocked` | 0 |
| `clean_total` | 13 | `clean_total` | 13 |
| `gap_probes_required` | 4 | `gap_probe_total` | 4 |
| `gap_probe_total` | 4 | `gap_probe_total` | 4 |

#### Migration

| Protocol key | Preregistered value | Actual metric | Actual value |
| --- | ---: | --- | ---: |
| `cases_required_per_property` | 12 | `minimum_property_pass_count` | 12 |
| `case_total` | 12 | `valid_fixture_count` | 12 |
| `property_count` | 5 | `property_count` | 5 |
| `failure_atomicity_required` | 4 | `failure_atomicity_passed` | 4 |
| `failure_atomicity_total` | 4 | `failure_atomicity_total` | 4 |

### Gate-family ablation accounting

Ablations use only the checked-in must-block mutation rows and mapped, observed rule IDs. They do not measure outcomes outside this corpus.

| Family | Mapped rules | Observed rules | Computed |
| --- | ---: | ---: | --- |
| D | 1 | 1 | yes |
| N | 10 | 8 | yes |
| G | 0 | 0 | no |
| A | 1 | 1 | yes |
| R | 3 | 3 | yes |
| E | 0 | 0 | no |

| Family | Targeted killed / total | Targeted recall | Standalone coverage | Leave-one-out loss |
| --- | ---: | ---: | ---: | ---: |
| A | 0 / 0 | not applicable | 0 / 51 | 0 |
| D | 1 / 1 | 1 | 1 / 51 | 1 |
| N | 10 / 10 | 1 | 10 / 51 | 10 |
| R | 2 / 2 | 1 | 2 / 51 | 2 |

Families without observed mapped rules: G, E.

### Result integrity and reproduction

`summary.json` SHA-256: `5c6a2f9fcaffd0e29c83e717151691fd1d3d4c99e0221e12815ca10bc0c54bdb`

```sh
uv run --no-project benchmarks/run.py
uv run --no-project benchmarks/run.py --check
uv run --no-project benchmarks/validate_results.py
```
<!-- END GENERATED RESULTS -->

## Negative results and deviations

Migration `normalized-inspect-parity` measured 0/12 in the initial run and the
0.7.2 re-run. The initial result included a new `N-CONTEXT-MISSING` finding
because the migrated `.garden.toml` inherited
`documentation.root_context_required = true`. Version 0.7.2 fixes that behavior
by rendering `root_context_required = false` with an explicit TODO to enable it
after the project adds a root `CONTEXT.md`.

That fix is a protocol deviation relative to the preregistered migration
comparison, which permitted dropping only the legacy-deprecation advisory. The
remaining parity differences expose a flaw in the invariant: exact parity
effectively requires conserving legacy detection bugs. Configured mode
intentionally corrects legacy source and test misclassification, so the
post-migration finding set differs on `R-component-contract` and
`A-colocated-tests` even after `N-CONTEXT-MISSING` is removed. Corpus labels and
thresholds were not changed to manufacture parity.

Revising the invariant to parity modulo documented intentional detection fixes
is deferred to a future Benchmark v1.1 protocol cycle. Benchmark v1 retains the
failed migration result as measured.

The committed run exercises one local platform and Python combination, not the
four declared matrix cells. Cross-matrix normalized-output identity is therefore
not established by this artifact and counts as unsatisfied in the migration
summary.

### v1.1 (2026-07-17)

Benchmark v1.1 implements the deferred revision: the migration comparison is
now parity modulo the documented, reviewed intentional-changes registry through
the semantic-migration invariant, rather than exact, unqualified finding
parity. The invariant compares normalized finding keys, not byte-for-byte
report output. The v1 exact-parity failure remains the honest measurement under
the v1 protocol; it is neither retracted nor superseded, because v1.1 changes
the invariant's scope rather than the v1 measurement.

Cross-matrix normalized-output identity changes from structurally unmeasurable
for the v1 single committed cell to a CI-measured v1.1 property through the
four-cell `benchmark-matrix-compare` job. The committed artifact in this
repository still reflects one local cell; only CI runs and asserts the four-cell
comparison.

## Known gaps

The eight gap probes are reporting rows, not must-block mutation catches.

| Probe | Classification | Measured outcome |
| --- | --- | --- |
| Missing capability contract | `detect_only` | `R-component-contract` reported; gate did not block. |
| Missing mapped test | `detect_only` | `A-colocated-tests` reported; gate did not block. |
| `scan.roots` walk restriction | `known_unenforced` | No preregistered enforcement signature; gate did not block. |
| `contracts.required_for` | `known_unenforced` | No dedicated enforcement signature; gate did not block. |
| `boundaries.public` | `known_unenforced` | No dedicated enforcement signature; gate did not block. |
| Structured exceptions | `known_unenforced` | Contract advisory remained present; gate did not block. |
| Markers resolution | `known_unenforced` | No preregistered enforcement signature; gate did not block. |
| Explicit boundary and state policy | `known_unenforced` | No preregistered enforcement signature; gate did not block. |

## Limitations

Benchmark v1 evaluates deterministic GARDEN behavior only: configured path,
test, and capability classification on a fixed synthetic corpus; detection of
enumerated mutations by the checked-in gate suite; and reproducibility of
configuration migration. The fixtures are constructed rather than randomly
sampled from software repositories, so the reported rates describe this corpus
and do not establish population-wide accuracy or defect-detection ability.

Agent-effectiveness remains unmeasured. Benchmark v1 contains no LLM-agent runs.
It cannot support claims about agent task success, regressions introduced by
agents, token consumption, wall-clock task time, files opened, search effort,
human review effort, or rollback frequency. It also cannot attribute an agent
outcome to an individual GARDEN principle. Those outcomes remain EXPERIMENTAL
until a preregistered agent-task benchmark is run.

The intentional-changes registry
[`benchmarks/corpus/migration-intentional-changes.json`](../../benchmarks/corpus/migration-intentional-changes.json)
is itself a curated, human-reviewed artifact. An unreviewed or incorrect entry
could mask a real regression as an intentional change, so registry entries need
the same review scrutiny as corpus labels.

A killed mutation shows that the named gate detects that specific, checked-in
defect operator at the pinned repository revision. It is not evidence that the
gate detects every defect in the same category, and a passing gate is not proof
that defects are absent. Advisory and currently unenforced rules are reported
separately and are not counted as blocking catches.

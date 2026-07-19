# Changelog

## 0.11.1

- Fixed invalid Claude model IDs (`opus-4.8` and `sonnet-5`) in the agent-value
  benchmark v2 protocol and pricing config, replacing them with
  `claude-opus-4-8` and `claude-sonnet-5`.

## 0.11.0

- Added the agent-value benchmark v2 scaffold: preregistered
  `benchmarks/agent/protocol-v2.toml`, `pricing.toml`, the synthetic shop fixture
  with capabilities, tests, prompts, and T1-T3 verifiers, the result schema, and
  the dry-run-only `run_agent_benchmark.py` runner; it makes no live agent or LLM
  invocation and produces no agent-effectiveness results.
- Added `docs/evidence/benchmark-v2-protocol.md` and CI coverage running
  `unittest discover -s benchmarks/agent` for the dry-run scaffold.

## 0.10.2

- Added `docs/development/enforcement-roadmap.md`, a design-only roadmap for
  markers-based capability resolution (`gap-07`) and explicit boundary/state-policy
  enforcement (`gap-08`); this release changes neither runtime behavior nor the rule
  registry.

## 0.10.1

- Added `SECURITY.md`, documenting the `garden-check.sh` and `garden-prompt.sh`
  hooks, their fail-open status contract, and `garden_mcp.py`'s two read-only
  stdio tools with client-root and symlink confinement.
- Documented bounded walk and file-read limits, POSIX-only scope with Windows
  unsupported, and runtime supply-chain constraints: hooks use `uv run
  --no-project` with standard-library and local modules, without dependency
  resolution, installation, or third-party fetch; `plugin_version.py` remains
  maintainer-only tooling.
- Recorded that `test_garden_security.py` exercises capability-directory
  symlink escapes, TOCTOU file swaps, pathological glob matching, malformed
  UTF-8, and interrupted atomic writes.
- Recorded a grep-based tools scan with no `eval(`, `exec(`, `os.system`,
  `socket.`, or `urllib.request` occurrences.
- Added GitHub Security-tab reporting through **Report a vulnerability** rather
  than public issues.

## 0.9.1

- Added installed-harness smoke tests that install the packaged plugin into
  isolated Claude Code and Codex configurations and exercise the full offline
  lifecycle with real, pinned CLI binaries: marketplace registration, plugin
  installation, discovery listings, and MCP server listing.
- Added installed-copy behavioral checks against the installed package: hook
  pass and fail round-trips, a real MCP handshake, and a `garden:start` /
  `garden:stop` project surface round-trip.
- Added `.github/workflows/integration.yml`, a scheduled integration workflow
  separate from per-PR validation, running on `workflow_dispatch`, a weekly
  schedule, and pull requests that modify plugin packaging paths, with pinned
  harness CLI versions.
- Documented the validated harness CLI versions (Claude Code CLI 2.1.212,
  Codex CLI 0.144.1) in `docs/reference/platform-support.md`.

## 0.9.0

- Replaced Benchmark v1.1's exact migration-parity invariant with a semantic
  invariant checked against the curated intentional-changes registry at
  `benchmarks/corpus/migration-intentional-changes.json`.
- Added protocol v1.1 (`benchmarks/protocol-v1.1.toml`) alongside the preserved
  historical v1 protocol (`benchmarks/protocol-v1.toml`).
- Made `matrix_identity` a separate, CI-measured invariant distinct from the
  migration suite, rather than an unmeasurable single-cell property.
- CI now reruns the benchmark against the current plugin tree with
  `benchmarks/run.py --check` on the authoritative cell.
- CI now produces normalized per-cell artifacts across all four declared
  platform/Python matrix cells, and the `benchmark-matrix-compare` job asserts
  cross-matrix identity.
- `benchmarks/lib` unit tests now run in CI.
- Preserved Benchmark v1's negative migration result, the exact-parity failure,
  as a historical record rather than retracting it.

## 0.8.5

- Expanded `REFERENCE_PAIRS` to eight documents, including the evidence
  registry, verification-gates how-to, and rule-registry and configuration
  references, so packaged references are self-contained.
- Relative links now rewrite deterministically to their packaged equivalents at
  render time.
- Unresolved source-only links now fail the build instead of passing through
  silently.
- Documents explicitly outside packaging scope now use an explicit list of
  canonical GitHub URLs instead of relative links.
- Packaged links now validate from their packaged locations rather than the
  source repository layout.
- `validate_package.py` now checks that the plugin tree is self-contained.
- Retargeted the bootstrap skill's documentation links to the packaged
  references.

## 0.8.4

- Added the canonical, hand-authored, machine-readable rule registry at
  `plugins/garden/rules/garden-rules.toml`, covering 42 rules and 12 runtime
  checks.
- Runtime alias tables, exception eligibility, and report coverage lists now
  derive from the registry instead of separate hand-maintained lists.
- Rules with `implementation = "partial"` now keep mechanized and manual
  coverage lists disjoint, so a rule cannot appear in both.
- Added generation of a compact rules digest with a registry drift check through
  `generate_rules_digest.py --check`.
- `validate_registry.py` now runs in CI to keep the registry, documentation,
  runtime alias table, and benchmark principle map consistent.
- Added `garden explain RULE_ID`.
- Benchmark principle-map consistency checks now cross-validate the registry.

## 0.8.3

- Inspection and hook processing build one `ProjectIndex` per inspection or hook
  event, using a single filesystem walk regardless of how many files changed.
  Traversal is restricted to configured `scan.roots`, overlapping roots are
  deduplicated, and missing roots produce `D-scan-root-missing` advisories
  instead of failing.
- `scan.exclude` patterns are pruned from the walk before any budget counting
  occurs, and nested contract artifacts are discovered at any depth rather than
  only at the top level.
- Scan budgets distinguish an elapsed-time budget, which is an operational
  advisory deadline, from deterministic budgets such as file and entry counts,
  which remain hard errors. Hook mode fails open when the elapsed-time budget is
  exceeded, restoring prior hook behavior, while `--strict` fails closed on
  incomplete analysis.
- Reports gain a top-level scan report object describing roots, exclusions,
  budgets, and completeness alongside the existing report fields.

## 0.8.2

- Runtime boundary enforcement resolves the most specific (longest-path)
  configured boundary per file. SemVer format is required only at boundaries
  with `versioning = "semver"`; private boundaries and contracts are never
  version-checked in configured projects. Declared contract artifacts are
  checked for presence at any depth, `accepted_names` are honored in capability
  checks, and unrecognized or uncovered evidence categories are surfaced as
  unknown manual findings.
- Exception validation requires known rule IDs that are eligible for
  suppression. Only canonical schema-v2 exceptions are accepted; `owner` and
  `reason` must be non-empty, and `review_after` must be ISO-8601 or an accepted
  marker value.
- Exception application suppresses matching findings while preserving their
  original finding data, and tracks them with a separate `suppressed` counter
  distinct from the existing five-counter summary. Expired exceptions never
  suppress and cause `--strict` to fail.
- Legacy behavior for unconfigured projects is unchanged and remains
  deprecated.

## 0.8.1

- Added `.garden.toml` configuration schema v2 with structured `[[boundaries]]`
  declarations for `path`, `kind`, `owner`, `versioning`, `contracts`, and
  `required_evidence`, with closed-enum validation for `kind`, `versioning`,
  and `required_evidence` categories, owner-required-except-private and
  contradiction checks, duplicate-path rejection, and project-root
  path-confinement validation, including symlink escapes for boundary and
  contract paths. Private boundaries reject `versioning`, `contracts`, and
  `required_evidence`; internal-versioned boundaries require non-none
  `versioning`.
- `garden config show` now renders effective schema-v2 boundary entries with
  per-field `file`/`default` origins, alongside existing v1 rendering.
- `garden migrate-config --to-schema 2 --owner NAME` converts valid schema-v1
  `boundaries.public` entries to `[[boundaries]]` entries with
  `kind = "public-api"` and `versioning = "none"`; `--owner` is required when
  public boundaries are declared, and using `--owner` without `--to-schema 2`
  is a clear CLI error.
- Schema v1 remains fully supported with no breaking changes to existing v1
  configs, CLI behavior, or report output; v2 rejects the v1 `[boundaries]`
  table, and v1 rejects the v2 `[[boundaries]]` array within a single config.
- Boundary declarations are parsed, validated, and rendered, but are not yet
  enforced by deterministic project inspection; enforcement is planned for a
  later release.

## 0.8.0

- `garden inspect` and `garden_inspect_project` now return a versioned
  schema-v2 report: `schema_version`, `scope`, `complete`, `configuration`,
  rule `coverage` (from `garden_rule_metadata.COVERAGE`), surfaced
  (unenforced) `exceptions`, and a five-counter `summary`
  (`errors`/`warnings`/`advisories`/`unknown`/`suppressed`).
- Findings carry current rule IDs alongside their runtime alias:
  `rule_id`, `runtime_alias`, `level`, `state`, `evidence`, `remediation`,
  and `confidence`, in addition to the legacy `rule`, `severity`, `path`,
  and `message` keys.
- `inspect --strict` now also fails on an inactive project, invalid
  configuration, incomplete analysis, and expired exceptions, not only on
  `error`-severity findings.
- MCP tool responses return the same schema-v2 report.
- Added `validate_report.py`, a deterministic validator for schema-v2
  reports, wired into CI to check the report the strict inspection produces.
- CI wording changed from "GARDEN self-audit" to "deterministic structural
  inspection" to match this report's declared scope; the `garden:audit`
  skill remains the separate checklist-based review.
- Legacy v1 report keys (`active`, `root`, `findings[].rule`,
  `findings[].severity`, `findings[].path`, `findings[].message`,
  `summary.errors`, `summary.advisories`) are unchanged, so existing v1
  consumers keep working against a v2 report.

## 0.7.3

- All active documentation migrated to the revised GARDEN principles; how-to
  guides now align with the review skill's lens names and workflow.
- Packaged references (`plugins/garden/references/review-procedure.md`)
  regenerated from the migrated source.
- Added `validate_migration_language.py`, a deterministic validator that flags
  stale pre-migration principle terminology in tracked documentation, with
  unit tests and a CI step.
- No runtime behavior changes.

## 0.7.2

- Migrated configurations now set `documentation.root_context_required = false`
  so migration does not introduce a new root-context requirement.
- Benchmark v1 records the migration parity result as an honest negative. Its
  detection, evidence, and mutation suites pass; migration remains failed
  because the preregistered invariant conserves legacy classification bugs.
- The ignored TypeScript vendor fixture is tracked in both legacy and configured
  corpus trees, with repository-local ignore negations preventing it from being
  masked by contributor Git configuration.
- Marketplace principle names, checklist implementation status, and README
  evidence claims now match the revised model and measured results.
- CI pins Ruff `0.15.21` for reproducible lint and format checks.

The preceding pre-1.0 revision included semantically incompatible principle
renames and configuration changes that shipped as minor version bumps under the
repository's pre-1.0 SemVer policy. Benchmark v1 is deterministic and non-agent;
agent-task effectiveness remains unmeasured.

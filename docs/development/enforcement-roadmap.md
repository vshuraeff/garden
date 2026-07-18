# Enforcement roadmap for markers and explicit state policy

This design defines an enforcement path for two GARDEN policies that the current
runtime does not enforce: marker-based capability resolution and explicit ownership of
mutable state. It specifies future schema, resolver, gate, fixture, and benchmark work.
It does not implement those changes or change the current rule registry.

## Markers capability-directory resolution

### Current state

`CAPABILITY_STRATEGIES` includes `"markers"` in
`plugins/garden/tools/config_schema.py:19-35`, and `_parse_capabilities` accepts that
value through the closed strategy enum in
`plugins/garden/tools/config_schema.py:499-541`. The corresponding runtime behavior is
not implemented. `_children_capability_directory` and
`_explicit_capability_directory` provide distinct algorithms in
`plugins/garden/tools/garden_rules.py:276-298`, while
`_CAPABILITY_DIRECTORY_RESOLVERS` maps `"markers"` to
`_no_capability_directory` in `plugins/garden/tools/garden_rules.py:302-308`.
Consequently `_capability_directory` returns no directory for the markers strategy;
there is no `_markers_capability_directory` function.

For projects that select `markers`, four registry rules need a stable capability identity
before their measurements can be associated with a capability. Their current registry
state is:

| Rule | Title | Level | Implementation | Configuration keys | Exception policy |
| --- | --- | --- | --- | --- | --- |
| `G-DISC-006` | Resolution effort | `EXPERIMENTAL` | `experimental` | `[]` | `not-allowed` |
| `A-LOC-006` | Change-locality profile | `EXPERIMENTAL` | `experimental` | `[]` | `not-allowed` |
| `R-REPL-008` | Replacement drill | `EXPERIMENTAL` | `experimental` | `[]` | `not-allowed` |
| `D-VER-008` | Gate-value measurement | `EXPERIMENTAL` | `experimental` | `[]` | `not-allowed` |

These values are defined in `plugins/garden/rules/garden-rules.toml:71-81`,
`plugins/garden/rules/garden-rules.toml:148-158`,
`plugins/garden/rules/garden-rules.toml:255-265`, and
`plugins/garden/rules/garden-rules.toml:358-368`. The fuller definitions require,
respectively, local measurement of traversal effort, change locality, replacement
drills, and gate value. They appear in `docs/reference/principles.md:101-106`,
`docs/reference/principles.md:197-202`, `docs/reference/principles.md:308-313`, and
`docs/reference/principles.md:422-427`; the generated plugin copy carries the same
definitions at `plugins/garden/references/principles.md:102-107`,
`plugins/garden/references/principles.md:198-203`,
`plugins/garden/references/principles.md:309-314`, and
`plugins/garden/references/principles.md:423-428`.

The benchmark records this missing behavior as
`gap-07-markers-resolution`. Its current owner is `garden-inspect-strict`, its
`expected_rule_id_or_signature` is `"none"`, and its `gap_probe_kind` is
`"known_unenforced"` in `benchmarks/mutations/manifest.json:547-555`.

### Marker semantics

A capability marker will be an exact sentinel filename in the directory that owns the
capability. The default filename will be `CAPABILITY.marker`. The future
`[capabilities]` schema will add a `marker_file` key so a repository can select another
existing sentinel without changing every capability directory:

```toml
[capabilities]
strategy = "markers"
roots = ["src", "services"]
marker_file = "CAPABILITY.marker"
```

`marker_file` will accept one filename, not a path or glob. Validation will reject an
empty value, `.`, `..`, path separators, absolute paths, and more than one path
component. Matching will be case-sensitive. If the key is omitted, the effective value
will be `CAPABILITY.marker`.

The marker must be a regular, non-symlink file. Its contents have no semantic meaning;
an empty file is valid. Presence-only semantics avoid parsing language-specific
comments, Markdown front matter, or a second configuration language. The uppercase,
nearby sentinel follows the existing `CONTEXT.md` and `CONTRACT.md` convention: the
directory advertises its role through a repository-addressable artifact at the point it
governs. Keeping the marker separate also avoids changing the first-line version
contract for `CONTRACT.md` recorded in
`plugins/garden/tools/CONTRACT.md:19-27`.

The `markers` strategy is already an explicit project choice, so the new behavior does
not affect projects using `none`, `children`, or `explicit`. The first enforcement phase
will remain advisory for existing projects that selected `markers` while it was a no-op.

### Resolution algorithm

The future resolver will have the same callable shape as the existing resolvers:

```python
def _markers_capability_directory(
    relative: Path, root: Path, config: EffectiveConfig
) -> Path | None:
```

For a checked file, it will resolve as follows:

1. Normalize `relative` as a confined repository-relative path. Consider only configured
   capability roots that contain that path. A marker outside those roots cannot claim
   the file.
2. Start at the file's parent directory and examine ancestor directories toward each
   containing capability root. Probe only the exact effective `marker_file` name at each
   candidate directory; do not search file contents.
3. Return the deepest marked ancestor. This is nearest-ancestor-wins, matching the
   longest-prefix behavior used by explicit capability and boundary resolution. Nested
   markers therefore create nested capabilities without ambiguity.
4. If overlapping configured roots expose candidates at the same depth, compare their
   normalized repository-relative paths in lexical order. Duplicate normalized roots
   should be rejected by schema validation, so the lexical rule is a deterministic
   fallback rather than a normal configuration mechanism.
5. Ignore missing, non-regular, and symlinked markers. If no eligible ancestor has a
   valid marker, return `None`. The marker file itself must be excluded from the source
   candidate set.

Per-file resolution needs only bounded ancestor probes; it does not recursively scan a
capability subtree. Project-index discovery may collect markers during the existing
sorted bounded walk, but it must not start a second unbounded traversal. Both paths must
honor the existing limits recorded in `plugins/garden/tools/garden_scanner.py:15-18`:
`MAX_SCAN_SECONDS = 2.0` per bounded walk, `MAX_SCAN_ENTRIES = 10_000`,
`MAX_SCAN_DEPTH = 20`, and `MAX_CHECKED_FILE_BYTES = 1_048_576` per checked file.
Ancestor probing stops at depth 20. The presence-only marker design requires no marker
content read; any future content extension would still be capped at 1 MiB.

Nearest-ancestor-wins is also the conflict rule. A marker at `src/orders` claims
`src/orders/handler.py` unless a closer marker such as
`src/orders/refunds/CAPABILITY.marker` exists. Sorted path order makes index output
stable, but it never overrides a closer ancestor.

### Exit criteria for the related experimental rules

Marker resolution supplies the capability identity used by these measurements; it does
not by itself prove any experimental rule. All four rules require the following common
conditions before an individual level change:

- `marker_file` is represented in parsed and effective capability configuration, the
  schema rejects invalid filenames, and `_CAPABILITY_DIRECTORY_RESOLVERS` dispatches
  `markers` to the implemented resolver.
- Fixtures cover root and nested markers, overlapping roots, a missing marker, symlinked
  markers, invalid filenames, sorted output, and scan-limit failure. Regression fixtures
  show that `children`, `explicit`, and `none` retain their current results.
- The deterministic conformance fixtures have zero false positives and zero false
  negatives. A separately labeled migration corpus has no more than 1 percent false
  positives and 1 percent false negatives for path-to-capability assignment.
- `garden-inspect-strict` blocks the seeded markers violation reproducibly, and the
  `gap-07-markers-resolution` benchmark expects `must_block` rather than `"none"` or a
  `known_unenforced` gap.
- Resolver and index telemetry demonstrate compliance with the existing time, entry,
  depth, and file-read budgets.

Each rule also has a rule-specific graduation condition:

| Rule | Additional condition before `REQUIRED` |
| --- | --- |
| `G-DISC-006` | A labeled sample records ancestor probes, elapsed time, and successful paths from an entry point to its handler, schema, side effects, and tests. The project defines its threshold from that baseline, and the marker index makes every sampled relationship recoverable. |
| `A-LOC-006` | A representative set of completed changes is attributed to marked capabilities and records modules touched, crossings, ownership handoffs, and requisite context. Review of the sample confirms that the chosen threshold does not reward hidden coupling or unmarked shared code. |
| `R-REPL-008` | At least one marked, non-production capability completes a replacement drill against its recorded contract and evidence set. Both implementations resolve to the same capability and the drill records a local result rather than asserting a universal time threshold. |
| `D-VER-008` | Telemetry records marker-gate detections, escaped seeded violations, execution time, and flake rate. The strict gate is repeatable without retry-to-green behavior, and its measured detection value justifies making it blocking. |

The four level changes are independent. A rule stays `EXPERIMENTAL` until its own
measurement condition is satisfied even if marker resolution has shipped. The current
`exception_policy = "not-allowed"` also remains unchanged by default. A future change to
structured exceptions would need a separate registry decision with owner, reason,
scope, and review timing; promotion alone is not a reason to permit exceptions.

### Gap-07 migration plan

1. Phase 1 adds `marker_file` validation and effective configuration, implements the
   resolver and index integration, and enables it only for `strategy = "markers"`.
   Findings remain advisory during this compatibility phase. The benchmark continues to
   identify the gap as known and unenforced.
2. Phase 2 adds the conformance and regression fixtures, configuration documentation,
   migration-corpus labeling, performance telemetry, and a seeded benchmark mutation
   whose absence or invalidity is detectable by `garden-inspect-strict`.
3. Phase 3 changes `gap-07-markers-resolution` so
   `expected_rule_id_or_signature = "must_block"` and removes its
   `known_unenforced` treatment. The four registry rules move from `EXPERIMENTAL` to
   `REQUIRED` only as their individual exit criteria are met; their `implementation` and
   `configuration_keys` metadata must change with the implementation.

The Phase 3 edits to `benchmarks/mutations/manifest.json` and
`plugins/garden/rules/garden-rules.toml` are future implementation work. This design
change does not make them.

### Complexity estimate

Markers resolution is medium-sized. It adds one schema and effective-config field, one
resolver code path, project-index integration, fixtures, benchmark behavior, and
documentation. The algorithm is small and isolated behind the existing resolver
dispatch. The main risks are activation for repositories that already selected the
previously inert strategy, nested-marker precedence, and scan-limit behavior. Regression
risk to `children` and `explicit` should remain low if their dispatch entries and
effective defaults are not changed.

## Explicit boundary and state policy (gap-08)

### Current state

There is no state-policy key or mutable-state model in the current configuration
schema. `GardenConfig` contains schema-version, project, scan, capability, test,
contract, boundary, naming, documentation, and exception fields in
`plugins/garden/tools/config_schema.py:137-148`. The top-level key allowlist contains the
same set in `plugins/garden/tools/config_schema.py:824-848`. Searches for `state` and
`mutable` in that file return no schema field; the only lower-case `policy` matches
describe boundary versioning validation.

The closest mechanism is schema v2 boundary configuration. `BoundaryConfig` and
`EffectiveBoundaryConfig` record path, kind, owner, versioning, contracts, and required
evidence in `plugins/garden/tools/config_schema.py:106-112` and
`plugins/garden/tools/config_schema.py:208-214`. `_parse_boundary_v2` validates those
fields in `plugins/garden/tools/config_schema.py:622-688`, and schema v2 accepts
`[[boundaries]]` as an array of tables in
`plugins/garden/tools/config_schema.py:905-960`. `resolve_boundary` normalizes a path and
returns the matching boundary with the deepest path prefix in
`plugins/garden/tools/garden_rules.py:255-267`.

This gap belongs under E, Explicit Boundaries and State. `E-EXPL-002` requires side
effects, dependencies, and state transitions to be explicit at the controlling boundary
in `docs/reference/principles.md:486-507` and the generated copy at
`plugins/garden/references/principles.md:487-508`. `E-EXPL-006` currently calls only for
an experimental audit of hidden state and undocumented defaults in
`docs/reference/principles.md:521-526` and
`plugins/garden/references/principles.md:522-527`.

The benchmark records the missing runtime gate as
`gap-08-explicit-state-policy`. It is owned by `garden-inspect-strict`, has
`expected_rule_id_or_signature = "none"`, and is a `known_unenforced` gap in
`benchmarks/mutations/manifest.json:557-565`.

### State-policy schema

For this policy, mutable state means repository code or artifacts whose value can change
after initialization and affect behavior across calls, requests, processes, or
deployments. A local variable confined to one invocation is not in scope. A state policy
declares the repository path where such state is implemented or stored, the existing
boundary that owns its lifecycle, and which other boundaries may reach it directly.

Schema v2 will add an optional top-level array of tables named `state_policies`:

- `path` is a normalized repository-relative path prefix. Duplicate normalized paths are
  invalid. Nested paths are allowed and use longest-prefix-wins, matching
  `resolve_boundary`.
- `owner` is the exact `path` of one existing `[[boundaries]]` entry. It identifies the
  boundary that controls state lifetime and transitions; it is not the human owner name
  stored in `BoundaryConfig.owner`.
- `kind` is one of `owned`, `shared`, or `forbidden`.
- `consumers` is an optional list of exact boundary paths. It is required and non-empty
  for `shared`, and rejected for `owned` and `forbidden`.

The kinds have these fixed meanings:

- `owned`: mutable state may exist under `path`; only the `owner` boundary may reference
  it directly.
- `shared`: mutable state may exist under `path`; the `owner` and the boundaries listed
  in `consumers` may reference it directly. This is an explicit exception to single-owner
  reachability, not an all-repository shared directory.
- `forbidden`: the path is reserved as stateless. Any file selected by the project's scan
  configuration under the path, or an in-repository reference to it, is a violation.
  `owner` names the boundary responsible for removing the violation even though state is
  not allowed there.

For example:

```toml
schema_version = 2

[[boundaries]]
path = "src/payments"
kind = "private"
owner = "payments-team"

[[boundaries]]
path = "src/orders"
kind = "private"
owner = "orders-team"

[[boundaries]]
path = "src/platform"
kind = "private"
owner = "platform-team"

[[state_policies]]
path = "src/payments/state"
owner = "src/payments"
kind = "owned"

[[state_policies]]
path = "src/platform/session_state"
owner = "src/platform"
kind = "shared"
consumers = ["src/orders", "src/payments"]
```

Validation will normalize `path`, `owner`, and `consumers` with the same repository-path
rules used by boundary paths. Every owner and consumer must resolve to exactly one
declared boundary. Consumer entries are deduplicated and stored in sorted order. The
most specific state-policy prefix governs a target path; equal normalized prefixes are
invalid rather than order-dependent.

### Runtime-check shape and rule correspondence

The runtime check will combine the existing boundary resolver with a new state-policy
resolver:

1. Build the boundary and state-policy prefix indexes from effective configuration.
2. During the existing bounded project walk, use a stack-specific adapter to resolve
   in-repository imports or references to normalized target paths. The core check must
   not guess dynamic or external targets from text alone.
3. Resolve the source file through `resolve_boundary` and the target through the
   longest matching state-policy prefix.
4. For `owned`, report a violation when the source boundary differs from `owner`. For
   `shared`, report when the source is neither `owner` nor an allowed consumer. For
   `forbidden`, report any scan-selected file under the path and any resolved
   in-repository reference to it.
5. An unsupported language or unresolved dynamic reference produces an explicit
   `unknown` during the experimental phase. Before strict enforcement, an adapter that
   declares a file in scope must either resolve its internal references or return an
   incomplete-analysis error that strict mode blocks; it cannot silently omit them.

Violations will report against the existing canonical rule `E-EXPL-002`, because that
rule already governs hidden state and state transitions at their controlling boundary.
Creating a second canonical rule would duplicate that scope. Configuration-shape errors
remain schema-validation errors. `A-LOC-002` may consume the same boundary-crossing
evidence for change verification, but a state ownership violation is not reported under
A by default: E names the omitted boundary/state policy directly.

The check reuses the existing bounded walk and file-read machinery. It must respect
`MAX_SCAN_SECONDS = 2.0`, `MAX_SCAN_ENTRIES = 10_000`, `MAX_SCAN_DEPTH = 20`, and
`MAX_CHECKED_FILE_BYTES = 1_048_576` as recorded by
`plugins/garden/tools/garden_scanner.py:15-18`. Reference extraction may read each checked file
once and may not exceed 1 MiB. It must not start an unbounded import-graph crawl or
follow symlinked directories.

### Exit criteria

The policy can move from absent to `EXPERIMENTAL` when all of the following exist:

- Parsed and effective schema v2 types for `state_policies`, closed validation for the
  three kinds, exact boundary-reference validation, duplicate detection, and
  longest-prefix resolution.
- Configuration reference documentation and fixtures for every kind, nested policies,
  missing owners, invalid consumers, duplicate paths, boundary ties, symlinks, and all
  scan-limit failures.
- At least one stack-specific reference adapter with resolved-path fixtures. Unsupported
  stacks return `unknown`; the core does not infer imports with an unchecked regular
  expression.
- Advisory `E-EXPL-002` findings and telemetry for owned, shared, and forbidden
  violations. At this stage `gap-08-explicit-state-policy` remains a
  `known_unenforced` probe.

The check can become `REQUIRED` only when:

- Strict enforcement is limited to configured projects and adapters whose supported
  syntax and resolution behavior are documented and fixture-backed.
- Deterministic conformance fixtures have zero false positives and zero false negatives.
  A manually labeled multi-boundary corpus has no more than 1 percent false positives
  and 1 percent false negatives for resolved in-scope references; unsupported or
  unresolved cases are measured separately rather than counted as passes.
- Repeated runs stay inside every scan and file-read budget and expose scan-limit or
  incomplete-analysis failures to `garden-inspect-strict`.
- A seeded owned, shared, or forbidden violation is blocked reproducibly under
  `E-EXPL-002`, and the gap-08 benchmark expects `must_block`.
- The rule registry records the implemented configuration keys and runtime behavior.
  `E-EXPL-002` remains `REQUIRED`; `E-EXPL-006` remains experimental until incident and
  change-failure sampling independently justifies changing that audit heuristic.

The explicit `shared` consumer list is the normal escape hatch. The state gate should
not add a blanket exception merely to bypass ownership; any later structured exception
must carry the existing owner, reason, scope, and review timing required by GARDEN's
exception model.

### Gap-08 migration plan

1. Phase 1 adds optional schema v2 `[[state_policies]]` parsing, effective values,
   validation, and longest-prefix resolution. Existing configuration without the table
   remains valid. No strict runtime finding is introduced.
2. Phase 2 adds the first supported reference adapter, advisory `E-EXPL-002` findings,
   conformance fixtures, labeled-corpus measurement, documentation, and a seeded
   cross-boundary state mutation. Unsupported analysis stays explicit as `unknown`.
3. Phase 3 makes supported, configured violations blocking and changes
   `gap-08-explicit-state-policy` so
   `expected_rule_id_or_signature = "must_block"`, removing its
   `known_unenforced` treatment. Registry metadata changes in the same implementation
   change so the gate and documentation cannot drift.

The Phase 3 edits to `benchmarks/mutations/manifest.json`, the rule registry, schema,
runtime, adapters, fixtures, and reference documentation are future tasks. This design
change does not perform them.

### Complexity estimate

Explicit state policy is large. Unlike markers, it has no current schema field,
effective model, resolver, or runtime path. It requires new schema types, referential
validation against boundary entries, a prefix index, stack-specific reference adapters,
new findings, fixtures, benchmark mutations, documentation, and performance telemetry.
Its false-positive and false-negative risk is also higher because import resolution and
dynamic references vary by language and build system.

## Migration risks and tradeoffs

Existing `.garden.toml` files remain valid because `state_policies` is optional and the
state gate applies only to configured projects with a supported adapter. Marker behavior
has a narrower compatibility risk: a repository that already selected `markers` selected
an inert strategy and will begin resolving the default sentinel after implementation.
The advisory phase and explicit migration fixtures provide notice before strict findings
can affect CI.

Both migrations change the meaning of `garden-inspect-strict` only in their final phase.
Before the corresponding benchmark expects `must_block`, telemetry and labeled fixtures
must demonstrate the stated error budgets. After that flip, scan exhaustion and
incomplete supported analysis must remain visible rather than being reported as clean
passes.

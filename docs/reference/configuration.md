---
owner: vshuraeff
last_reviewed: 2026-07-17
review_on:
  - config-schema-change
  - major-release
---

# Project configuration reference

GARDEN reads `.garden.toml` from the project root. It supports schema versions 1
and 2. Schema v1 remains fully supported during the pre-1.0 migration window.
Schema v2 adds structured boundary declarations through `[[boundaries]]`. The file
is parsed with strict key and type validation. Unknown keys are errors at every level.
Every root key is optional; omitted keys take the defaults listed below.

For how deterministic inspection reports a configuration's location, schema version,
and validation result, see [report-schema.md](report-schema.md).

Relative paths and globs are evaluated from the directory containing `.garden.toml`.
GARDEN normalizes `\` separators to `/` and rejects absolute paths, drive-letter
paths, UNC paths, and `..` segments. Existing symlinks must also resolve inside the
project root. This normalization is a security boundary, not a cross-platform
compatibility layer; see
[platform-support.md](platform-support.md) for the resulting Windows constraint.

## Root keys

| Key | Type | Default | Semantics |
| --- | --- | --- | --- |
| `schema_version` | integer | `1` | Configuration schema. If present, the value must be `1` or `2`; booleans are not integers. |
| `project` | table | section defaults | Project classification and root context declarations. |
| `scan` | table | section defaults | Source discovery roots and globs. |
| `capabilities` | table | section defaults | Capability resolution for deterministic structural checks. |
| `tests` | table | section defaults | Test discovery and capability association. |
| `contracts` | table | section defaults | Contract policy for declared public boundaries. |
| `boundaries` | table (v1) / array of tables (v2) | section defaults | Schema v1 uses `[boundaries]` for public boundary declarations. Schema v2 uses `[[boundaries]]` for structured boundary entries. |
| `naming` | table | section defaults | Naming-registry location and requirement. |
| `documentation` | table | section defaults | Root context requirement and line budget. |
| `exceptions` | array of tables | `[]` | Structured rule waivers validated and applied to eligible matching findings. |

## Project

| Key | Type | Default | Semantics |
| --- | --- | --- | --- |
| `project.type` | string | `"other"` | One of `service`, `library`, `cli`, `monorepo`, `infra`, or `other`. |
| `project.context_files.any_of` | array of paths | `["CONTEXT.md"]` | At least one listed root-relative file must exist when root context is required. |
| `project.context_files.all_of` | array of paths | `[]` | Every listed root-relative file must exist when root context is required. |

When `any_of` and `all_of` are both non-empty, both conditions apply.

## Scan

| Key | Type | Default | Semantics |
| --- | --- | --- | --- |
| `scan.roots` | array of paths | `["."]` | Roots that constrain the deterministic project walk. Overlapping or nested valid roots are deduplicated; a root that does not exist or resolves outside the project root is skipped and reported. |
| `scan.include` | array of globs | `["**/*.py", "**/*.ts"]` | Candidate source paths. Configuration formats are not included unless listed explicitly. |
| `scan.exclude` | array of globs | `["**/node_modules/**", "**/dist/**"]` | Paths removed from source discovery. |

Each glob list accepts at most 200 patterns. Each pattern is at most 4096
characters. Adjacent recursive segments such as `**/**` and `a/**/**/b` are
invalid.

Deterministic inspection matches `scan.include` and `scan.exclude` against each
POSIX-normalized project-relative path. Exclusions win. An explicitly empty
`scan.include` uses the legacy source-suffix filter, while configuration formats
become source candidates only when an include glob matches them. Dotfiles and
files under ignored build or dependency directories remain excluded. The project walk
is restricted to `scan.roots`. `scan.exclude` prunes matching directories and files
before the entry-count budget is evaluated, so excluded content does not consume that
budget.

Configured project-root context paths from `project.context_files.any_of` and
`project.context_files.all_of` (default `CONTEXT.md`) and `.garden.toml` are checked
as explicit paths, not discovered by the walk, so they remain inspected outside
`scan.roots`. See [report-schema.md](report-schema.md) for the report's `scan` object
and `D-scan-root-missing` findings for configured roots that are skipped.

## Capabilities

| Key | Type | Default | Semantics |
| --- | --- | --- | --- |
| `capabilities.strategy` | string | `"children"` | One of `none`, `explicit`, `children`, or `markers`. |
| `capabilities.roots` | array of paths | `["."]` | Roots used by `children`; each capability begins below one of these roots. |
| `capabilities.depth` | positive integer | `1` | Number of path components below a capability root that form the capability name. Booleans are rejected. |
| `capabilities.map` | path-to-string table | `{}` | For `explicit`, maps a path prefix to a capability name. The longest matching prefix wins. |
| `capabilities.shared_roots` | array of paths | `[]` | Prefixes classified as shared before strategy dispatch; they are never capabilities. |

`markers` declares experimental intent only. Its resolver returns `unknown` tagged
`EXPERIMENTAL`; schema v1 does not define a marker-file format.

Configured deterministic inspection groups source files by the resolved capability
identity. `shared`, `none`, and `unknown` results do not receive capability contract
or colocated-test findings. A `children` capability checks for `CONTRACT.md` in its
resolved directory under the matched capability root. An `explicit` capability uses
the mapped name as its grouping identity and checks `CONTRACT.md` in the matched map
prefix, such as `src/client/CONTRACT.md` for `"src/client" = "client"`.

## Capability identity

For `strategy = "children"`, capability identity includes the configured root and
the resolved child path segments. For example, `src/orders` and `lib/orders` are
distinct capabilities rather than sharing the bare identity `orders`.

## Tests

| Key | Type | Default | Semantics |
| --- | --- | --- | --- |
| `tests.patterns` | array of globs | `["**/test_*.py", "tests/**"]` | Candidate test paths. With a config present, these replace filename substring discovery. |
| `tests.association` | string | `"same-capability"` | One of `same-capability` or `test-roots`. |
| `tests.test_roots` | path-to-path table | `{}` | For `test-roots`, maps a test-path prefix to its source-path prefix; the longest match wins. |

The 200-pattern and 4096-character limits also apply to `tests.patterns`.
With a config present, only matching paths are test candidates; filename substrings
do not count. `same-capability` resolves the test path through the configured
capability strategy. `test-roots` maps the test path to a source path and resolves
that source path through the same capability strategy. Mapped tests satisfy the
resulting capability across the whole project. Unmapped tests do not satisfy a
capability. Test candidates themselves do not receive capability-scoped findings.

## Contracts and boundaries

| Key | Type | Default | Semantics |
| --- | --- | --- | --- |
| `contracts.required_for` | array of strings | `[]` | Contract categories required when public boundaries are declared. |
| `contracts.accepted_names` | array of strings | `["CONTRACT.md", "openapi.yaml", "schema.graphql"]` | Accepted contract artifact names. |
| `boundaries.public` | array of paths | `[]` | Explicit public boundary paths. |

Schema v1 resolves `boundaries.public` and `contracts.required_for` but this wiring
does not enforce either in deterministic project inspection. `contracts.required_for`
is legacy and underspecified, superseded by schema v2 `[[boundaries]].contracts`, and
kept only for compatibility; it has no runtime effect.

## Schema v2 boundaries

Each `[[boundaries]]` entry accepts only these keys:

| Key | Type | Required | Semantics |
| --- | --- | --- | --- |
| `path` | string | yes | Project-relative boundary path. |
| `kind` | string | yes | Boundary kind. |
| `owner` | string | except for `private` | Person or team responsible for the boundary. |
| `versioning` | string | no | Compatibility versioning policy. |
| `contracts` | array of paths | no | Project-relative contract artifact paths resolved from `path`. |
| `required_evidence` | array of strings | no | Evidence categories required for the boundary. |

`kind` is a closed enum: `public-api`, `external-integration`,
`independently-deployed`, `persisted-schema`, `trust-boundary`,
`internal-versioned`, and `private`.

`versioning` is a closed enum: `none`, `semver`, `calendar`, `schema-specific`, and
`custom`.

`required_evidence` uses the closed `EVIDENCE_CATEGORIES` enum: `contract-tests`,
`compatibility-tests`, `rollback-plan`, `observability`, `migration-plan`, and
`security-review`.

An owner is required except when `kind = "private"`. Private boundaries must not
declare a versioning policy other than `none`. Private boundaries must not declare
`contracts` or `required_evidence`.
`internal-versioned` boundaries require a versioning policy other than `none`.

Two `[[boundaries]]` entries cannot use the same normalized `path`. Boundary `path`
values and contract artifact paths resolved from `contracts` are subject to the same
project-root confinement as other configured paths. The other fields are validated
strings or enums, not filesystem paths.

```toml
schema_version = 2

[[boundaries]]
path = "src/api"
kind = "public-api"
owner = "platform-team"
versioning = "semver"
contracts = ["CONTRACT.md"]
required_evidence = ["contract-tests", "rollback-plan"]
```

Deterministic project inspection checks each declared `contracts` artifact is a file;
a missing artifact emits the `R-boundary-contract-missing` error. When
`versioning = "semver"`, it checks boundary-relative files whose basename is an
accepted contract name or whose path is declared in `contracts`: the first non-empty
line must be `Version: MAJOR.MINOR.PATCH`, otherwise it emits
`R-contract-version`. Boundaries with any other versioning policy, including private
boundaries, are never version-checked. Each `required_evidence` category emits an
`R-boundary-evidence-review` advisory finding with `state = "unknown"`; file
existence cannot establish evidence completeness, so manual verification is required.

## Naming

| Key | Type | Default | Semantics |
| --- | --- | --- | --- |
| `naming.registry` | path | `"naming-registry.txt"` | Root-relative naming-registry path. |
| `naming.required` | boolean | `false` | Declares whether the configured registry is required. Integers are rejected. |

A required registry must exist and contain at least one entry. When `naming.required`
is true or a `[naming]` table is present, deterministic inspection validates every
non-blank, non-comment line as `concept: canonical_name`. Empty values, duplicate
concepts, and duplicate canonical names are errors. If `[naming]` is explicit but
`naming.required` is false, an absent registry is allowed; an existing registry is
still validated.

A project without `.garden.toml` can still activate through a root
`naming-registry.txt`. Run `garden migrate-config ROOT` to create a checked v1 config
that retains the registry declaration. Values not derivable from the legacy file are
written as `TODO` comments.

## Documentation

| Key | Type | Default | Semantics |
| --- | --- | --- | --- |
| `documentation.root_context_required` | boolean | `true` | Requires the `any_of` and `all_of` context-file conditions. |
| `documentation.max_context_lines` | positive integer | `200` | Maximum line count for configured context files. Booleans are rejected. |

When `.garden.toml` is absent, deterministic inspection retains the existing implicit
`CONTEXT.md` check and its 200-line budget.

## Exceptions

Each `[[exceptions]]` entry accepts only these keys:

| Key | Type | Default | Semantics |
| --- | --- | --- | --- |
| `rule_id` | string | `""` | Rule identifier waived by the entry. |
| `paths` | array of globs | `[]` | Paths covered by the waiver. The pattern count and length limits apply. |
| `reason` | string | `""` | Reason for the waiver. |
| `owner` | string | `""` | Person or team responsible for review. |
| `review_after` | string | `""` | Review date or project-specific review marker. |

Validation accepts only known canonical rule IDs or runtime aliases for
exception-eligible rules; schema v2 requires the canonical ID rather than a runtime
alias. The accepted canonical IDs and eligible runtime aliases originate in
`plugins/garden/rules/garden-rules.toml`: `garden_rule_metadata.py` derives
`EXCEPTION_ELIGIBLE_RULES` and `RUNTIME_ALIAS_TABLE` from it. `reason` and `owner`
must be non-empty, and `review_after` must be an ISO `YYYY-MM-DD` date or
`on-rule-change` or `on-major-release`. Inspection suppresses matching `fail` findings
by canonical rule ID and path glob unless an ISO-date `review_after` is in the past;
review markers do not expire. It never suppresses `unknown` findings.

## Commands

`garden config validate [ROOT]` reports syntax, schema, and confinement errors as
`dotted.path: message`. A missing `.garden.toml` is valid. Any reported error produces a
non-zero exit status.

`garden config show [ROOT]` prints one effective leaf per line in schema order:

```text
project.type = "service" # origin: file
scan.roots = ["."] # origin: default
```

Arrays and maps use deterministic inline TOML-like values. Every leaf ends with
`# origin: file` or `# origin: default`. The exceptions line contains the resolved entry
count, followed by indexed exception leaves when entries exist.

`garden init [ROOT]` detects `pyproject.toml`, `package.json`, `Cargo.toml`, and
`go.mod`, then writes a conservative `.garden.toml`. Existing common source directories
become proposed roots. The command writes no other files and requires `--force` to
replace an existing config.

`garden migrate-config [ROOT]` reads `naming-registry.txt`, renders keys in a fixed
schema-specific order, validates the generated TOML and effective meaning, and replaces
the destination atomically. It requires `--force` to replace an existing config.

`garden migrate-config ROOT --to-schema 2 --owner NAME` migrates an existing valid
schema v1 config to schema v2. It converts each `boundaries.public` path to a
`[[boundaries]]` entry with `kind = "public-api"`, the given owner, and
`versioning = "none"`. `--owner` is required when the v1 config declares public
boundaries. The command requires `--force` to replace an existing `.garden.toml`.

## Service example

```toml
schema_version = 1

[project]
type = "service"
context_files = { any_of = ["CONTEXT.md", "AGENTS.md"] }

[scan]
roots = ["src"]
include = ["**/*.py"]
exclude = ["**/dist/**"]

[capabilities]
strategy = "children"
roots = ["src"]
depth = 1
shared_roots = ["src/shared"]

[tests]
patterns = ["**/test_*.py"]
association = "same-capability"
```

## Library example

```toml
schema_version = 1

[project]
type = "library"
context_files = { all_of = ["CONTEXT.md"] }

[scan]
roots = ["src", "tests"]
include = ["**/*.ts"]
exclude = ["**/dist/**", "**/node_modules/**"]

[capabilities]
strategy = "explicit"
map = { "src/client" = "client", "src/types" = "types" }

[tests]
patterns = ["**/*.test.ts"]
association = "test-roots"
test_roots = { "tests/client" = "src/client", "tests/types" = "src/types" }
```

## Monorepo example

```toml
schema_version = 1

[project]
type = "monorepo"
context_files = { any_of = ["CONTEXT.md", "AGENTS.md"] }

[scan]
roots = ["packages"]
include = ["**/*.py", "**/*.ts"]
exclude = ["**/node_modules/**", "**/dist/**"]

[capabilities]
strategy = "children"
roots = ["packages"]
depth = 1
shared_roots = ["packages/shared"]

[tests]
patterns = ["**/test_*.py", "**/*.test.ts"]
association = "same-capability"
```

## Infrastructure example

Configuration formats must be included explicitly:

```toml
schema_version = 1

[project]
type = "infra"
context_files = { all_of = ["AGENTS.md"] }

[scan]
roots = ["roles", "inventory"]
include = ["**/*.yaml", "**/*.yml", "**/*.toml"]
exclude = ["**/dist/**"]

[capabilities]
strategy = "none"

[tests]
patterns = ["molecule/**", "tests/**"]
association = "test-roots"
test_roots = { "molecule" = "roles", "tests" = "roles" }

[documentation]
root_context_required = true
max_context_lines = 200
```

# Project configuration reference

GARDEN reads `.garden.toml` from the project root. The file uses schema v1 and is
parsed with strict key and type validation. Unknown keys are errors at every level.
Every key is optional; omitted keys take the defaults listed below.

Relative paths and globs are evaluated from the directory containing `.garden.toml`.
GARDEN normalizes `\` separators to `/` and rejects absolute paths, drive-letter
paths, UNC paths, and `..` segments. Existing symlinks must also resolve inside the
project root.

## Root keys

| Key | Type | Default | Semantics |
| --- | --- | --- | --- |
| `schema_version` | integer | `1` | Configuration schema. If present, the value must be exactly `1`; booleans are not integers. |
| `project` | table | section defaults | Project classification and root context declarations. |
| `scan` | table | section defaults | Source discovery roots and globs. |
| `capabilities` | table | section defaults | Capability resolution for deterministic structural checks. |
| `tests` | table | section defaults | Test discovery and capability association. |
| `contracts` | table | section defaults | Contract policy for declared public boundaries. |
| `boundaries` | table | section defaults | Explicit public boundary declarations. |
| `naming` | table | section defaults | Naming-registry location and requirement. |
| `documentation` | table | section defaults | Root context requirement and line budget. |
| `exceptions` | array of tables | `[]` | Structured rule waivers. Enforcement is deferred; entries are parsed and resolved in schema v1. |

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
| `scan.roots` | array of paths | `["."]` | Declared source discovery roots; deterministic walk restriction is deferred below. |
| `scan.include` | array of globs | `["**/*.py", "**/*.ts"]` | Candidate source paths. Configuration formats are not included unless listed explicitly. |
| `scan.exclude` | array of globs | `["**/node_modules/**", "**/dist/**"]` | Paths removed from source discovery. |

Each glob list accepts at most 200 patterns. Each pattern is at most 4096
characters. Adjacent recursive segments such as `**/**` and `a/**/**/b` are
invalid.

Deterministic inspection matches `scan.include` and `scan.exclude` against each
POSIX-normalized project-relative path. Exclusions win. An explicitly empty
`scan.include` uses the legacy source-suffix filter, while configuration formats
become source candidates only when an include glob matches them. Dotfiles and
files under ignored build or dependency directories remain excluded. `scan.roots`
is resolved for configuration consumers, but restricting the project walk to those
roots is deferred.

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

Schema v1 resolves these values but does not yet enforce them in deterministic project
inspection.

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

Exception enforcement is deferred. Schema v1 validates and preserves the structured
values so later rule wiring does not require a schema change.

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

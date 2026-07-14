---
owner: vshuraeff
last_reviewed: 2026-07-14
review_on:
  - config-schema-change
  - major-release
---

# How to migrate from GARDEN v0

Use this guide for a project whose root `naming-registry.txt` still provides its only
GARDEN activation marker. The migration keeps that registry while making schema v1
`.garden.toml` the primary project configuration.

## 1. Generate `.garden.toml` from the legacy registry

Run:

```sh
garden migrate-config ROOT
```

From an unpacked plugin, the equivalent command is:

```sh
uv run --no-project <plugin-root>/tools/garden_cli.py migrate-config ROOT
```

The command reads root `naming-registry.txt`, writes `schema_version = 1`, and creates a
`[naming]` table with `registry = "naming-registry.txt"` and `required = true`. It emits
the exact unresolved areas from `render_migrated_config` as `TODO` comments: project
type and context files; scan roots and source globs; capability strategy and test
association; and public boundaries, contract policy, and structured exceptions. It
refuses to replace an existing `.garden.toml` unless `--force` is explicit.

- Action: run the migration command, then resolve each `TODO` against the
  [configuration reference](../reference/configuration.md).
- Acceptance signal: `.garden.toml` parses as schema v1, retains the legacy registry
  declaration, and has no unresolved value that affects the project's actual source,
  tests, capabilities, or public boundaries.

## 2. Transfer project-level activation

The runtime's
[`find_project_activation`](../../plugins/garden/tools/garden_paths.py) checks
`.garden.toml` before `naming-registry.txt` at each candidate project root. After
migration, `garden:start` uses the config-first path and the prompt hook routes through
that same project-root lookup. `garden:stop` removes only provenance-owned instruction
surfaces; it preserves `.garden.toml`, the naming registry, contracts, capability
artifacts, and retrofit records.

- Action: run `garden:start` for the required harnesses after reviewing the migrated
  config. If project instructions are later removed, use `garden:stop` rather than
  deleting project artifacts.
- Acceptance signal: the prompt hook recognizes the project through `.garden.toml`, and
  stopping project tooling leaves the migrated config and project artifacts unchanged.

## 3. Verify the existing naming registry

Because the generated config sets `naming.required = true`, deterministic inspection
continues to require the configured registry and validates every non-blank,
non-comment line as `concept: canonical_name`. Empty values, duplicate concepts, and
duplicate canonical names remain errors; the migration does not relax those checks. See
the [Naming section](../reference/configuration.md#naming).

- Action: run `garden inspect ROOT` and resolve every naming error against the existing
  registry without changing a concept's meaning silently.
- Acceptance signal: inspection reports no missing-registry, malformed-entry,
  duplicate-concept, or duplicate-canonical-name error.

## 4. Reclassify existing contracts

Classify each existing `CONTRACT.md` by the boundary it governs. Published APIs,
independently deployed components, persisted schemas, external integrations, and
explicitly versioned boundaries need a compatibility policy and SemVer where SemVer
fits. A private internal module does not need an artificial `Version:` line; Git history
tracks it. The current scope is defined by
[`R-REPL-002`](../reference/principles.md#r--replaceable-components) and the
[configured public boundaries](../reference/configuration.md#contracts-and-boundaries).

- Action: declare actual public paths under `boundaries.public`, configure accepted
  contract names, and remove unneeded SemVer obligations from private-module contracts.
- Acceptance signal: every versioned contract maps to a designated versioned boundary,
  and no private module is versioned only because v0 required the file shape.

## 5. Scope canonical names by bounded context

Review the glossary entries for
[bounded context and translation map](../reference/glossary.md). When several bounded
contexts use different vocabulary, keep one canonical name inside each context and add
an explicit translation map at the boundary. Do not force a repository-wide synonym.
If one registry file remains, include the bounded context in the concept label so the
entry's scope is explicit.

- Action: identify context boundaries, scope existing concepts to their owning context,
  and document translations at every boundary that changes a name or representation.
- Acceptance signal: each context has one canonical meaning and name per concept, and a
  reader can recover every cross-context translation from a maintained map.

## 6. Map legacy runtime rule IDs

Search project docs, lint configuration, suppression files, and CI output parsers for
old rule-ID strings. Map them through the
[Runtime rule-ID correspondence](../reference/principles.md#runtime-rule-id-correspondence)
table rather than copying the table into project documentation. Keep a legacy runtime
string only where the current plugin still emits it.

- Action: replace normative references with their stable current rule IDs and retain a
  compatibility alias only at the runtime integration that still needs it.
- Acceptance signal: project policy cites current `G-`, `A-`, `R-`, `D-`, `E-`, or
  `N-` rule IDs, while runtime consumers continue to recognize emitted compatibility
  strings.

## 7. Gate the schema v1 configuration in CI

Add the config validator before checks that depend on scan roots, capabilities, naming,
contracts, or exceptions:

```sh
garden config validate ROOT
```

The unpacked-plugin equivalent is:

```sh
uv run --no-project <plugin-root>/tools/garden_cli.py config validate ROOT
```

- Action: run config validation from versioned CI configuration and stop dependent
  GARDEN checks when it fails.
- Acceptance signal: malformed, unsupported, or unconfined `.garden.toml` values fail CI
  before project inspection uses them.

## 8. Retire registry-only activation

Schema v1 keeps `naming-registry.txt`-only activation as a legacy fallback: in
`garden_paths.py`, `find_project_activation` checks `.garden.toml` first and returns the
legacy marker only when the config is absent at that root. The schema v1 configuration
reference specifies no removal release for this fallback, but new projects should not
rely on it exclusively; use `garden init` or the migration command to create
`.garden.toml`.

- Action: keep the registry as configured naming data, not as the project's only
  activation or structure declaration.
- Acceptance signal: `.garden.toml` is the primary activation marker and CI validates
  it; removing the legacy fallback in a future major release would not erase the
  project's configuration model.

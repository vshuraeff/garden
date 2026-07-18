---
owner: vshuraeff
last_reviewed: 2026-07-17
review_on:
  - rule-change
  - config-schema-change
---
<!-- Generated from docs/reference/rule-registry.md. Do not edit directly. Run sync_references.py --write to update. -->

# GARDEN rule registry

`plugins/garden/rules/garden-rules.toml` is the canonical source of GARDEN rule
metadata. It records each stable rule ID, principle letter, title, normative level,
scope, implementation status, runtime aliases, configuration keys, exception policy,
exception eligibility, and compact-digest text. It also records principle names and
digest notes and the runtime-only checks that are not canonical rules.

`implementation = "partial"` records a working approximate or legacy runtime check
whose full mechanization remains tracked in the registry. Coverage reports it only as
implemented; it is not duplicated in the manual or planned lists. See
[report-schema.md](https://github.com/vshuraeff/garden/blob/master/docs/reference/report-schema.md#coverage).

## Derived artifacts

| Derived data | Producer and use |
| --- | --- |
| Runtime aliases, exception eligibility, and coverage | `garden_rule_metadata.py` loads the registry to build `RUNTIME_ALIAS_TABLE`, `EXCEPTION_ELIGIBLE_RULES`, and `COVERAGE`. |
| Exception rule-ID validation | `config_schema.py` `_parse_exception` accepts registry-loaded canonical IDs and aliases from `RUNTIME_ALIAS_TABLE`, then checks registry-derived exception eligibility. Schema v2 requires canonical IDs. See [configuration.md](./configuration.md#exceptions). |
| Inspection-report coverage | `garden_report.py` serializes `COVERAGE`; [report-schema.md](https://github.com/vshuraeff/garden/blob/master/docs/reference/report-schema.md#coverage) defines the report fields. |
| Compact rules digest | `generate_rules_digest.py --write` renders `plugins/garden/assets/garden-rules.md` from the registry. `garden_project.py` reads that asset when installing project rules. |
| Rule inspection | `garden explain RULE_ID` loads the registry and prints a canonical rule or resolves a runtime alias. |

## Human-authored material

Rationale, anti-patterns, and examples remain in [principles.md](./principles.md).
Evidence and procedure prose remain in [checklist.md](./checklist.md). Edit the compact
digest wording in a rule's `digest` field in the TOML; do not edit the generated
`plugins/garden/assets/garden-rules.md`.

## Drift checks

`plugins/garden/tools/validate_registry.py` checks registry rule IDs and levels against
[principles.md](./principles.md), checklist IDs, levels, and Mechanization prefixes
against [checklist.md](./checklist.md), runtime-alias uniqueness and consistency with
`RUNTIME_ALIAS_TABLE`, the human-readable runtime correspondence table, and
`benchmarks/principle-rule-map.json` principle mappings. It also checks the registry
exception-eligibility fields against `EXCEPTION_ELIGIBLE_RULES`.

## Packaged references

`plugins/garden/tools/sync_references.py` maps these editable sources to flat package
copies through `REFERENCE_PAIRS`:

| Source | Package copy |
| --- | --- |
| `docs/reference/principles.md` | `plugins/garden/references/principles.md` |
| `docs/reference/checklist.md` | `plugins/garden/references/checklist.md` |
| `docs/reference/glossary.md` | `plugins/garden/references/glossary.md` |
| `docs/how-to/review-code-as-agent.md` | `plugins/garden/references/review-procedure.md` |
| `docs/evidence/evidence-registry.md` | `plugins/garden/references/evidence-registry.md` |
| `docs/how-to/set-up-verification-gates.md` | `plugins/garden/references/set-up-verification-gates.md` |
| `docs/reference/rule-registry.md` | `plugins/garden/references/rule-registry.md` |
| `docs/reference/configuration.md` | `plugins/garden/references/configuration.md` |

`render()` preserves each source except for a generated-file marker inserted after
front matter, or at the top when no front matter exists, and deterministic link
rewriting. Links to another source in `REFERENCE_PAIRS` become same-directory
`./<package-filename>` links. Links to the following unpackaged sources become
`https://github.com/vshuraeff/garden/blob/master/<path>` links:

- `docs/how-to/apply-to-new-project.md`
- `docs/how-to/retrofit-legacy-codebase.md`
- `docs/explanation/why-agent-first-principles.md`
- `docs/reference/report-schema.md`
- `docs/reference/platform-support.md`

Any other relative source-only link raises `ValueError`, so both
`sync_references.py --check` and `--write` fail. `validate_package.py`'
`validate_packaged_links()` is the self-containment enforcement point: it separately
checks that every remaining relative packaged link resolves to a file within the
plugin, while fallback targets are absolute GitHub URLs. It catches manual edits and
rendering regressions; an installed plugin can therefore navigate these references
without a source-repository checkout.

## Changing a rule

Edit the rule definition and level in [principles.md](./principles.md), its matching
checklist entry and Mechanization prefix in [checklist.md](./checklist.md), and the
registry entry together. Run:

```sh
uv run --no-project plugins/garden/tools/validate_registry.py
uv run --no-project plugins/garden/tools/validate_docs.py
```

If a field rendered in the digest changes, run:

```sh
uv run --no-project plugins/garden/tools/generate_rules_digest.py --write
uv run --no-project plugins/garden/tools/sync_references.py --check
```

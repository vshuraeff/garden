---
owner: vshuraeff
last_reviewed: 2026-07-17
review_on:
  - rule-change
  - config-schema-change
---

# GARDEN rule registry

`plugins/garden/rules/garden-rules.toml` is the canonical source of GARDEN rule
metadata. It records each stable rule ID, principle letter, title, normative level,
scope, implementation status, runtime aliases, configuration keys, exception policy,
exception eligibility, and compact-digest text. It also records principle names and
digest notes and the runtime-only checks that are not canonical rules.

`implementation = "partial"` records a working approximate or legacy runtime check
whose full mechanization remains tracked in the registry. Coverage reports it only as
implemented; it is not duplicated in the manual or planned lists. See
[report-schema.md](./report-schema.md#coverage).

## Derived artifacts

| Derived data | Producer and use |
| --- | --- |
| Runtime aliases, exception eligibility, and coverage | `garden_rule_metadata.py` loads the registry to build `RUNTIME_ALIAS_TABLE`, `EXCEPTION_ELIGIBLE_RULES`, and `COVERAGE`. |
| Exception rule-ID validation | `config_schema.py` `_parse_exception` accepts registry-loaded canonical IDs and aliases from `RUNTIME_ALIAS_TABLE`, then checks registry-derived exception eligibility. Schema v2 requires canonical IDs. See [configuration.md](./configuration.md#exceptions). |
| Inspection-report coverage | `garden_report.py` serializes `COVERAGE`; [report-schema.md](./report-schema.md#coverage) defines the report fields. |
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

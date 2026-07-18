---
owner: vshuraeff
last_reviewed: 2026-07-16
review_on:
  - rule-change
  - config-schema-change
  - major-release
---

# Deterministic structural inspection report schema

`garden inspect` and `garden_inspect_project` return a schema-v2 JSON report.
The report records the deterministic structural checks evaluated for one project
root.

**Not a compliance audit.** The fixed `scope` value
`"deterministic-structural-inspection"` distinguishes this report from a full
GARDEN compliance audit. The separate `garden:audit` skill performs the
checklist-based, LLM-driven review against [checklist.md](checklist.md); this
report neither replaces nor represents that review.

## Top-level object

| Field | Type | Semantics |
| --- | --- | --- |
| `schema_version` | integer | `2`. |
| `scope` | string | Always `"deterministic-structural-inspection"`. |
| `active` | boolean | Whether the resolved root is an active GARDEN project. |
| `complete` | boolean | Whether structural inspection completed without an `unknown` finding. |
| `root` | string | Resolved project root inspected by the tool. |
| `configuration` | object | Configuration location, schema version, and validation result. |
| `coverage` | object | Rule coverage declared by `garden_rule_metadata.COVERAGE`. |
| `exceptions` | array | Configured exception records, reported without enforcement. |
| `findings` | array | Finding objects described below. |
| `summary` | object | Counts from the deduplicated finding set. |

`configuration` has these fields:

| Field | Type | Semantics |
| --- | --- | --- |
| `path` | string or null | Location of `.garden.toml`, or `null` when no configuration file is present. |
| `schema_version` | integer or null | Configuration schema version, or `null` without a loaded configuration. |
| `valid` | boolean | Result of configuration loading; no configuration is represented as valid. |

`summary.errors`, `summary.warnings`, and `summary.advisories` count findings by
severity. `summary.unknown` and `summary.suppressed` count findings by state.
Every counter is a non-negative integer.

`exceptions` serializes configured `[[exceptions]]` values as `rule_id`,
`paths`, `reason`, `owner`, and `review_after`. The current inspector does not
apply an exception to a finding or emit `suppressed` for it. Exception-suppression
enforcement is future work and outside this report schema's current behavior.

## Completion and finding state

`complete` is false whenever any deduplicated finding has `state = "unknown"`.
It is also false for roots that are inactive or cannot be fully inspected because
configuration loading failed. A consumer must surface `complete = false`; it
must not silently treat an incomplete inspection as a clean pass.

The report validator accepts these states:

| State | Meaning |
| --- | --- |
| `pass` | The evaluated check was satisfied. |
| `fail` | The evaluated check found a structural violation. |
| `not-applicable` | The evaluated rule does not apply to this project or path. It is a per-finding applicability result. |
| `unknown` | The check could not be evaluated deterministically, such as after a bounded scan limit. It is a real finding state, never a pass. |
| `suppressed` | Reserved for a finding suppressed by an enforced exception. Current structural inspection does not emit this state. |

Current rules construct `fail` findings and use `unknown` for bounded-scan
failures. The other accepted values make the report contract usable by rules
that can evaluate those outcomes without changing its schema.

## Findings

Each finding has the following fields:

| Field | Type | Semantics |
| --- | --- | --- |
| `rule_id` | string | Canonical rule identifier. For the four mappings in [principles.md](principles.md#runtime-rule-id-correspondence), this is the normative ID; otherwise it is the emitted runtime ID. |
| `runtime_alias` | string or null | Earlier runtime identifier when `rule_id` has a normative mapping; otherwise `null`. |
| `level` | string | One of `REQUIRED`, `DEFAULT`, or `EXPERIMENTAL`. |
| `severity` | string | One of `error`, `warning`, `advisory`, or `information`. |
| `state` | string | One of the states in the preceding table. |
| `path` | string | Path attributed to the finding. |
| `message` | string | Deterministic finding message. |
| `evidence` | array of strings | Rule-provided evidence. It can be empty; evidence is not populated universally. |
| `remediation` | string or null | Rule-provided remediation, when available. |
| `confidence` | string or null | Rule-provided confidence, when available. |
| `rule` | string | Deprecated v1 compatibility key. It is the runtime alias when one exists, otherwise the same value as `rule_id`. |

The structural rules currently construct findings without evidence, remediation,
or confidence values, so their serialized `evidence` is empty and the nullable
fields are `null`. The assembler preserves values supplied by a rule.

## Coverage

`coverage` lists stable rule IDs from `garden_rule_metadata.COVERAGE`:

| Field | Meaning |
| --- | --- |
| `implemented_rules` | Rules with a current deterministic runtime check. |
| `manual_rules` | Rules that require manual, owner-led evaluation rather than this inspection. |
| `planned_rules` | Rules intended for future mechanization. |
| `not_applicable_rules` | Rules the tool declares categorically inapplicable; this list is currently empty. |

`implemented_rules` and `manual_rules`/`planned_rules` are not disjoint.
`R-REPL-001`, `R-REPL-002`, `A-LOC-004`, and `N-KNOW-005` appear in both:
[checklist.md](checklist.md) still records their full mechanization as manual
or planned, while `RUNTIME_ALIAS_TABLE` already runs an approximate legacy
heuristic check for them (contract presence, contract version, colocated
tests, context budget) that predates and does not satisfy the checklist's
mechanization criteria. The overlap signals partial mechanization, not a
data error. A canonical machine-readable rule registry with an explicit
"partial" implementation status is planned to remove the overlap.

A rule absent from `implemented_rules` is not evaluated by this tool. That is
different from finding state `not-applicable`, which is a project-specific
applicability judgment for a rule that was evaluated.

## Legacy compatibility

The v1 `findings[].rule` key and `summary.errors` and `summary.advisories`
counters remain unchanged for backward compatibility. They are deprecated in
favor of `rule_id` and `runtime_alias`, and the fuller `summary` object. No
removal date is set.

`benchmarks/lib/garden_adapter.py` still falls back to `findings[].rule` when a
report has no `rule_id`. `benchmarks/gates.json` also names `summary.errors` and
`summary.advisories` as inspection-report signature fields. These are current
v1-compatible consumers.

## Migration from v1

The v1 fields form this subset:

```json
{
  "active": true,
  "root": "<resolved project root>",
  "findings": [
    {
      "severity": "error",
      "rule": "R-contract-version",
      "path": "CONTRACT.md",
      "message": "CONTRACT.md must start with a version"
    }
  ],
  "summary": {
    "errors": 1,
    "advisories": 0
  }
}
```

Schema v2 retains that subset and adds report context and richer finding data:

```json
{
  "schema_version": 2,
  "scope": "deterministic-structural-inspection",
  "active": true,
  "complete": true,
  "root": "<resolved project root>",
  "configuration": {
    "path": "<configuration path>",
    "schema_version": 1,
    "valid": true
  },
  "coverage": {
    "implemented_rules": [],
    "manual_rules": [],
    "planned_rules": [],
    "not_applicable_rules": []
  },
  "exceptions": [],
  "findings": [
    {
      "rule_id": "R-REPL-002",
      "runtime_alias": "R-contract-version",
      "level": "REQUIRED",
      "severity": "error",
      "state": "fail",
      "path": "CONTRACT.md",
      "message": "CONTRACT.md must start with a version",
      "evidence": [],
      "remediation": null,
      "confidence": null,
      "rule": "R-contract-version"
    }
  ],
  "summary": {
    "errors": 1,
    "warnings": 0,
    "advisories": 0,
    "unknown": 0,
    "suppressed": 0
  }
}
```

The additive fields are `schema_version`, `scope`, `complete`, `configuration`,
`coverage`, `exceptions`, `summary.warnings`, `summary.unknown`,
`summary.suppressed`, and the finding fields `rule_id`, `runtime_alias`,
`level`, `state`, `evidence`, `remediation`, and `confidence`.

`active`, `root`, `findings[].severity`, `findings[].path`,
`findings[].message`, `summary.errors`, and `summary.advisories` retain their
v1 meanings, types, and positions in the object hierarchy. `findings[].rule`
also remains as the deprecated compatibility key, with its v1 runtime-string
value. A v1 consumer that reads only the v1 fields continues to work without
changes against a v2 report.

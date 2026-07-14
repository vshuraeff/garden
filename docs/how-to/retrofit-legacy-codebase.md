---
owner: vshuraeff
last_reviewed: 2026-07-14
review_on:
  - rule-change
  - config-schema-change
---

# How to retrofit GARDEN onto a legacy codebase

Adopt GARDEN in an existing codebase through measurement, strangler-style extraction,
and ratcheted enforcement rather than a rewrite. For the principles being applied, see
[reference/principles.md](../reference/principles.md).

## 1. Measure before changing anything

Record these six baseline fields with a date and measurement method:

- median files opened per task;
- duplicate findings from clone detection;
- changed-module count;
- escaped regressions;
- CI rule coverage, defined as the share of stated invariants enforced by a
  deterministic gate;
- unknown or incomplete audit count, covering items an audit could not evaluate.

A project may add search-miss rate as an EXPERIMENTAL diagnostic. Do not substitute it
for one of the six baseline fields or assign a universal threshold before collecting a
project-specific baseline.

- Action: sample a stated task window for files opened and modules changed, run clone
  detection, count regressions that escaped the selected gates, map documented
  invariants to CI checks, and count audit items lacking enough evidence for a result.
- Acceptance signal: all six dated baseline fields are recorded with methods that a
  later retrofit pass can repeat; any search-miss measurement is labeled EXPERIMENTAL.

## 2. Extract capabilities strangler-style

Do not restructure the whole codebase at once. Read the effective `.garden.toml`, pick
one capability, and move it toward the project's declared `children`, `explicit`,
`markers`, or `none` strategy while the legacy path remains available behind one
cutover point. Treat `markers` resolution as EXPERIMENTAL and unknown until the project
defines a marker format. A vertical slice is one valid target when the project selects
it, not a required root-level layout.

- Action: choose the highest-traffic or highest-change-frequency capability, extract it
  into its configured location with a stable mapping to its tests and operational
  artifacts, and redirect callers through one router or feature flag.
- Acceptance signal: the extracted capability resolves through the configured strategy,
  its tests are colocated or mapped through `tests.test_roots`, and no caller reaches the
  old implementation directly before removal.

Keep both implementations reachable behind the single cutover point until the new
capability has demonstrated the expected behavior through the agreed cutover period.
Remove the legacy implementation only after characterization and compatibility evidence
cover the behavior being replaced.

## 3. Run naming consolidation passes

Legacy codebases accumulate overlapping vocabulary (**G**). Consolidate within each
bounded context rather than forcing one repository-wide synonym.

- Action: for each touched concept, choose the canonical name for its bounded context,
  write it to `.garden.toml`'s configured `naming.registry` path when naming is required,
  and rename references within touched files only. Use root `naming-registry.txt` only as
  the legacy fallback and add a translation map where two contexts retain different
  names.
- Acceptance signal: every touched concept has one canonical name in its context, the
  configured registry validates, and the extraction introduces no undocumented synonym.

Do not chase every legacy occurrence across the codebase in one pass. Leave untouched
spellings until a later extraction reaches their bounded context, and record the
translation needed at any boundary crossed in the meantime.

## 4. Add contracts to public seams before touching internals

Before modifying a public legacy seam, capture its current observable behavior and
compatibility evidence (**R**). Characterization tests come before the behavior-
preserving rewrite.

- Action: classify the seam as public or private. For a public, persisted,
  independently deployed, external, or explicitly versioned boundary, record its
  inputs, outputs, errors, behavior, compatibility policy, and applicable replacement
  evidence in an accepted contract artifact. Keep private modules unversioned.
- Acceptance signal: characterization or compatibility tests capture current observable
  behavior before the first internal change, and only designated versioned boundaries
  carry a SemVer obligation.

## 5. Ratchet lint rules instead of enforcing them everywhere at once

Applying strict deterministic gates (**D**) to an entire legacy codebase at once usually
fails outright. Ratchet instead: new and touched code is held to the configured rule,
while untouched legacy violations remain visible as warnings.

- Action: configure lint rules to fail on new or modified files and to warn on untouched
  legacy files; tighten the boundary over time as more files are touched.
- Acceptance signal: CI fails when a newly written or modified file violates a rule and
  does not report an untouched legacy violation as a clean pass.

```text
# ratchet config (pseudocode)
rule "no-implicit-any": error on files changed after 2026-01-01, warn otherwise
rule "one-canonical-name": error in migrated bounded contexts, warn elsewhere
```

Track the warning count over time as a progress signal alongside the baseline in step 1.

See [set-up-verification-gates.md](set-up-verification-gates.md) for the full gate
pipeline this step plugs into.

## 6. Know when not to retrofit

Skip or defer an area when:

- it is scheduled for deprecation or replacement within the current planning horizon;
- it has no active development and no likely agent edits;
- its project-specific baseline already shows low change-distance, few duplicate
  findings and escaped regressions, adequate CI rule coverage, and no material unknown
  audit items.

- Action: compare each candidate area with its measured baseline and planned lifetime.
- Acceptance signal: root `retrofit-log.md` records one line per retrofit, skip, or defer
  decision with the area and reason, so the decision does not need to be rediscovered.

## Next steps

- Setting up the deterministic gates referenced in step 5:
  [set-up-verification-gates.md](set-up-verification-gates.md).
- Applying GARDEN to a new codebase from scratch:
  [apply-to-new-project.md](apply-to-new-project.md).
- Background on why this is incremental rather than a rewrite:
  [explanation/the-garden-model.md](../explanation/the-garden-model.md).

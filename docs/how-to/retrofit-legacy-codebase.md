---
owner: vshuraeff
last_reviewed: 2026-07-14
review_on:
  - rule-change
---

# How to retrofit GARDEN onto a legacy codebase

This guide covers incremental adoption of GARDEN in an existing codebase that was not
built with agent-first principles. Do not attempt a rewrite; retrofit through
measurement, strangler-style extraction, and ratcheted enforcement. For the principles
being applied, see [reference/principles.md](../reference/principles.md).

## 1. Measure before changing anything

Establish a baseline so you can tell whether the retrofit is working.

- Action: measure the search-miss rate (how often an agent fails to find an existing
  utility and reimplements it), the duplication level (copy-pasted and cloned code as a
  share of changed lines), and current gate coverage (share of stated invariants that
  are checked by a type, lint rule, test, or CI job rather than by prose).
- Acceptance signal: you have three baseline numbers recorded and dated, so later passes
  can show delta.

Gather the search-miss rate by sampling recent agent sessions or pull requests and
checking whether a new function duplicates an existing one that a grep for its purpose
would have surfaced. Gather duplication from a clone-detection tool run once over the
current tree. Gather gate coverage by listing the invariants stated in existing docs or
comments and checking, one by one, whether a type, lint rule, or test currently fails if
the invariant is violated.

## 2. Extract slices strangler-style

Do not restructure the whole codebase at once. Pick one capability at a time and extract
it into an atomic vertical slice (**A**) alongside the legacy code, routing new work to
the slice while the old implementation keeps serving until it is fully replaced.

- Action: choose the highest-traffic or highest-change-frequency capability first,
  extract it into its own directory with entry point, logic, data access, and colocated
  tests, and redirect callers to the new slice.
- Acceptance signal: the extracted capability's tests are colocated with its slice, and
  no caller reaches the old implementation for that capability anymore.

During extraction, keep both implementations reachable behind a single call site (a
router or a feature flag) so the cutover is reversible; remove the legacy implementation
only after the new slice has run in production long enough to catch behavioral gaps the
extracted contract did not anticipate.

## 3. Run naming consolidation passes

Legacy codebases typically accumulate synonym sprawl (**G**). Consolidate incrementally
rather than renaming everything at once.

- Action: for each concept touched by a slice extraction, pick the one canonical name,
  record it in a naming registry, and rename references within the touched files as you
  go; do not do a codebase-wide rename in one pass.
- Acceptance signal: every concept touched during the retrofit has exactly one name in
  the naming registry, and no new synonym is introduced by the extraction.

For example, if a legacy codebase calls the same concept `order`, `purchase`, and
`txn` across different modules, the first slice that touches any of them picks one name
(`order`), records it, and renames only the references inside that slice's new
directory. The other two spellings stay until a later slice extraction reaches them —
do not chase every occurrence across the whole codebase in one pass.

## 4. Add contracts to seams before touching internals

Before modifying a legacy component's internals, write down its contract (**R**) as
observed from its current callers. This turns an implicit dependency into an explicit
one and gives you a regression net.

- Action: for each seam you are about to extract or modify, write the contract (inputs,
  outputs, errors) from the component's current observable behavior before changing any
  internal code.
- Acceptance signal: a contract file exists and is versioned next to the seam before the
  first internal change lands.

## 5. Ratchet lint rules instead of enforcing them everywhere at once

Applying strict deterministic gates (**D**) to an entire legacy codebase at once usually
fails outright. Ratchet instead: new and touched code is held to the full standard, old
untouched code is grandfathered.

- Action: configure lint rules to fail on new or modified files and to warn (not fail) on
  untouched legacy files; tighten the boundary over time as more files are touched.
- Acceptance signal: CI fails when a newly written or modified file violates a rule, and
  does not fail on an untouched legacy file that predates the rule.

```text
# ratchet config (pseudocode)
rule "no-implicit-any": error on files changed after 2026-01-01, warn otherwise
rule "one-canonical-name": error on files inside an already-extracted slice, warn elsewhere
```

Track the warn count over time; a shrinking warn count is the retrofit's real progress
metric, independent of the baseline in step 1.

See [set-up-verification-gates.md](set-up-verification-gates.md) for the full gate
pipeline this step plugs into.

## 6. Know when not to retrofit

Retrofitting has a cost. Skip it, or defer it, when:

- the component is scheduled for deprecation or replacement within the current planning
  horizon — contract-first extraction work would be thrown away;
- the component has no active development and no agent is expected to edit it soon —
  requisite context is not currently being spent on it, so the retrofit yields little;
- the measured baseline (step 1) shows low search-miss rate and low duplication for that
  area already — the retrofit budget is better spent elsewhere.

- Action: before retrofitting a given area, check it against the three conditions above.
- Acceptance signal: `retrofit-log.md` at the project root records one line per decision
  stating why an area was retrofitted or skipped, so the decision is not re-litigated
  later.

## Next steps

- Setting up the deterministic gates referenced in step 5:
  [set-up-verification-gates.md](set-up-verification-gates.md).
- Applying GARDEN to a new codebase from scratch:
  [apply-to-new-project.md](apply-to-new-project.md).
- Background on why this is incremental rather than a rewrite:
  [explanation/the-garden-model.md](../explanation/the-garden-model.md).

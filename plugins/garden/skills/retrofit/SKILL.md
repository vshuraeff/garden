---
name: retrofit
description: "Retrofit an existing codebase to GARDEN through measured, strangler-style adoption and ratcheted gates. Use for requests such as retrofit legacy codebase, make this codebase agent-friendly, adopt GARDEN in an existing project, incrementally add agent-first structure, or modernize legacy architecture for agents."
---

# Retrofit a legacy codebase

Read `references/principles.md` relative to the plugin root before deciding how to apply a GARDEN rule. Read the sibling `references/glossary.md` before applying terms such as managed duplication, one-context task, or vertical slice.

Treat mechanizable MUST rules as gate work, not instruction-file work. The N-principle evidence reports roughly 25–40% compliance for instruction-file-only rules and roughly 95% for the same rule enforced by a runtime hook or deterministic gate. Use prose to preserve intent and gates to enforce behavior.

Work through these steps in order. Do not advance while the current acceptance signal fails.

1. Measure three baselines before changing anything.

   Action: Measure search-miss rate, duplication level, and gate coverage. Record all three numbers with a date in a project document so later passes can show delta. Measure search misses from sampled agent sessions or change history, duplication with a clone-detection pass, and gate coverage by testing whether each stated invariant fails a type, lint, test, or CI check.

   Acceptance signal: Three dated baseline numbers exist and are attributable to their measurement method.

2. Extract slices strangler-style.

   Action: Choose the highest-change-frequency or highest-traffic capability. Extract one vertical slice as a directory at the project root by default, with its entry point, logic, data access, and colocated tests. Keep the legacy and new implementations reachable through one router or feature-flag call site until the new slice proves its behavior; remove the legacy path only then. If a crowded legacy root or a monorepo layout requires a wrapper or other alternative slice root, record that choice as one line in `CONTEXT.md` with a one-sentence justification.

   Acceptance signal: The extracted slice has colocated tests, all external callers route through the one cutover call site, and the legacy path has no direct callers. Remove it only after the new slice has demonstrated the expected behavior through the agreed cutover period. The slice directory sits at the project root, or `CONTEXT.md` records the alternative root and why.

3. Consolidate names per slice.

   Action: For each concept touched by the current slice, choose one canonical name, append its `concept: canonical-name` entry to root `naming-registry.txt`, and rename references only in the touched files. Never run a codebase-wide rename in one pass.

   Acceptance signal: Each touched concept has exactly one registry name and the extraction introduces no new synonym.

4. Add contracts at seams before touching internals.

   Action: Before changing a legacy component's internals, write its current observable inputs, outputs, errors, interface, and examples in a neighboring `CONTRACT.md`. Make the first line `Version: MAJOR.MINOR.PATCH`; point the new slice boundary at this contract rather than the implementation.

   Acceptance signal: A versioned contract exists beside the seam before the first internal change lands, and it describes current observable behavior rather than the intended implementation.

5. Ratchet lint rules.

   Action: Make lint errors fail CI for new or modified files and warnings apply to untouched legacy files. Tighten the warning boundary as slices are touched. Track the warning count over time as the progress metric.

   Acceptance signal: CI fails a newly written or modified file that violates the rule, permits an untouched legacy violation as a warning, and records a warn count that can shrink over time.

6. Apply the when-NOT-to-retrofit test.

   Action: Before retrofitting each area, decide whether it is scheduled for deprecation or replacement, has no active development and no likely agent edits, or already has low search-miss and low duplication baselines. Record every decision, including retrofit, skip, or defer, as one line in root `retrofit-log.md` with the area and reason.

   Acceptance signal: `retrofit-log.md` contains one reasoned line for every evaluated area, so no decision must be rediscovered or re-litigated later.

Read the plugin's `references/principles.md` whenever a retrofit exposes a stated invariant. Add the strongest feasible deterministic check for each mechanizable MUST rule; record a non-mechanizable invariant as a risk rather than relying on an agent's assessment.

---
name: retrofit
description: "Retrofit an existing codebase to GARDEN through measured, strangler-style adoption and ratcheted gates. Use for requests such as retrofit legacy codebase, make this codebase agent-friendly, adopt GARDEN in an existing project, incrementally add agent-first structure, or modernize legacy architecture for agents."
---

# Retrofit a legacy codebase

Read `references/principles.md` relative to the plugin root before deciding how to apply a GARDEN rule. Read the sibling `references/glossary.md` before applying terms such as managed duplication, change-distance, requisite context, or vertical slice.

Treat mechanizable REQUIRED rules as gate work, not instruction-file work. Hooks and deterministic gates enforce a rule far more reliably than an instruction file alone. Use prose to preserve intent and gates to enforce behavior. [CLAIM-N001]

Work through these steps in order. Do not advance while the current acceptance signal fails.

1. Measure the baseline before changing anything.

   Action: Record median files opened per task, duplicate findings from clone detection, changed-module count, escaped regressions, CI rule coverage as the share of stated invariants enforced by deterministic gates, and unknown or incomplete audit count. Date every value and record its measurement method. A project may also measure search-miss rate as an EXPERIMENTAL diagnostic, but it is not part of the required baseline set.

   Acceptance signal: Six dated baseline values exist and are attributable to reproducible measurement methods; any search-miss sample is labeled EXPERIMENTAL.

2. Extract capabilities strangler-style.

   Action: Read the effective `.garden.toml` capability strategy, then choose the highest-change-frequency or highest-traffic capability. Extract it into the layout declared by `capabilities.strategy`, including `children`, `explicit`, `markers`, or `none`. Treat `markers` resolution as EXPERIMENTAL and unknown until a project-defined marker format exists. Keep the legacy and new implementations reachable through one router or feature-flag call site until the new capability proves its behavior; remove the legacy path only then. A vertical slice is valid when the project declares that strategy, but a root-level slice directory is not the universal default.

   Acceptance signal: The extracted capability follows the configured location and test association, all external callers route through the one cutover call site, and the legacy path has no direct callers before removal.

3. Consolidate names per touched context.

   Action: For each concept touched by the current extraction, choose one canonical name within its bounded context and rename references only in the touched files. When `.garden.toml` has a `[naming]` table, write the entry to the path declared by `naming.registry`; use root `naming-registry.txt` only as the legacy fallback. Add an explicit translation map when two bounded contexts retain different names. Never run a codebase-wide rename in one pass.

   Acceptance signal: Each touched concept has one canonical name in its bounded context, the configured registry records it when naming is required, and the extraction introduces no undocumented synonym.

4. Add contracts at public seams before touching internals.

   Action: Before changing a legacy public boundary, capture its observable inputs, outputs, errors, behavior, and compatibility in an accepted contract artifact, and add characterization or compatibility tests. Add a `Version:` line only when the boundary is published, independently deployed, persisted, external, or explicitly designated as versioned; keep private internal modules under Git history instead.

   Acceptance signal: The seam's current behavior is executable before the first internal change, and every versioned boundary states its compatibility policy without imposing SemVer on private modules.

5. Ratchet lint rules.

   Action: Make lint errors fail CI for new or modified files and warnings apply to untouched legacy files. Tighten the warning boundary as capabilities are touched. Track the warning count over time as a progress signal.

   Acceptance signal: CI fails a newly written or modified file that violates the rule, permits an untouched legacy violation as a warning, and records a warning count that can shrink over time.

6. Apply the when-NOT-to-retrofit test.

   Action: Before retrofitting each area, decide whether it is scheduled for deprecation or replacement, has no active development and no likely agent edits, or already performs well against the project's baseline for change-distance, duplicate findings, escaped regressions, CI rule coverage, and audit completeness. Record every decision, including retrofit, skip, or defer, as one line in root `retrofit-log.md` with the area and reason.

   Acceptance signal: `retrofit-log.md` contains one reasoned line for every evaluated area, so no decision must be rediscovered or re-litigated later.

Read the plugin's `references/principles.md` whenever a retrofit exposes a stated invariant. Add the strongest feasible deterministic check for each mechanizable REQUIRED rule; record a non-mechanizable invariant as a risk rather than relying on an agent's assessment.

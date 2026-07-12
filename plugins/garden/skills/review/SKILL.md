---
name: review
description: "Review a change with GARDEN's deterministic-gate-first G/A/R/D/E/N lenses and evidence-based hypotheses. Use for requests such as GARDEN review, review this change with GARDEN lenses, agent-first code review, review agent-authored code, or check a change for GARDEN violations."
---

# Review with GARDEN lenses

Read `${CLAUDE_PLUGIN_ROOT}/references/review-procedure.md` before reviewing. Read `${CLAUDE_PLUGIN_ROOT}/references/principles.md` for the complete GARDEN rules, and `${CLAUDE_PLUGIN_ROOT}/references/glossary.md` when a review depends on a defined term.

Treat mechanizable MUST rules as candidate deterministic gates. The N-principle evidence reports roughly 25–40% compliance for instruction-file-only rules, compared with roughly 95% when the rule is enforced by a runtime hook or deterministic gate. Do not rely on a review finding to enforce a rule that the target stack can type-check, lint, test, or gate.

1. Check deterministic gates before reading the change.

   State whether type check, lint, unit tests, and clone detection each ran and passed or failed before writing any finding. Do not manually re-verify a fact that a passing gate already proved. Treat a gate that did not run as a D-lens finding rather than substituting manual review for it.

2. Apply the G lens: naming and discoverability.

   Check that every new or renamed identifier maps to one naming-registry entry, and that new domain logic remains statically searchable rather than relying on string-built identifiers, reflection, or convention routing. Cite the identifier or call site and the canonical name or broken search path.

3. Apply the A lens: slice boundaries and duplication budget.

   Check whether the change remains within its capability slice, reaches through another slice's explicit contract rather than its internals, and avoids an abstraction before three concrete usages. Cite the cross-slice reach or abstraction and state its relation to the clone-detection budget.

4. Apply the R lens: contract drift.

   Check whether observable behavior changed without a corresponding contract update, or whether code diverged from a contract that should be corrected first. Identify the `CONTRACT.md` clause that agrees or conflicts with the changed behavior.

5. Apply the D lens: invariants without gates.

   Identify each new assumption the change relies on that lacks a type, lint rule, test, or CI gate. State the invariant in plain language and propose the specific deterministic gate that would detect a future violation.

6. Apply the E lens: implicit couplings.

   Check for temporal coupling, magic values, ambient dependencies, insufficiently typed boundary data, and errors that omit what failed, why, or caller action. State the explicit parameter, type, constant, builder, or error form that would replace the coupling.

7. Apply the N lens: knowledge hop distance.

   Check that knowledge needed to understand or extend the change is reachable within one hop from the edit site through a README, linked contract, or `CONTEXT.md` entry. Treat information known only from the review conversation as missing documentation; name the README or context location that would close the gap.

8. Report findings as verifiable hypotheses.

   Cite an exact file and line range for every finding, name the specific GARDEN rule, and avoid splitting one underlying issue into several findings. The reported LLM-review noise profile is roughly 24% false negatives and up to 50% false positives; present findings as falsifiable hypotheses for a human or deterministic check to confirm, not as facts or verdicts.

9. Never self-certify.

   Output findings and evidence only. Do not use `approved`, `safe to merge`, or an equivalent self-certifying conclusion. Leave merge decisions to deterministic gates and the separate decision process.

Recommend delegation to the plugin's `garden-reviewer` agent when an isolated review is preferable. Do not have the implementer act as the reviewer of its own change.

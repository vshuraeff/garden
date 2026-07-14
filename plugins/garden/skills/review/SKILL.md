---
name: review
description: "Review a change with GARDEN's deterministic-gate-first G/A/R/D/E/N lenses and evidence-based hypotheses. Use for requests such as GARDEN review, review this change with GARDEN lenses, agent-first code review, review agent-authored code, or check a change for GARDEN violations."
---

# Review with GARDEN lenses

Read `references/review-procedure.md` relative to the plugin root before reviewing. Read the sibling `references/principles.md` for the complete GARDEN rules, and `references/glossary.md` when a review depends on a defined term.

Treat mechanizable REQUIRED rules as candidate deterministic gates. Hooks and deterministic gates enforce a rule far more reliably than an instruction file alone. Do not rely on a review finding to enforce a rule that the target stack can type-check, lint, test, or gate. [CLAIM-N001]

Use the GARDEN lenses as one part of the review. Also evaluate correctness, compatibility, security, operability, architecture boundaries, and evidence quality where the change makes those concerns relevant.

1. Check deterministic gates before reading the change.

   State whether type check, lint, unit tests, and clone detection each ran and passed or failed before writing any finding. Do not manually re-verify a fact that a passing gate already proved. Treat a gate that did not run as unknown verification evidence and a `D-VER-*` finding rather than substituting manual review for it.

2. Apply the G lens: naming and discoverability.

   Resolve the project's actual naming mechanism first: use `.garden.toml`'s `naming.registry` path when configured, otherwise use root `naming-registry.txt` only as the legacy fallback. Check that new or renamed domain concepts use the canonical name within their bounded context, that boundary vocabulary has an explicit translation map where needed, and that production relationships remain recoverable through the project's stated graph mechanism. Cite applicable `G-DISC-*` rule IDs and the identifier, call site, registry entry, manifest, or broken resolution path.

3. Apply the A lens: capability boundaries and duplication budget.

   Read the effective `.garden.toml` capability strategy before judging locality. Check the change against the configured `children`, `explicit`, `markers`, or `none` strategy, including shared roots and test association; do not assume root-level vertical slices. Check boundary crossings against declared interfaces and evaluate early abstractions against the configured exception to the rule of three. Cite applicable `A-LOC-*` rule IDs, the resolved capability or unknown mapping, and the relevant cross-boundary reach or clone-detection evidence.

4. Apply the R lens: contract drift.

   Check whether observable behavior changed without a corresponding update to the configured contract or replacement evidence, or whether code diverged from an accepted contract artifact that should be corrected first. Cite applicable `R-REPL-*` rule IDs and identify the clause or evidence that agrees or conflicts with the changed behavior.

5. Apply the D lens: invariants without gates.

   Identify each new assumption the change relies on that lacks a type, lint rule, test, or CI gate. State the invariant in plain language and propose the specific deterministic gate that would detect a future violation.

6. Apply the E lens: implicit couplings.

   Check for temporal coupling, magic values, ambient dependencies, insufficiently typed boundary data, and errors that omit what failed, why, or caller action. State the explicit parameter, type, constant, builder, or error form that would replace the coupling.

7. Apply the N lens: nearby, maintained knowledge.

   Apply `N-KNOW-004`'s public-boundary, separate-owner, non-obvious-decision, independent-edit, operational-obligation, and navigation-entry signals. Where a signal warrants nearby documentation, check that governed knowledge is linked from its boundary and uses progressive disclosure to expose the requisite context. Treat information known only from the review conversation as missing documentation; cite the applicable `N-KNOW-*` rule ID and name the maintained location that would close the gap.

8. Report findings as verifiable hypotheses.

   Cite an exact file and line range for every finding, name the applicable stable `G-`, `A-`, `R-`, `D-`, `E-`, or `N-` rule ID, and avoid splitting one underlying issue into several findings. Report missing evidence, ambiguous applicability, unavailable gates, and unresolved experimental capability markers as `unknown`, never as an implied pass. One CodeX-Verify preprint reported a 50% false-positive rate for its author's system; present findings as falsifiable hypotheses for a human or deterministic check to confirm, not as facts or verdicts. [CLAIM-N003]

9. Never self-certify.

   Output findings and evidence only. Do not use `approved`, `safe to merge`, or an equivalent self-certifying conclusion. Leave merge decisions to deterministic gates and the separate decision process.

When an isolated review is preferable, delegate it to `garden-reviewer`. Claude Code loads the plugin agent directly. Codex loads the project agent after `garden:start` installs `.codex/agents/garden-reviewer.toml`; when that file is absent, spawn a read-only subagent with the same review instructions inline. Wait for the result. Do not have the implementer act as the reviewer of its own change.

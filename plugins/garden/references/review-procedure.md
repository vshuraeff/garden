---
owner: vshuraeff
last_reviewed: 2026-07-16
review_on:
  - rule-change
  - evidence-change
---
<!-- Generated from docs/how-to/review-code-as-agent.md. Do not edit directly. Run sync_references.py --write to update. -->

# How to review code as an agent

This guide is written to be used directly as a review prompt for an agent conducting a
GARDEN-lens code review. It assumes the deterministic gates described in
[set-up-verification-gates.md](./set-up-verification-gates.md) already ran. For the rule
definitions referenced below, see
[reference/principles.md](./principles.md) and
[reference/checklist.md](./checklist.md).

## 1. Check what the gates already covered

Before reading a single line for review, check the CI results for this change.

- Action: read the type check, lint, test, and clone-detection results for the change
  under review.
- Acceptance signal: you can state, for each of those four gates, whether it ran and
  whether it passed, before writing any review finding.

Do not re-litigate anything a passing gate already proved. If lint enforces an import
boundary and lint passed, do not raise a finding about that boundary; instead, look for
what the gates cannot see. Treat a gate that did not run as unknown verification evidence
and a `D-VER-*` finding under the D lens in step 5, rather than trying to manually verify
what the missing gate would have checked.

## 2. Apply the G lens: naming and discoverability

- Action: resolve the project's actual naming mechanism first: use the effective
  `.garden.toml` `naming.registry` path when configured, otherwise use root
  `naming-registry.txt` as the legacy fallback. Check that new or renamed domain concepts
  use the canonical name within their bounded context, that boundary vocabulary has an
  explicit translation map where needed, and that production relationships remain
  recoverable through the project's stated graph mechanism; registries and generated
  graphs count as discoverability evidence. Cite applicable `G-DISC-*` rule IDs.
- Acceptance signal: each finding names the specific identifier, boundary translation,
  call site, registry entry, manifest, or broken resolution path and states the canonical
  name or graph evidence it requires.

## 3. Apply the A lens: capability boundaries and duplication budget

- Action: read the effective `.garden.toml` capability strategy before judging locality:
  `children`, `explicit`, `markers`, or `none`, including shared roots. Check boundary
  crossings against declared interfaces, test placement against the project's configured
  `[tests]` patterns and mapping, and early abstractions against the configured exception
  to the rule of three. Cite applicable `A-LOC-*` rule IDs.
- Acceptance signal: each finding cites the resolved capability or unknown mapping, the
  relevant cross-boundary reach, test mapping, or premature abstraction, with file paths,
  and states the applicable clone-detection evidence.

## 4. Apply the R lens: contract drift

- Action: check whether observable behavior changed without a corresponding update to the
  configured contract or replacement evidence, or whether code diverges from an accepted
  contract artifact that should be corrected first. Cite applicable `R-REPL-*` rule IDs.
- Acceptance signal: each finding identifies the relevant contract artifact or replacement
  evidence and the clause or evidence that agrees or conflicts with the changed behavior.

## 5. Apply the D lens: new invariants without gates

- Action: check whether the change introduces a new invariant (an assumption the code
  depends on) that is not backed by a type, lint rule, or test. Cite applicable `D-VER-*`
  rule IDs.
- Acceptance signal: each finding names the invariant in plain language and proposes the
  specific deterministic gate (type, lint rule, or test) that would catch a future
  violation.

## 6. Apply the E lens: implicit couplings

- Action: check for hidden ordering requirements between operations, magic values without
  named constants, dependencies passed through ambient state instead of parameters, and
  errors that do not state what failed, why, and what the caller can do. Cite applicable
  `E-EXPL-*` rule IDs.
- Acceptance signal: each finding points to the specific implicit coupling and states the
  explicit form it should take.

## 7. Apply the N lens: nearby, maintained knowledge

- Action: apply `N-KNOW-004`'s public-boundary, separate-owner, non-obvious-decision,
  independent-edit, operational-obligation, and navigation-entry signals. Where a signal
  warrants nearby documentation, check that governed knowledge is linked from its boundary
  and uses progressive disclosure to expose the requisite context. Treat information known
  only from the review conversation as missing documentation. Cite applicable `N-KNOW-*`
  rule IDs.
- Acceptance signal: each finding states what governed knowledge is missing and the
  maintained location that should link from the relevant boundary to close the gap.

## 8. Report findings as verifiable hypotheses, never as verdicts

LLM review carries a real noise profile. One single-author preprint evaluated 99 samples
with the author's own four-agent system and reported a 50% false-positive rate for that
system. Treat every finding from this review as a hypothesis a human or a deterministic
check must confirm, not as a fact or verdict.
([CLAIM-N003](./evidence-registry.md#claim-n003))

Report missing evidence, ambiguous applicability, unavailable gates, and unresolved
experimental capability markers as `unknown`, never as an implied pass.

- Action: for every finding, cite the exact file and line range as evidence, state the
  specific GARDEN rule it violates, and avoid restating the same underlying issue as
  multiple findings to inflate apparent confidence.
- Acceptance signal: each finding is falsifiable — a reader can check the cited file and
  either confirm or reject it without needing to trust the reviewing agent's assessment.

Running several passes over the same change with genuinely different lenses (as in
steps 2-7) is what the evidence supports; running the same lens multiple times and
treating agreement as confirmation is not — consensus among samples from the same model
is not independent evidence of correctness.

## 9. Never self-certify

- Action: do not report the change as "approved," "safe to merge," or equivalent. State
  findings and their supporting evidence only; leave the merge decision to the
  deterministic gates and to a human or a separate decision process.
- Acceptance signal: the review output contains no self-certifying verdict, only findings
  with evidence and, where applicable, a proposed gate.

## Next steps

- The gate pipeline this review sits downstream of:
  [set-up-verification-gates.md](./set-up-verification-gates.md).
- The full rule set behind each lens:
  [reference/principles.md](./principles.md).
- Machine-checkable version of these lenses: [reference/checklist.md](./checklist.md).

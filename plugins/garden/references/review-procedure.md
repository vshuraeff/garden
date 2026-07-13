<!-- Generated from docs/how-to/review-code-as-agent.md. Do not edit directly. Run sync_references.py --write to update. -->
# How to review code as an agent

This guide is written to be used directly as a review prompt for an agent conducting a
GARDEN-lens code review. It assumes the deterministic gates described in
[set-up-verification-gates.md](set-up-verification-gates.md) already ran. For the rule
definitions referenced below, see
[reference/principles.md](../reference/principles.md) and
[reference/checklist.md](../reference/checklist.md).

## 1. Check what the gates already covered

Before reading a single line for review, check the CI results for this change.

- Action: read the type check, lint, test, and clone-detection results for the change
  under review.
- Acceptance signal: you can state, for each of those four gates, whether it ran and
  whether it passed, before writing any review finding.

Do not re-litigate anything a passing gate already proved. If lint enforces an import
boundary and lint passed, do not raise a finding about that boundary; instead, look for
what the gates cannot see. If a gate did not run at all (for example, no contract test
exists for the slice being changed), treat that absence itself as a finding under the D
lens in step 5, rather than trying to manually verify what the missing gate would have
checked.

## 2. Apply the G lens: naming and discoverability

- Action: check whether every new or renamed identifier maps to exactly one entry in the
  project's naming registry, and whether any new domain logic is reachable only through
  string-built identifiers, reflection, or convention-based routing.
- Acceptance signal: each finding names the specific identifier or call site and states
  which canonical name it should use, or which static-search path is broken.

## 3. Apply the A lens: slice boundaries and duplication budget

- Action: check whether the change stays inside its slice's directory, whether it reaches
  into another slice's internals instead of its explicit interface, and whether it
  introduces an abstraction before three concrete usages exist.
- Acceptance signal: each finding cites the specific cross-slice reach or the premature
  abstraction, with file paths, and states whether it falls within the clone-detection
  budget or exceeds it.

## 4. Apply the R lens: contract drift

- Action: check whether the change modifies a component's observable behavior without
  updating its contract, or whether it patches around a contract instead of correcting
  the contract first.
- Acceptance signal: each finding identifies the contract file and the specific clause
  that no longer matches the code, or confirms no drift was found.

## 5. Apply the D lens: new invariants without gates

- Action: check whether the change introduces a new invariant (an assumption the code
  depends on) that is not backed by a type, lint rule, or test.
- Acceptance signal: each finding names the invariant in plain language and proposes the
  specific deterministic gate (type, lint rule, or test) that would catch a future
  violation.

## 6. Apply the E lens: implicit couplings

- Action: check for hidden ordering requirements between operations, magic values without
  named constants, dependencies passed through ambient state instead of parameters, and
  errors that do not state what failed, why, and what the caller can do.
- Acceptance signal: each finding points to the specific implicit coupling and states the
  explicit form it should take.

## 7. Apply the N lens: knowledge hop distance

- Action: check whether the knowledge needed to understand or safely extend this change
  is reachable within one hop from the edit site (a README, a linked contract, a context
  file entry), or whether it exists only in the reviewing agent's own memory of the
  conversation.
- Acceptance signal: each finding states what documentation is missing and where it
  should live (which README or context file) to close the hop-distance gap.

## 8. Report findings as verifiable hypotheses, never as verdicts

LLM review carries a real noise profile. One single-author preprint evaluated 99 samples
with the author's own four-agent system and reported a 50% false-positive rate for that
system. Treat every finding from this review as a hypothesis a human or a deterministic
check must confirm, not as a fact or verdict.
([CLAIM-N003](../evidence/evidence-registry.md#claim-n003))

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
  [set-up-verification-gates.md](set-up-verification-gates.md).
- The full rule set behind each lens:
  [reference/principles.md](../reference/principles.md).
- Machine-checkable version of these lenses: [reference/checklist.md](../reference/checklist.md).

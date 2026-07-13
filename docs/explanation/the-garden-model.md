# The garden model

## A codebase as something tended, not built once

The metaphor GARDEN takes its name from is deliberately unglamorous: a codebase is a
garden that agents continuously tend, not a building that is constructed once and then
occupied. A building, once erected, mostly just stands there; a garden left alone does
not stand still — it grows wild. Paths close over, beds run into each other, one
aggressive planting crowds out everything nearby. Tending is not a one-time setup cost;
it is an ongoing practice that has to keep pace with how fast the garden grows.

This is not a comforting analogy chosen for effect. It is, as far as the available
evidence goes, an observation about code churn under sustained agent-driven change. The
GitClear AI Code Quality report examined 211 million changed lines from January 2020
through December 2024 and observed copy-pasted code rising from 8.3% to 12.3% of changed
lines, refactored or moved code falling from 24.1% to 9.5%, and blocks of duplicated code
growing roughly eightfold. These observational metrics do not identify the cause of the
trend or prove the effect of a particular architecture practice. GARDEN's six principles
are a countervailing practice for the risks those metrics make visible: tending work that
keeps a codebase navigable, extensible, and trustworthy as agents keep touching it, year
over year, without a ground-up rewrite.
([CLAIM-N004](../evidence/evidence-registry.md#claim-n004))

## The six principles as a system, not a checklist

Each GARDEN principle addresses a specific mechanical constraint an agent works under
(see [why-agent-first-principles.md](why-agent-first-principles.md) for the mechanics
themselves), but none of the six functions well in isolation. They are load-bearing for
each other:

- **G — Grep-first Discoverability** makes **A — Atomic Vertical Slices** findable: a
  slice is only atomic in practice if an agent can locate it in the first place.
- **A** makes **R — Regenerable Components** affordable: a small, self-contained slice
  is cheap to specify precisely and cheap to rewrite from scratch, where a sprawling
  module is neither.
- **R** makes **D — Deterministic Verification** meaningful: a contract gives
  deterministic gates something precise to check a component against, rather than
  checking code against vague intent.
- **D** makes **E — Explicit Everything** enforceable: explicitness is only durable once
  it is captured as a lint rule or type, not left as a habit that erodes commit by
  commit.
- **E** makes **N — Navigable Knowledge** cheaper: the less that is implicit, the less
  documentation has to work to explain the gaps.
- **N** makes **G** work at the scale of a whole repository: naming conventions
  documented once, and findable at the point of use, are what let grep-first search
  stay reliable as the codebase grows past what any single session can hold.

The loop closes: better navigability at repo scale (N) is exactly what keeps
discoverability (G) working as the codebase grows, which is where the chain started.
None of the six is optional scaffolding around the "real" principles; each is the
precondition the next one needs. For the full statement of each principle's rules,
rationale, and anti-patterns, see [../reference/principles.md](../reference/principles.md).

## What optimizing for agents does not mean

It is easy to hear "optimize for the agent as primary reader" and infer something
GARDEN does not claim.

**It does not mean lower quality.** Grep-first naming, small slices, explicit contracts,
deterministic gates, explicit interfaces, and navigable documentation are not
shortcuts — several of them require more upfront discipline than the looser conventions
they replace. The evidence base for GARDEN is largely a record of what happens when that
discipline is absent: search misses, duplicated blocks, spec drift, invariants that only
exist in someone's head. Optimizing for the agent as reader is, in practice, optimizing
for correctness and long-term maintainability, because those are exactly the properties
an agent's mechanical limits punish first when they are missing.

**It does not mean removing humans.** Under GARDEN, humans set intent, define
constraints, and own the "why." **Regenerable Components** treats code as expendable
precisely so that the parts worth preserving carefully — the contract, the rationale,
the trade-off record — are the parts a human authored or approved, not the
implementation detail an agent can reproduce on request. **Navigable Knowledge**
explicitly reserves the human-authored "why" as a MUST, distinct from documentation an
agent may draft: agents may draft explanatory content, but humans approve it before it
becomes the record other agents will trust. GARDEN redistributes labor; it does not
eliminate the human role in the loop, and the principle most directly responsible for
that boundary is Deterministic Verification's refusal to let an agent self-certify its
own work.

## Trade-offs, stated honestly

GARDEN is not free. Adopting it costs something in specific, predictable places, and the
model is more credible for naming them rather than glossing over them.

**Managed duplication has a real cost.** Tolerating duplicate code until a
clone-detection signal justifies extracting an abstraction means living with more
repeated logic than a strict-DRY codebase would carry at any given moment. That
repetition is a deliberate trade: it avoids the cost of premature abstractions that
entangle unrelated call sites, but it is still a cost, paid in the form of more surface
area to eventually reconcile once the clone-detection threshold is crossed. A team that
never runs the reconciliation step will accumulate genuine bit-rot, not just
"managed" duplication.

**Explicit boundaries add ceremony.** Requiring dependencies to point at contracts
rather than concrete implementations, requiring typed interfaces at every boundary, and
requiring a spec precise enough to regenerate a component from scratch all add code and
process that a smaller, more tightly coupled design would not need. For a genuinely
small, short-lived script, this ceremony can cost more than it returns; GARDEN's target
is systems that go to production, integrate with other systems, and need to survive
years of extension, not every throwaway snippet an agent produces.

**Navigable knowledge requires upkeep discipline.** A README in every significant
directory and a short root context file are only assets while someone keeps them
accurate; an informal single-author practitioner report suggests that curated context
files help while autogenerated, unmaintained ones hurt. Navigable Knowledge is not
satisfied by writing the documentation once — it requires deleting documentation that
has drifted from the code it describes, which is its own recurring cost.
([CLAIM-N001](../evidence/evidence-registry.md#claim-n001))

These costs are the price of the properties GARDEN targets — findability, regenerable
components, gates that do not depend on any one model's judgment, and knowledge reachable
within one hop. None of them are amortized to zero; they are traded deliberately against
the failure modes described in
[why-agent-first-principles.md](why-agent-first-principles.md), and against the classic
principles GARDEN inherits from and diverges from, discussed in
[relation-to-classic-principles.md](relation-to-classic-principles.md).

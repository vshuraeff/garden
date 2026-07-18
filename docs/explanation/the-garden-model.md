---
owner: vshuraeff
last_reviewed: 2026-07-16
review_on:
  - rule-change
  - evidence-change
---

# The garden model

## A codebase as something tended, not built once

The metaphor GARDEN takes its name from is deliberately unglamorous: a codebase is a
garden that people and agents continuously tend, not a building constructed once and
then occupied. A building, once erected, mostly just stands there; a garden left alone
does not stand still. Paths close over, beds run into each other, and one aggressive
planting crowds out everything nearby. Tending is not a one-time setup cost; it has to
keep pace with how fast the garden grows.

This is not a comforting analogy chosen for effect. The available evidence includes
observations about code churn under sustained agent-driven change. The GitClear AI Code
Quality report examined 211 million changed lines from January 2020 through December
2024 and observed copy-pasted code rising from 8.3% to 12.3% of changed lines,
refactored or moved code falling from 24.1% to 9.5%, and blocks of duplicated code
growing roughly eightfold. These observational metrics do not identify the cause of
the trend or prove the effect of a particular architecture practice. GARDEN's six
principles are a countervailing practice for the risks those metrics make visible:
tending work that keeps a codebase navigable, changeable, and trustworthy as agents
keep touching it without a ground-up rewrite.
([CLAIM-N004](../evidence/evidence-registry.md#claim-n004))

## The six principles as a system, not a checklist

Each GARDEN principle addresses a mechanical constraint an agent works under (see
[why-agent-first-principles.md](why-agent-first-principles.md) for those mechanics),
but none of the six functions well in isolation. The principles form a chain of
evidence rather than a prescribed repository shape or toolchain:

- **G — Graph-resolvable Discoverability** makes a capability's full change surface
  findable through a stated relationship mechanism.
- **A — Adaptive Capability Locality** keeps that surface proportionate to the change
  by minimizing unnecessary modules, crossings, context, handoffs, and coupling.
- **R — Replaceable Components** records the evidence that says what a replacement
  must preserve at its boundary.
- **D — Defense-in-depth Verification** exercises those claims at the verification
  levels relevant to the change's risk.
- **E — Explicit Boundaries and State** exposes the state, policies, and ownership
  that those checks need to observe.
- **N — Nearby, Maintained Knowledge** records the ownership, intent, and residual
  risk that neither code nor generated facts can authoritatively supply.

The loop returns from N to G because maintained knowledge makes the declared graph
mechanisms, boundary maps, and decision records available to the next change. A
relationship that exists only in a previous conversation is not a usable discovery
path. For the full rules, rationale, and anti-patterns behind the six principles, see
[../reference/principles.md](../reference/principles.md).

Graph-resolvable Discoverability does not make static search the canonical path.
`G-DISC-001` requires an in-scope production relationship to be recoverable through at
least one stated mechanism. Grep is one valid mechanism; an AST, LSP, symbol index,
route map, plugin registry, schema registry, or generated wiring can also expose the
same graph. Dynamic dispatch is compatible with the model when a machine-readable
manifest, schema, registry, or generated map reveals its targets.

Adaptive Capability Locality likewise does not impose a universal tree shape.
`A-LOC-001` requires a stated location and ownership strategy that identifies the code,
state, tests, and operational artifacts affecting a production capability.
`.garden.toml` expresses that choice with `capabilities.strategy` set to `children`,
`explicit`, `markers`, or `none`; `markers` currently records experimental intent.
A vertical slice beneath a configured root is one valid use of `children`, alongside
framework-standard layouts, explicit path maps, pipelines, and generated maps. The
question is change-distance — modules touched, boundary crossings, requisite context,
ownership clarity, and coupling — rather than whether a repository follows a prescribed
layout.

## What optimizing for agents does not mean

It is easy to hear "optimize for the agent as a primary reader" and infer something
GARDEN does not claim.

**It does not mean lower quality.** Recoverable relationship maps, proportionate
capability boundaries, boundary evidence, verification at relevant levels, explicit
state, and maintained decision records are not shortcuts. They make assumptions
inspectable by people, tools, and agents. The model does not claim that a single
directory layout, contract format, or review tool produces those properties; it asks a
project to make its relevant relationships and evidence visible enough to check.

**It does not mean removing humans.** Humans own the boundary evidence and the record
of intent and trade-offs. Under `R-REPL-001`, a component whose replacement can affect
correctness, compatibility, or security records the applicable public interface or
schema, behavioral examples, characterization and compatibility tests, migration and
rollback plan, observability expectations, data ownership, and concurrency or ordering
semantics. An agent replacing or rewriting that component works from the recorded
evidence rather than guessing what must survive; any omitted category needs a
boundary-specific reason. `N-KNOW-001` and `N-KNOW-002` keep the governing knowledge
linked, owned, reviewed for staleness, and human-authored. `D-VER-005` then prevents the
implementing agent from being the sole authority for its own change.

## Trade-offs, stated honestly

GARDEN is not free. Adopting it costs something in specific, predictable places, and
the model is more credible for naming those costs than for glossing over them.

**Managed duplication has a real cost.** `A-LOC-005` delays sharing an abstraction
until three concrete uses demonstrate a stable common shape, unless a known boundary,
security control, or platform constraint justifies an earlier extraction. That can
leave more repeated logic in the repository than a strict-DRY approach would accept.
The trade avoids coupling unrelated callers to an abstraction whose shape is still
unclear, but the repeated behavior still needs review and eventual reconciliation when
the evidence justifies it. GitClear's observed changes in churn and clone-detection
metrics are context for measuring that cost in a project, not proof that a particular
layout causes it.

**Explicit boundaries add ceremony.** Boundary contracts, typed interfaces where the
boundary needs them, and replacement evidence add artifacts and review work that a
smaller, tightly coupled design may avoid. The cost is justified only where omitted
information could affect correctness, compatibility, security, or operations:
`E-EXPL-001` defines the public, trust, and persistence boundaries that need contracts,
while `R-REPL-001` defines the evidence a consequential replacement needs. A small,
short-lived script can reasonably have a smaller boundary surface than a system that
integrates with other systems and must absorb years of change.

**Nearby, Maintained Knowledge requires upkeep discipline.** `N-KNOW-004` calls for
nearby navigation or decision documentation when a directory is a public boundary, has
a separate owner, contains non-obvious decisions, is edited independently of siblings,
carries operational obligations, or serves as a navigation entry point. `N-KNOW-007`
keeps that material from restating facts already clear from code or generated artifacts,
and `N-KNOW-001` assigns its owner and staleness trigger. The recurring work is to keep
those decisions current and remove drift, not to satisfy a directory-count convention.
A practitioner report suggests curated context helps while autogenerated, unmaintained
context hurts; its informal, single-author scope does not establish a universal
documentation threshold.
([CLAIM-N001](../evidence/evidence-registry.md#claim-n001))

The costs buy evidence, not certainty: recoverable relationships, a proportionate
change surface, recorded replacement constraints, verification beyond one model's
judgment, and maintained decisions. They remain deliberate trade-offs against the
failure modes described in
[why-agent-first-principles.md](why-agent-first-principles.md), and against the classic
principles GARDEN inherits from and diverges from in
[relation-to-classic-principles.md](relation-to-classic-principles.md). Progressive
disclosure keeps a typical change focused on its bounded requisite context rather than
assuming that every governing fact belongs in the first document a reader opens.

---
owner: vshuraeff
last_reviewed: 2026-07-14
review_on:
  - rule-change
---
<!-- Generated from docs/reference/glossary.md. Do not edit directly. Run sync_references.py --write to update. -->

# GARDEN glossary

Terms below use the meanings given here throughout the GARDEN reference set.
Normative definitions link to [principles.md](./principles.md).

- Document owner: GARDEN plugin maintainers
- Last reviewed: 2026-07-13
- Review trigger: a principle title, normative level, or defined boundary term
  changes
- Executable checks: `plugins/garden/tools/sync_references.py` and
  `plugins/garden/tools/validate_evidence.py`

**agent** — An LLM-driven program that reads, writes, or reviews code through
tools. An agent does not provide independent verification of its own change;
see [D — Defense-in-depth Verification](./principles.md#d--defense-in-depth-verification).

**bounded context** — A declared domain boundary within which a concept has one
canonical meaning and name. Different bounded contexts may use different names
when an explicit translation map connects them. Normative in
[G — Graph-resolvable Discoverability](./principles.md#g--graph-resolvable-discoverability).

**canonical name** — The stable name for a concept inside one bounded context.
It is not required to be the only name used across every context. Normative in
[G — Graph-resolvable Discoverability](./principles.md#g--graph-resolvable-discoverability).

**capability strategy** — The project-specific mapping from a capability to the
code, state, tests, operational artifacts, boundaries, and owner that can affect
it. A vertical slice, a framework-standard layered layout, a pipeline stage, or
a generated map may implement the strategy. Normative in
[A — Adaptive Capability Locality](./principles.md#a--adaptive-capability-locality).

**change-distance** — The modules, boundary crossings, ownership handoffs, and
requisite context involved in completing a capability change. GARDEN treats
these as measurable project properties rather than prescribing a universal
directory shape. Defined in
[A — Adaptive Capability Locality](./principles.md#a--adaptive-capability-locality).

**context file** — A maintained entry point that gives an agent or engineer the
constraints and links needed to start work. GARDEN does not require one fixed
filename or universal line limit. See
[N — Nearby, Maintained Knowledge](./principles.md#n--nearby-maintained-knowledge).

**context rot** — Observed degradation of model performance as input context
grows. GARDEN interprets some of the practical effect as a state-tracking
problem, but that causal interpretation is GARDEN's reading, not a study
finding. ([CLAIM-N002](../evidence/evidence-registry.md#claim-n002)) Motivates
[N — Nearby, Maintained Knowledge](./principles.md#n--nearby-maintained-knowledge).

**context window** — The finite token budget a model can attend to at once. It
is one input to requisite-context measurement, not a fixed module-size rule.
See [A — Adaptive Capability Locality](./principles.md#a--adaptive-capability-locality)
and [N — Nearby, Maintained Knowledge](./principles.md#n--nearby-maintained-knowledge).

**DEFAULT** — A recommendation that a project may override through
configuration, with a documented reason. DEFAULT rules use `SHOULD` or
`SHOULD NOT`; they do not use `MUST`.

**deterministic gate** — An executable check with versioned inputs and a
reproducible pass or fail result, such as a type check, lint rule, test, or CI
job. A pass is evidence, not proof that defects are absent. Normative in
[D — Defense-in-depth Verification](./principles.md#d--defense-in-depth-verification).

**EXPERIMENTAL** — A hypothesis that needs measurement before it can become a
rule. An EXPERIMENTAL item records a method, baseline, and result; it does not
use `MUST`.

**hop distance** — The links or navigation transitions between an edit site and
the knowledge required to edit it safely. Lower distance can be useful, but
GARDEN does not define one universal maximum. See
[N — Nearby, Maintained Knowledge](./principles.md#n--nearby-maintained-knowledge).

**magic value** — A literal that affects domain or operational behavior and is
not obvious at its point of use. Ordinary local literals are not magic values
solely because they are literals. Defined in
[E — Explicit Boundaries and State](./principles.md#e--explicit-boundaries-and-state).

**managed duplication** — A project strategy that delays shared abstraction
until repeated uses show a stable shape, while using review or clone signals to
track the cost. It is one way to apply the Rule of Three DEFAULT in
[A — Adaptive Capability Locality](./principles.md#a--adaptive-capability-locality).

**nearby knowledge** — Governing knowledge stored at, or linked from, the
boundary it documents with an owner and staleness trigger. Defined in
[N — Nearby, Maintained Knowledge](./principles.md#n--nearby-maintained-knowledge).

**premature abstraction** — A shared abstraction introduced before its common
shape or boundary value is supported by concrete uses. The Rule of Three is the
GARDEN DEFAULT for judging this condition, not a universal prohibition. See
[A — Adaptive Capability Locality](./principles.md#a--adaptive-capability-locality).

**progressive disclosure** — Knowledge navigation that starts from a concise
entry point and follows links to detail only when needed. A project measures
whether this reduces requisite context. Defined in
[N — Nearby, Maintained Knowledge](./principles.md#n--nearby-maintained-knowledge).

**replaceability evidence** — The applicable set of interface or schema,
behavioral examples, characterization tests, property tests, compatibility
tests, non-functional requirements, migration and rollback plan, observability
expectations, data ownership, and concurrency or ordering semantics needed to
replace a boundary without guessing. Normative in
[R — Replaceable Components](./principles.md#r--replaceable-components).

**REQUIRED** — A rule whose violation creates a demonstrable risk to
correctness, compatibility, or security. REQUIRED rules may use `MUST` or
`MUST NOT` within their stated scope.

**requisite context** — The minimum set of files, relationships, constraints,
and facts needed to perform a change correctly. It is measured under
[A — Adaptive Capability Locality](./principles.md#a--adaptive-capability-locality)
and managed under
[N — Nearby, Maintained Knowledge](./principles.md#n--nearby-maintained-knowledge).

**residual-risk acceptance** — A manual decision to proceed with an unresolved
risk. It is valid only when it records an owner, supporting evidence, scope, and
expiry. Normative in
[D — Defense-in-depth Verification](./principles.md#d--defense-in-depth-verification).

**self-certification** — An agent acting as the sole authority that its own
output is correct or ready to ship. Prohibited in
[D — Defense-in-depth Verification](./principles.md#d--defense-in-depth-verification).

**spec drift** — Divergence between a declared interface, schema, behavior, or
compatibility expectation and the implementation that claims to satisfy it.
Addressed in
[R — Replaceable Components](./principles.md#r--replaceable-components).

**temporal coupling** — A requirement that operations occur in a particular
order when that state transition or ordering rule is not exposed at the
controlling boundary. Addressed in
[E — Explicit Boundaries and State](./principles.md#e--explicit-boundaries-and-state).

**translation map** — A machine-readable or explicitly documented mapping
between the canonical names or representations used by two bounded contexts.
It preserves local vocabulary while making the boundary recoverable. Normative
in [G — Graph-resolvable Discoverability](./principles.md#g--graph-resolvable-discoverability).

**versioned boundary** — A published API, independently deployed component,
persisted schema, external integration, or other boundary explicitly designated
to carry a compatibility version. Private internal modules are not versioned
boundaries by default. Normative in
[R — Replaceable Components](./principles.md#r--replaceable-components).

**vertical slice** — One possible capability strategy that groups a
capability's entry point, logic, data access, and tests. GARDEN permits it but
does not require it as the physical project layout. See
[A — Adaptive Capability Locality](./principles.md#a--adaptive-capability-locality).

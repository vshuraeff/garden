# Relation to classic principles

GARDEN did not invent six principles from nothing. Each one inherits from an established
line of software design thinking, and each one also weakens or rejects a specific part of
that lineage where the classic formulation assumed a reader GARDEN no longer treats as
primary: a human navigating by accumulated familiarity, in an IDE, with time to ask a
colleague. This document walks the lineage classic principle by classic principle, states
what each contributes, what is kept, what is weakened, and what is rejected, and grounds
each judgment in agent mechanics rather than taste. The condensed "inherits from / rejects"
line for each principle appears in [../reference/principles.md](../reference/principles.md);
this file is the expanded reasoning behind it.

## SOLID, member by member

**Single Responsibility Principle (SRP).** Kept, and central to **A — Atomic Vertical
Slices**. SRP's core claim — a module should have one reason to change — survives intact
under agent-first conditions and arguably matters more: a slice with a single, clear
responsibility is a slice an agent can hold entirely in its context window for one task.
What changes is the axis along which "one responsibility" is drawn. SRP is traditionally
applied per class or per technical layer; GARDEN applies it per vertical capability,
because a capability-shaped slice is what keeps entry point, logic, data access, and
tests within one hop of each other.

**Open/Closed Principle (OCP).** Kept, and central to **R — Regenerable Components**.
"Open for extension, closed for modification" maps directly onto extension through
explicit ports rather than by editing a component's internals. What GARDEN adds is a
consequence OCP does not itself require: because extension happens at ports, the
component behind the port becomes disposable — it can be regenerated from its contract
rather than surgically modified, which is a stronger claim than OCP makes on its own.

**Liskov Substitution Principle (LSP).** Kept, weakened in scope. LSP's substitutability
requirement is exactly what makes a contract in **R** trustworthy: if an implementation
behind a port cannot be substituted without breaking callers, the port is not really a
contract, it is a leaky abstraction with one variant. GARDEN does not ask for LSP across
deep inheritance hierarchies, only at the explicit ports that separate slices — a much
smaller surface, and one an agent can verify against a written contract rather than
infer from a class hierarchy.

**Interface Segregation Principle (ISP).** Kept, and folded into **E — Explicit
Everything**. Narrow, purpose-specific interfaces are a direct ally of explicitness:
a caller that depends on a fat interface is implicitly coupled to methods it never
calls, which is exactly the kind of hidden coupling E targets. ISP's classic
justification — avoiding forced recompilation or reimplementation of unused methods —
still applies, but the agent-first justification is stronger: a narrow interface is a
narrow, cheap thing to read and reason about in one pass.

**Dependency Inversion Principle (DIP).** Kept, weakened in mechanism. DIP's core idea —
depend on abstractions, not concretions — is exactly R's "dependencies point at
contracts, not concrete implementations." What is weakened is the standard
*implementation* of DIP: reflection-heavy dependency-injection frameworks that resolve
concrete types at runtime through container configuration. That machinery inverts
dependencies for the compiler while inverting discoverability for the reader — a
container-resolved dependency cannot be traced by static text search, which is a direct
violation of **G — Grep-first Discoverability**. GARDEN keeps DIP's goal and asks for it
to be achieved through explicit, statically traceable wiring wherever possible.

## KISS, DRY, YAGNI

**Keep It Simple (KISS).** Kept without qualification, and one of A's direct ancestors.
Simplicity was always partly about the next reader's cognitive load; under agent-first
conditions that cognitive load has a harder ceiling — the context window — which makes
KISS less a stylistic preference and more a binary constraint: a slice either fits an
agent's one-context task or it does not.

**Don't Repeat Yourself (DRY).** Weakened, deliberately, to **managed duplication**.
Classic DRY treats any duplication as a defect to eliminate on sight. The GitClear
evidence complicates that stance without overturning it: duplicated code has grown
roughly eightfold since AI assistants became mainstream, which sounds like an argument
for stricter DRY, but the mechanism behind that growth is search-miss-driven
reimplementation, not a shortage of enthusiasm for abstraction. Applying strict DRY
reactively in an agent-first codebase tends to produce **premature abstraction** —
collapsing two or three superficially similar blocks into a shared function before
enough concrete usages exist to know what actually varies, which then forces every
future edit to reason about all the call sites the abstraction now serves, inflating
requisite context rather than shrinking it. GARDEN's answer is not "duplicate freely"
but "tolerate duplication until a clone-detection signal in CI justifies extracting an
abstraction, and require at least three concrete usages first" — deduplication by
detection, not by prediction.

**You Aren't Gonna Need It (YAGNI).** Kept, and extended explicitly to documentation
under **N — Navigable Knowledge**. Classic YAGNI targets speculative code; GARDEN applies
the same discipline to speculative and exhaustive documentation. Encyclopedic
autogenerated docs are a YAGNI violation with agent-specific costs: the evidence on
context files (ETH Zurich, 2025) shows autogenerated, unmaintained instruction material
actively reducing task success (roughly 3%), where curated hand-written material helps
(roughly 4 percentage points). Docs that restate what the code already shows are waste under YAGNI
whether or not an agent will ever read them, but they carry an added cost when an agent
does read them — competing for a share of a bounded context window.

## GRASP highlights

**Information Expert and Low Coupling / High Cohesion.** Kept, and the direct ancestor of
A's "organize by capability." Assigning responsibility to the module that has the
information needed to fulfill it, and keeping coupling low between modules, is what
makes a vertical slice viable as a unit an agent can edit without chasing dependencies
across the tree.

**Controller and Indirection.** Weakened. GRASP's Indirection pattern — inserting an
intermediate object to decouple two others — is a reasonable tool used sparingly, but
GARDEN treats indirection as a cost to be spent deliberately, not a default good. Every
layer of indirection a GRASP-literate design might introduce for flexibility's sake adds
to the **indirection tax**: extra search-and-read cost an agent pays before it can see
what a call actually does, and raises hallucination risk when the agent
guesses at what an unread layer contains rather than reading it.

**Protected Variations.** Kept, and effectively restated by R's contracts-at-ports
requirement: protect the system from variation by wrapping the point of variation in a
stable interface. GARDEN's addition is that the interface must be precise enough for
regeneration, not merely stable enough for compilation.

## Design by contract

Kept, and the direct ancestor of both **R — Regenerable Components** and **D —
Deterministic Verification**. Design by contract's preconditions, postconditions, and
invariants are exactly the substance a component's spec needs to make regeneration
possible without behavioral drift, and exactly the kind of statement D requires to exist
in executable form rather than prose. GARDEN's departure is narrow but important: design
by contract typically assumes the contract is checked at runtime, by assertions; GARDEN
requires the same rigor pushed as far left as possible — into types and CI gates —
because a runtime assertion an agent can route around under time pressure is weaker
protection than a gate the agent cannot merge past.

## Parnas information hiding

Kept, and the direct ancestor of R. Parnas's original insight — modules should hide
design decisions likely to change behind a stable interface — is precisely what makes a
component regenerable: the things likely to change are exactly the things GARDEN wants
inside the disposable implementation, not baked into the contract other slices depend on.
What GARDEN rejects is not information hiding itself but the corollary mindset it can
encourage: treating the hidden implementation as precious, carefully preserved code
rather than as expendable material that can be rewritten wholesale once its contract is
understood. Under R, the contract is the durable artifact Parnas asked teams to design
around; the code behind it is disposable in a way Parnas-era teams, writing by hand at
much higher cost per line, did not have the luxury of treating it as.

## Notable rejections, stated plainly

Three classic practices are not merely weakened under GARDEN; they are actively rejected
for agent-first work, and it is worth being explicit about why.

**Strict DRY as a reflex.** As covered above, DRY applied reflexively — collapsing
similar-looking code the moment it appears twice — produces premature abstractions that
cost an agent more in requisite context than the duplication they remove. GARDEN rejects
DRY as an on-sight reflex while keeping it as an eventual, detection-driven practice.

**Deep GoF inheritance hierarchies and Singleton.** Both are rejected as default tools,
not banned outright. A deep inheritance chain requires an agent to trace behavior through
several overridden layers before it can be sure what a call actually does — a textbook
indirection tax, and one that static text search handles poorly, since the concrete
method that actually executes may be several classes away from the call site. Singleton
compounds the problem by adding hidden global state that no call site's signature
reveals, which is precisely the ambient, undeclared dependency **E — Explicit Everything**
prohibits.

**Clean Architecture's global layering.** Organizing an entire codebase into concentric
layers (entities, use cases, interface adapters, frameworks) asks the reader to
understand the whole system's layering scheme before any single edit can be judged
correct — a form of whole-program understanding a human architect can build up over
years on a project, but that an agent working from a bounded context window cannot
reconstruct on demand for every task. GARDEN rejects global layering as an organizing
principle in favor of **A**'s capability-first slicing, while keeping Clean
Architecture's underlying goal — dependencies that point inward toward stable
abstractions — as exactly what **R**'s ports-not-implementations rule already asks for,
scoped to a slice's boundary rather than the whole system.

## Reading this table alongside the rest of the docs

None of these judgments are arbitrary preferences; each traces back to a specific
mechanical constraint covered in
[why-agent-first-principles.md](why-agent-first-principles.md) — the context window,
search-based navigation, fragment reading, and context rot — and each principle's full
rule set, including the anti-patterns each rejection targets by name, is stated
canonically in [../reference/principles.md](../reference/principles.md).

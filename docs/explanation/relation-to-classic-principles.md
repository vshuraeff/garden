---
owner: vshuraeff
last_reviewed: 2026-07-16
review_on:
  - rule-change
  - evidence-change
---

# Relation to classic principles

GARDEN builds its six principles from established lines of software-design
thinking, while narrowing their application to stated boundaries, evidence, and
project-specific constraints. The correspondences below identify what carries
forward and where the current rules change the classic formulation. The
condensed "inherits from / rejects" line for each principle appears in
[../reference/principles.md](../reference/principles.md); this file records the
reasoning behind it.

## SOLID, member by member

**Single Responsibility Principle (SRP).** Kept, and closely aligned with
**A — Adaptive Capability Locality**. A module should have a clear reason to
change, but that does not prescribe a vertical-slice tree. `A-LOC-001` requires
a stated capability location and ownership strategy that identifies its code,
state, tests, and operational artifacts; `A-LOC-002` requires the affected
contracts and checks when a change crosses a boundary. Framework-standard
layouts, shared kernels, and other physical structures are valid when that
strategy makes the change surface and ownership clear. `A-LOC-003` then makes
low change-distance — fewer unrelated modules, crossings, handoffs, and less
requisite context — the DEFAULT objective.

**Open/Closed Principle (OCP).** Kept, and aligned with **R — Replaceable
Components**. "Open for extension, closed for modification" maps to extension
through declared interfaces, schemas, adapters, or ports when they reduce
consumer coupling (`R-REPL-007`). The boundary must also record the applicable
replaceability evidence: interface or schema, behavioral examples,
characterization or compatibility tests, migration and rollback expectations,
and other relevant constraints (`R-REPL-001`). Extension therefore preserves
the boundary's recorded behavior and compatibility expectations; it does not
imply that an implementation can be recreated from a single contract artifact.

**Liskov Substitution Principle (LSP).** Kept, with scope at a component
boundary. A replacement is credible only when its observable behavior,
compatibility, ordering, and other applicable constraints are covered by the
evidence required by `R-REPL-001`. GARDEN does not require LSP analysis across
every deep inheritance hierarchy. It applies the concern where consumers depend
on a declared boundary and compatibility evidence can demonstrate whether a
substitution preserves the required behavior.

**Interface Segregation Principle (ISP).** Kept, and related to **E — Explicit
Boundaries and State**. Narrow purpose-specific interfaces make a boundary's
inputs, outputs, validation, compatibility expectations, and ownership easier
to state as required by `E-EXPL-001`. The same principle does not demand
ceremony in every local function: `E-EXPL-004` calls for proportionate local
explicitness. An interface should expose the behavior its boundary needs,
without making callers carry unrelated dependencies.

**Dependency Inversion Principle (DIP).** Kept, with a choice of mechanisms.
Depending on declared interfaces, schemas, adapters, or ports can reduce
consumer coupling under **R — Replaceable Components** (`R-REPL-007`). A
dependency-injection container is compatible with **G — Graph-resolvable
Discoverability** when its registry, manifest, schema, or generated dependency
graph makes the relationship recoverable (`G-DISC-001`). `E-EXPL-004` also
allows generated wiring that already proves the relationship. Ad hoc reflection
with no machine-readable registry or generated map is instead a discoverability
gap, because its targets cannot be recovered before execution. Direct references
remain the DEFAULT when dynamic dispatch provides no measured value
(`G-DISC-005`).

## KISS, DRY, YAGNI

**Keep It Simple (KISS).** Kept, and an ancestor of **A — Adaptive Capability
Locality**. A finite context window makes the next reader's cognitive load a
practical constraint, but not a binary fit test. `A-LOC-003` asks a typical
change to minimize requisite context along with unrelated modules and boundary
crossings. `N-KNOW-005` complements that goal by recommending progressive
disclosure so documentation loads the requisite context for the change rather
than an undifferentiated project history.

**Don't Repeat Yourself (DRY).** Weakened, deliberately, to **managed
duplication**. Classic DRY treats any duplication as a defect to eliminate on
sight. GitClear's observational report, covering 211 million changed lines
from 2020-2024, found blocks of duplicated code growing roughly eightfold. That
trend does not establish its cause, but it complicates the case for strict DRY
without overturning it. Applying strict DRY reactively in an agent-first
codebase tends to produce **premature abstraction** — collapsing two or three
superficially similar blocks into a shared function before enough concrete uses
show what actually varies, which then makes a future edit reason about all of
the call sites the abstraction serves and inflates requisite context. GARDEN's
DEFAULT is to defer a shared abstraction until at least three concrete uses show
a stable common shape; a known boundary, security control, or platform
constraint may justify a documented override (`A-LOC-005`). Clone-detection
signals can inform that decision, but do not make the rule an absolute mandate.
([CLAIM-N004](../evidence/evidence-registry.md#claim-n004))

**You Aren't Gonna Need It (YAGNI).** Kept, and extended explicitly to
documentation under **N — Nearby, Maintained Knowledge**. Classic YAGNI targets
speculative code; GARDEN applies the same discipline to speculative and
exhaustive documentation. `N-KNOW-007` says documentation should record
decisions, constraints, navigation, and operations rather than restate facts
already clear from code or generated artifacts. An informal single-author
practitioner report suggests that unmaintained autogenerated instruction
material can hurt while curated hand-written material can help. Repeated code
facts compete with the requisite context when a reader needs the decisions the
code cannot express. ([CLAIM-N001](../evidence/evidence-registry.md#claim-n001))

## GRASP highlights

**Information Expert and Low Coupling / High Cohesion.** Kept, and an ancestor
of **A — Adaptive Capability Locality**. Assigning responsibility where the
needed information lives and keeping coupling low supports a capability strategy
that identifies its code, state, tests, operational artifacts, and owner
(`A-LOC-001`). A vertical slice can be one such strategy, but framework-standard
or shared structures are also valid when they preserve low change-distance and
make the capability's verification surface recoverable (`A-LOC-002`,
`A-LOC-003`).

**Controller and Indirection.** Weakened. GRASP's Indirection pattern —
inserting an intermediate object to decouple two others — is useful when its
boundary value outweighs its navigation cost. `G-DISC-005` recommends the
lowest-cost relationship mechanism the stack can inspect reliably, while
`G-DISC-001` permits dynamic dispatch when a manifest, schema, registry, or
generated map exposes the graph. Indirection is therefore a deliberate choice,
not a default good or a requirement for flexibility.

**Protected Variations.** Kept, and aligned with **R — Replaceable
Components**. A declared interface can protect consumers from variation, but it
is sufficient only when the boundary's applicable replaceability evidence
records what a change must preserve (`R-REPL-001`). `R-REPL-007` recommends
interfaces, schemas, adapters, or ports for extensions and replacements when
they reduce consumer coupling; it does not require an abstraction with no
replacement or test value.

## Design by contract

Kept, and an ancestor of both **R — Replaceable Components** and **D —
Defense-in-depth Verification**. Preconditions, postconditions, and invariants
can form part of a boundary's interface, behavioral examples, or compatibility
evidence under `R-REPL-001`; a greenfield public boundary defines its observable
interface, behavior, errors, and compatibility expectations before
implementation (`R-REPL-006`). `D-VER-001` requires a change to record the
relevant verification levels, and `D-VER-002` requires applicable executable
checks to be reproducible. Runtime assertions remain one possible verification
level, but they do not replace the other applicable checks or the compatibility
evidence needed to judge a replacement.

## Parnas information hiding

Kept, and an ancestor of **R — Replaceable Components**. Parnas's insight —
modules should hide design decisions likely to change behind a stable interface
— remains the boundary design goal. The interface and the recorded
replaceability evidence in `R-REPL-001` let a team judge whether a hidden
implementation can change without breaking observable behavior, consumers,
data, ordering, or operations. That judgment is boundary-specific; GARDEN does
not treat implementation code as disposable by default.

## Notable constraints and rejections

Some classic practices remain rejected as reflexes; global layering is instead
constrained by the same capability and verification rules as other structures.

**Strict DRY as a reflex.** As covered above, DRY applied reflexively —
collapsing similar-looking code the moment it appears twice — produces premature
abstractions that can cost more requisite context than the duplication removes.
GARDEN rejects DRY as an on-sight reflex while keeping it as an eventual,
detection-informed practice subject to the DEFAULT in `A-LOC-005`.

**Deep GoF inheritance hierarchies and Singleton.** Both are rejected as
default tools, not banned outright. A deep inheritance chain can require a
reader to trace behavior through several overridden layers before identifying
the implementation that runs. A Singleton can add hidden global state that a
caller's signature does not reveal. At a boundary controlling domain behavior,
`E-EXPL-002` requires side effects, external dependencies, and state
transitions to be explicit and forbids hidden ambient state from determining
behavior across that boundary; it does not require every local state detail to
be surfaced.

**Clean Architecture's global layering.** Layering is compatible with GARDEN
when the project states a capability strategy that traces a change to its code,
state, tests, operational artifacts, and owner (`A-LOC-001`), and identifies
the affected contracts and relevant checks at boundary crossings
(`A-LOC-002`). The allowed exceptions for **A — Adaptive Capability Locality**
explicitly include shared kernels, staged or tool-defined layouts, and
framework-standard directories when they retain that traceability and
verification surface. Clean Architecture's goal of dependencies toward stable
abstractions can likewise support **R — Replaceable Components** where declared
interfaces, schemas, adapters, or ports reduce consumer coupling
(`R-REPL-007`); no global layout is required.

## Reading this table alongside the rest of the docs

Each correspondence is bounded by the current rule scope and normative level.
The related mechanical constraints appear in
[why-agent-first-principles.md](why-agent-first-principles.md), and the
canonical rules, exceptions, and evidence references are in
[../reference/principles.md](../reference/principles.md).

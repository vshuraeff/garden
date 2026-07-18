---
owner: vshuraeff
last_reviewed: 2026-07-16
review_on:
  - rule-change
  - evidence-change
---
<!-- Generated from docs/reference/principles.md. Do not edit directly. Run sync_references.py --write to update. -->

# GARDEN principles

GARDEN defines six language-agnostic design principles for software written,
reviewed, and operated by people and agents. The principles constrain risks at
their stated scopes; they do not prescribe one repository layout, framework,
contract file, or review tool.

- Document owner: GARDEN plugin maintainers
- Last reviewed: 2026-07-13
- Review trigger: a principle, normative level, rule ID, or cited evidence claim
  changes
- Executable checks: `plugins/garden/tools/sync_references.py`,
  `plugins/garden/tools/validate_evidence.py`, and
  `plugins/garden/tools/validate_package.py`

## Normative levels and rule IDs

GARDEN uses exactly three normative levels:

- **REQUIRED** — violating the rule creates a demonstrable risk to
  correctness, compatibility, or security.
- **DEFAULT** — a recommendation that a project may override through
  configuration, with a documented reason.
- **EXPERIMENTAL** — a hypothesis that needs measurement before it can become
  a rule.

The RFC 2119 keywords `MUST` and `MUST NOT` appear only in REQUIRED rules and
apply only within the scope stated by the rule. DEFAULT rules use `SHOULD` or
`SHOULD NOT`. EXPERIMENTAL heuristics define measurements or trials and do not
use `MUST`.

Every rule has a stable machine-readable ID. A future rename retains the ID or
adds an explicit migration alias; it does not silently assign a new ID to the
same rule. Project overrides record the rule ID, owner, reason, supporting
evidence, and review trigger. REQUIRED rules allow an exception only when the
rule's scope or its Allowed exceptions section says so.

## Runtime rule-ID correspondence

The plugin runtime still emits earlier rule-ID strings. Runtime code and
tests retain those strings; this table maps them to the nearest normative rule.

| New normative rule ID | Existing runtime rule ID | Correspondence |
| --- | --- | --- |
| `N-KNOW-005` | `N-context-budget` | Bounded requisite context and progressive disclosure |
| `R-REPL-002` | `R-contract-version` | Versioning at designated versioned boundaries |
| `R-REPL-001` | `R-component-contract` | Evidence required to replace a component safely |
| `R-REPL-001` | `R-boundary-contract-missing` | Missing declared boundary contract artifact |
| `R-REPL-001` | `R-boundary-evidence-review` | Required evidence category surfaced as a manual `unknown` finding |
| `A-LOC-004` | `A-colocated-tests` | Test placement or mapping under the project's capability strategy |

The machine-readable source of this alias mapping is the canonical registry at
`plugins/garden/rules/garden-rules.toml` (`runtime_aliases` per rule); this table is a
human-readable view of the same data. [rule-registry.md](./rule-registry.md) records
its derivations and drift checks.

## G — Graph-resolvable Discoverability

### Goal

An engineer or agent can recover relationships through a stated mechanism.
Valid mechanisms include grep, an AST, an LSP, a symbol index, a route map, a
plugin registry, a schema registry, or generated wiring. Dynamic dispatch is
acceptable when a manifest, schema, registry, or generated map exposes the
graph.

### Required rules

- **G-DISC-001 [REQUIRED] Recoverable relationships.** Production relationships
  that affect domain behavior, data flow, authorization, or side effects `MUST`
  be recoverable through at least one stated mechanism. A dynamic relationship
  `MUST` have a machine-readable manifest, schema, registry, or generated map.
- **G-DISC-002 [REQUIRED] Bounded canonical names.** A domain concept `MUST`
  have a canonical name within its bounded context. A context boundary that
  uses a different name `MUST` provide an explicit translation map rather than
  forcing one global name or relying on an undocumented synonym.
- **G-DISC-003 [REQUIRED] Stable error identity.** An error handled across a
  public, process, service, or operational boundary `MUST` expose a stable,
  machine-readable code and structured fields. Human-readable error text may
  change without becoming part of the compatibility contract.

### Defaults

- **G-DISC-004 [DEFAULT] Concept-aligned locations.** Files, symbols, routes,
  tests, and documentation `SHOULD` use names that connect them to the bounded
  context's canonical concept or its declared registry entry.
- **G-DISC-005 [DEFAULT] Lowest-cost graph mechanism.** A project `SHOULD` use
  the simplest relationship mechanism its stack can inspect reliably. Direct
  references are preferred when dynamic dispatch adds no measured value; a
  framework registry is preferred when it already provides the authoritative
  graph.

### Experimental heuristics

- **G-DISC-006 [EXPERIMENTAL] Resolution effort.** Measure the searches, tool
  calls, or elapsed time required to move from an entry point to its handler,
  schema, side effects, and tests. Any threshold is project-specific and
  unmeasured until the project records a baseline.

### Allowed exceptions

Generated wiring may be the authoritative relationship map when its source
schema and regeneration command are discoverable. Framework routing and plugin
dispatch are allowed when their registry is machine-readable. No exception
permits production domain dispatch whose targets cannot be recovered.

A bounded context may keep its established vocabulary. The boundary owns the
translation map; internal code is not required to adopt a repository-wide
synonym.

### Evidence

The evidence registry does not contain a study that isolates graph-resolvable
discovery as a cause of fewer defects. `G-DISC-*` rules are risk controls whose
satisfaction is demonstrated by project artifacts and a successful graph
traversal. The registry's observed increase in duplicated code is relevant
context for finding existing behavior, but it does not establish that any
discoverability structure prevents duplication.
([CLAIM-N004](./evidence-registry.md#claim-n004))

### Good example

```yaml
# payments/routes.yaml — authoritative input to generated routing
refund.requested:
  handler: payments.refunds.handle_request
  schema: schemas/refund-request.json
```

The dispatch may be dynamic because the route map exposes the handler and
schema through stable identifiers.

### Counterexample

```python
def dispatch(event):
    module = import_module(f"handlers.{event['kind']}_handler")
    return getattr(module, "run")(event)
```

No registry or generated map enumerates the possible targets, so the runtime
relationship cannot be recovered before execution.

### Tooling support

- `G-DISC-001`: planned — adapter-specific checks can compare dispatch code
  with a declared route, plugin, or schema registry.
- `G-DISC-002`: manual-with-owner — the bounded-context owner reviews canonical
  names and translation maps; a future configuration-driven naming check is
  planned.
- `G-DISC-003`: planned — boundary schema and structured-log checks can require
  an error code and fields without freezing message text.

## A — Adaptive Capability Locality

### Goal

A typical capability change has low change-distance and a clear owner. The
project chooses a physical structure that fits its language, framework,
deployment model, and target. Locality is judged by modules touched, boundary
crossings, requisite context, ownership clarity, and coupling, not by whether
the tree matches a prescribed vertical-slice layout.

### Required rules

- **A-LOC-001 [REQUIRED] Stated capability strategy.** A production capability
  `MUST` have a stated location and ownership strategy sufficient to identify
  the code, state, tests, and operational artifacts that can affect it.
- **A-LOC-002 [REQUIRED] Verified boundary crossings.** A change that crosses a
  capability, trust, persistence, or independently deployed boundary `MUST`
  identify the affected contracts and run the relevant compatibility or
  integration checks.

### Defaults

- **A-LOC-003 [DEFAULT] Low change-distance.** A typical capability change
  `SHOULD` minimize unrelated modules touched, boundary crossings, requisite
  context, and ownership handoffs while preserving the stack's normal
  structure.
- **A-LOC-004 [DEFAULT] Discoverable tests.** Tests `SHOULD` be colocated with
  the capability they verify when the stack supports colocation. Otherwise the
  capability strategy `SHOULD` provide a stable mapping from production code to
  its tests.
- **A-LOC-005 [DEFAULT] Rule of Three.** An abstraction `SHOULD NOT` be shared
  until at least three concrete uses demonstrate a stable common shape. A
  project may override this default for a known boundary, security control, or
  platform constraint with a documented reason.

### Experimental heuristics

- **A-LOC-006 [EXPERIMENTAL] Change-locality profile.** Measure modules touched,
  boundary crossings, ownership handoffs, and requisite context for a sample of
  completed capability changes. Adopt thresholds only after the project has a
  baseline and has checked that the metric does not reward hidden coupling.

### Allowed exceptions

Shared kernels, compiler passes, data pipelines, SDKs, infrastructure
repositories, embedded targets, and generated code may require horizontal,
staged, or tool-defined layouts. They still satisfy `A-LOC-001` and
`A-LOC-002`: the capability strategy states how a change is traced and which
boundaries require verification.

Framework-standard directories are allowed when they reduce requisite context
for maintainers of that stack. A vertical slice is one valid capability
strategy, not a required root layout.

### Evidence

GitClear observed changes in churn and clone-detection metrics across its
corpus, but did not establish that a particular directory structure caused
them. That limitation supports measuring change locality in the target project
instead of declaring a universal tree shape.
([CLAIM-N004](./evidence-registry.md#claim-n004))

### Good example

```text
src/                 # framework-standard layout
  controllers/
  services/
  models/
capabilities.yaml    # maps "refund" to its code, tests, owner, and runbook
tests/
runbooks/
```

The layout remains conventional for the stack while `capabilities.yaml` makes
the full change surface and owner recoverable.

### Counterexample

```text
src/shared/refund.py
src/legacy/refund_helpers.py
jobs/reconcile.py
ops/manual-refunds.md
```

No capability map or owner identifies which files form the refund behavior, so
a change crosses implicit boundaries without a known verification set.

### Tooling support

- `A-LOC-001`: manual-with-owner — the capability owner reviews the declared
  location, state, tests, and operational artifacts; configuration-driven maps
  are planned.
- `A-LOC-002`: planned — repository adapters can compare changed paths with
  boundary maps and required compatibility gates.
- `A-LOC-004`: planned — the existing runtime ID `A-colocated-tests` remains a
  compatibility signal; a future check must also accept an explicit test map.

## R — Replaceable Components

### Goal

A component can be changed or replaced without guessing which observable
behavior, data, operational property, or ordering constraint must survive.
Replaceability is demonstrated by evidence appropriate to the boundary, not by
one mandated contract format.

### Required rules

- **R-REPL-001 [REQUIRED] Replaceability evidence.** A component boundary whose
  replacement can affect correctness, compatibility, or security `MUST` record
  the applicable evidence: public interface or schema, behavioral examples,
  characterization tests, property tests where applicable, compatibility
  tests, non-functional requirements, migration and rollback plan,
  observability expectations, data ownership, and concurrency or ordering
  semantics. An omitted category `MUST` be marked not applicable with a reason.
- **R-REPL-002 [REQUIRED] Scoped versioning.** Published APIs, independently
  deployed components, persisted schemas, external integrations, and
  boundaries explicitly designated as versioned `MUST` declare their
  compatibility policy and use SemVer where SemVer describes the artifact. A
  private internal module `MUST NOT` be given an artificial `Version:` line;
  Git history tracks it unless the boundary is explicitly designated as
  versioned.
- **R-REPL-003 [REQUIRED] Characterize legacy behavior.** Legacy behavior
  `MUST` be captured by characterization or compatibility tests before a
  replacement or behavior-preserving rewrite begins.
- **R-REPL-004 [REQUIRED] Reproduce bugs first.** A bug fix `MUST` begin with a
  failing executable test or reproducer that passes after the fix.
- **R-REPL-005 [REQUIRED] Protect undocumented behavior.** Observable but
  undocumented behavior `MUST NOT` be removed or rewritten without
  compatibility evidence that identifies affected consumers and supports the
  change.
- **R-REPL-006 [REQUIRED] Contract-first public boundaries.** A greenfield
  public boundary `MUST` define its observable interface, behavior, errors, and
  compatibility expectations before implementation. Contract-first design does
  not apply to a legacy rewrite until `R-REPL-003` is satisfied.

### Defaults

- **R-REPL-007 [DEFAULT] Replace through boundaries.** Extensions and
  replacements `SHOULD` use declared interfaces, schemas, adapters, or ports
  when doing so reduces consumer coupling. A private module `SHOULD` remain a
  direct implementation when an extra abstraction has no replacement or test
  value.

### Experimental heuristics

- **R-REPL-008 [EXPERIMENTAL] Replacement drill.** On a non-production path,
  measure whether a second implementation or schema version can pass the
  recorded evidence set. Treat time-to-replace as a local diagnostic, not a
  universal threshold.

### Allowed exceptions

Evidence categories may be not applicable only with a boundary-specific
reason. Generated components may point to their source schema, generator, and
generation checks instead of duplicating a handwritten interface. Private
internal modules are outside SemVer scope unless the project designates them
as versioned.

An emergency mitigation follows `D-VER-004` when complete evidence cannot be
collected before deployment. The recorded acceptance does not erase the
missing test or compatibility work, and it expires.

### Evidence

The evidence registry does not establish that a specific contract file or
version marker makes components replaceable. Its observed changes in duplicated
and refactored code are context for preserving behavior before replacement, not
proof of the `R-REPL-*` model.
([CLAIM-N004](./evidence-registry.md#claim-n004))

### Good example

```text
refunds/
  api.yaml
  compatibility/
    legacy-cases.json
  tests/
    characterization_test.py
  migration.md
  operations.md
```

The boundary records behavior, compatibility, migration, rollback, ownership,
and operational expectations. Its published API is versioned; its private
helpers are tracked only through Git.

### Counterexample

```text
refunds/
  CONTRACT.md   # Version: 1.0.0, but no behavioral or compatibility evidence
  refund.py
```

A version line alone does not identify consumers, persisted data, ordering,
rollback, or the behavior a replacement must preserve.

### Tooling support

- `R-REPL-001`: manual-with-owner — the boundary owner evaluates completeness;
  schema, test, and migration-file checks are planned.
- `R-REPL-002`: planned — artifact-specific checks can require versioning only
  for boundaries configured as published, deployed, persisted, external, or
  versioned.
- `R-REPL-003`: manual-with-owner — characterization coverage is reviewed
  against observed legacy behavior; test execution is automated once tests
  exist.
- `R-REPL-004`: manual-with-owner — review links the failing reproducer to the
  fix; the reproducer then runs in the project's automated test gate.
- `R-REPL-005`: manual-with-owner — consumer and compatibility evidence require
  boundary-owner review.
- `R-REPL-006`: manual-with-owner — public-boundary review precedes
  implementation; schema lint and contract tests are automated when provided
  by the project.

## D — Defense-in-depth Verification

### Goal

A change is supported by independent, reproducible evidence selected for its
risk. An agent's assessment is never sufficient by itself, and an LLM review
never substitutes for an executable check. A passing deterministic gate is
evidence, not proof that defects are absent.

### Required rules

- **D-VER-001 [REQUIRED] Explicit verification levels.** Each change `MUST`
  identify which of these levels are relevant and record the result or the
  reason a level is not applicable: static validation; unit or property tests;
  integration or contract tests; security or fuzz testing; runtime assertions
  and telemetry; canary or staged rollout; independent review; and explicit
  residual-risk acceptance.
- **D-VER-002 [REQUIRED] Reproducible executable checks.** Applicable type,
  lint, test, and CI checks `MUST` be reproducible from versioned configuration.
  An LLM review `MUST NOT` replace an applicable executable check.
- **D-VER-003 [REQUIRED] Visible flakiness.** A flaky check `MUST NOT` be hidden
  behind automatic retries or reported as a clean pass. Its instability and
  owner `MUST` remain visible until the cause is fixed or the check is removed
  through an explicit risk decision.
- **D-VER-004 [REQUIRED] Bounded risk acceptance.** A human decision to accept
  residual risk `MUST` record an owner, supporting evidence, scope, and expiry.
- **D-VER-005 [REQUIRED] No self-certification.** An agent `MUST NOT` be the
  sole authority that its own change is correct or ready to ship. Executable
  gates and an authorized human or independent decision process own that
  decision.

### Defaults

- **D-VER-006 [DEFAULT] Earliest useful gate.** A violation `SHOULD` surface at
  the earliest verification level that can detect it without weakening a
  higher-level check.
- **D-VER-007 [DEFAULT] Independent review lenses.** Review `SHOULD` separate
  correctness, security, compatibility, concurrency, input hardening, and
  quality concerns as relevant. LLM findings `SHOULD` be reported as hypotheses
  that require confirmation.

### Experimental heuristics

- **D-VER-008 [EXPERIMENTAL] Gate-value measurement.** Measure defect detection,
  escaped defects, execution time, and flake rate per gate before changing the
  verification mix. Do not treat repeated agreement from one model as an
  independent signal.

### Allowed exceptions

A verification level may be not applicable when the change cannot exercise
that risk, and the verification record states why. A missing applicable check
is residual risk, not a pass. Time pressure may lead to the bounded acceptance
defined by `D-VER-004`; it does not authorize a hidden retry or agent
self-certification.

### Evidence

One practitioner report found instruction-only rules less reliable than rules
backed by runtime enforcement, but the report is informal and from one author.
([CLAIM-N001](./evidence-registry.md#claim-n001)) One single-author
preprint reported better defect detection from its multi-agent system than from
one agent while also reporting substantial false positives. It does not prove
that multi-agent review generalizes or replaces executable checks.
([CLAIM-N003](./evidence-registry.md#claim-n003))

### Good example

```text
Verification record
- static: type check and lint passed from committed configuration
- unit/property: refund invariants passed
- integration/contract: payment sandbox contract passed
- security/fuzz: request parser fuzz corpus passed
- runtime: refund error-code dashboard linked
- rollout: staged to one region with rollback condition
- independent review: compatibility owner reviewed
- residual risk: none accepted
```

### Counterexample

```text
Tests were flaky, so the job retried until green. The implementing agent
reviewed the diff and declared it safe.
```

Retries conceal the unstable signal, and the agent's conclusion supplies no
independent authority.

### Tooling support

- `D-VER-001`: manual-with-owner — the change owner selects applicable levels;
  each selected executable gate is automated by the project where available.
- `D-VER-002`: automated — project type, lint, test, and CI entry points provide
  the evidence. In this repository, `validate_package.py` validates the plugin
  package and `validate_evidence.py` validates documentation evidence use.
- `D-VER-003`: planned — CI should expose first-attempt status and reject hidden
  retry-to-green behavior.
- `D-VER-004`: manual-with-owner — acceptance records require owner and expiry;
  a future configuration-driven expiry check is planned.
- `D-VER-005`: manual-with-owner — branch protection or release authorization
  should separate implementation from the final decision; automation is
  project-specific.

## E — Explicit Boundaries and State

### Goal

Information whose omission can change correctness, compatibility, security, or
operations is visible at the boundary where it matters. Local implementation
detail remains proportionate: explicitness does not require ceremony for every
literal, local type, dependency, or framework default.

### Required rules

- **E-EXPL-001 [REQUIRED] Boundary contracts.** Public APIs, trust boundaries,
  and persistence formats `MUST` state their input and output shapes,
  validation, compatibility expectations, and ownership.
- **E-EXPL-002 [REQUIRED] Behavioral state.** Side effects, external
  dependencies, and state transitions `MUST` be explicit at the boundary that
  controls them. Hidden ambient state `MUST NOT` determine domain behavior
  across that boundary.
- **E-EXPL-003 [REQUIRED] Operational decisions.** Retries, timeouts,
  authorization decisions, and cross-boundary failures `MUST` expose their
  policy and owner. Errors in this scope `MUST` carry the stable code and
  structured fields required by `G-DISC-003`.

### Defaults

- **E-EXPL-004 [DEFAULT] Proportionate local explicitness.** Local code `SHOULD`
  use the least ceremony that leaves behavior clear. It `SHOULD NOT` introduce
  manual dependency injection for a static dependency, replace generated
  wiring that already proves correctness, or abandon a reasonable framework
  default without a boundary-specific reason.
- **E-EXPL-005 [DEFAULT] Narrow magic-value rule.** A magic value is a literal
  that affects domain or operational behavior and is not obvious at its point
  of use. Such a value `SHOULD` be named or explained at that point. Ordinary
  local literals do not require constants merely because they are literals.

### Experimental heuristics

- **E-EXPL-006 [EXPERIMENTAL] Implicit-dependency audit.** Sample incidents and
  change failures for hidden state, undocumented defaults, retry behavior, or
  authorization assumptions. Use the result to decide which boundary checks to
  automate.

### Allowed exceptions

A small local function need not fully type every intermediate value or replace
every literal with a named constant. Static dependencies need not use manual
dependency injection. Generated wiring may remain implicit in source when its
generated graph proves the relationship. Framework defaults are allowed when
the boundary does not need to override them and the effective behavior is
recoverable.

These exceptions do not apply at public APIs, trust boundaries, side effects,
state transitions, persistence formats, retries or timeouts, authorization
decisions, cross-boundary errors, or ownership boundaries.

### Evidence

The evidence registry contains no study that establishes a universal amount of
explicitness. `E-EXPL-*` rules therefore limit REQUIRED scope to omissions with
a demonstrable boundary risk and leave local style as DEFAULT or project
judgment.

### Good example

```python
retry_policy = RetryPolicy(max_attempts=3, timeout_seconds=2, owner="payments")
decision = authorizer.check(actor, "refund:create", refund_id)
gateway.create_refund(request, retry_policy=retry_policy, decision=decision)
```

The side effect, authorization decision, retry policy, timeout, and owner are
visible where the boundary is invoked.

### Counterexample

```python
configure_from_environment()
gateway.create_refund(request)  # ambient auth, retries, and timeout
```

The call site and boundary contract do not reveal which authorization decision
or operational policy controls the side effect.

### Tooling support

- `E-EXPL-001`: planned — schema, ownership, and compatibility checks are
  boundary- and stack-specific.
- `E-EXPL-002`: manual-with-owner — reviewers trace side effects, dependencies,
  and state transitions; static checks for configured boundaries are planned.
- `E-EXPL-003`: planned — schema and policy checks can require retry, timeout,
  authorization, and structured-error declarations at configured boundaries.

## N — Nearby, Maintained Knowledge

### Goal

Knowledge lives close to what it governs, has a named owner and staleness
trigger, and does not duplicate facts the code or generated artifacts already
show. Navigation shape follows the project's ownership and operational needs,
not fixed directory-size thresholds.

### Required rules

- **N-KNOW-001 [REQUIRED] Governed knowledge.** Knowledge required to preserve
  correctness, compatibility, security, or operational safety `MUST` be stored
  in a repository-addressable location linked from the boundary it governs.
  It `MUST` name an owner and a staleness review trigger.
- **N-KNOW-002 [REQUIRED] Human-authored decisions.** Intent, trade-offs,
  business rationale, risk acceptance, and ownership decisions `MUST` be
  human-authored. Generated documentation `MUST NOT` present derived text as
  the authority for those decisions.
- **N-KNOW-003 [REQUIRED] Generated facts only.** Generated documentation `MUST`
  be limited to derived facts such as API reference, dependency graphs, schema
  documentation, CLI help, and configuration reference, and `MUST` identify its
  source and regeneration path.

### Defaults

- **N-KNOW-004 [DEFAULT] Navigation by judgment signals.** A directory `SHOULD`
  have nearby navigation or decision documentation when it is a public
  boundary, has a separate owner, contains non-obvious decisions, is edited
  independently of siblings, carries operational obligations, or serves as a
  navigation entry point. No file-count or subdirectory-count threshold applies.
- **N-KNOW-005 [DEFAULT] Bounded requisite context.** Documentation `SHOULD` use
  progressive disclosure and link from a concise entry point to details so a
  typical change loads only the requisite context.
- **N-KNOW-006 [DEFAULT] Normative-document maintenance fields.** A normative
  document `SHOULD` carry an owner, last-reviewed date, review trigger, and links
  to the executable checks that enforce it. Mechanical enforcement of this
  convention is planned for a later change.
- **N-KNOW-007 [DEFAULT] No code restatement.** Documentation `SHOULD NOT`
  duplicate facts already clear from code or a generated artifact; it should
  record decisions, constraints, navigation, and operational obligations.

### Experimental heuristics

- **N-KNOW-008 [EXPERIMENTAL] Knowledge-maintenance signals.** Measure stale
  links, expired review dates, ownerless normative documents, navigation
  failures, and requisite context for completed changes. Any proximity or size
  threshold remains unmeasured until validated in the target project.

### Allowed exceptions

A directory needs no README merely because it has a particular number of files
or child directories. A repository root needs no file with a prescribed name
when another maintained entry point provides the required navigation. Generated
documentation may publish derived facts, but not the human decisions listed in
`N-KNOW-002`.

External knowledge systems are allowed when the repository carries a stable
link, owner, access expectations, and staleness trigger. Knowledge available
only in a chat transcript is not an accepted source for a governing decision.

### Evidence

Chroma observed model-performance degradation as input context grew, including
on simple retrieval tasks. The claim does not establish that state tracking is
the cause; that causal interpretation remains GARDEN's own reading.
([CLAIM-N002](./evidence-registry.md#claim-n002)) A practitioner report
found runtime-enforced instructions more reliable than instruction-only rules
in one author's sessions. Its scope does not establish a universal context-file
size or directory documentation threshold.
([CLAIM-N001](./evidence-registry.md#claim-n001))

### Good example

```markdown
# Refund operations

Owner: Payments operations
Last reviewed: 2026-07-13
Review trigger: refund provider, retry policy, or alert changes
Checks: `tests/refunds/`, `monitoring/refund-alerts.yaml`

The rollback decision and provider trade-off are recorded here. API fields are
generated from `schemas/refund.yaml` by `tools/generate-api-docs`.
```

### Counterexample

```text
refunds/README.md: autogenerated prose guesses why retries are capped
team chat: actual rollback owner and rationale
generated/api.md: copied manually and no longer tied to its schema
```

The governing decisions have no maintained repository source, while the
derived reference has no regeneration path.

### Tooling support

- `N-KNOW-001`: manual-with-owner — boundary owners verify proximity,
  ownership, and review triggers; link and expiry checks are planned.
- `N-KNOW-002`: manual-with-owner — decision ownership and authorship require
  human confirmation.
- `N-KNOW-003`: automated where generated copies are declared. This repository
  uses `sync_references.py` to check canonical and generated reference parity;
  other generators must expose their own check command.
- `N-KNOW-006`: planned — the metadata convention is introduced here before a
  future configuration-driven check.

## How the principles interact

Graph-resolvable relationships make a capability's full change surface
findable. Adaptive locality keeps that surface proportionate to the change.
Replaceability evidence defines what verification must preserve.
Defense-in-depth verification tests those claims at relevant levels. Explicit
boundaries expose the state and policies those checks need to observe. Nearby,
maintained knowledge records the ownership, intent, and residual risk that code
and generated facts cannot supply.

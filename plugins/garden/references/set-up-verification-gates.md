---
owner: vshuraeff
last_reviewed: 2026-07-16
review_on:
  - rule-change
  - evidence-change
---
<!-- Generated from docs/how-to/set-up-verification-gates.md. Do not edit directly. Run sync_references.py --write to update. -->

# How to set up verification gates

This guide covers building the deterministic verification pipeline (**D**) that lets a
codebase avoid self-certification: an agent's own assessment is never sufficient, gates
decide. For the underlying rule set, see
[reference/principles.md](./principles.md).

## 1. Encode invariants as types first

The cheapest and earliest gate is the type system. Push as many invariants as possible
into types before reaching for lint or tests.

- Action: for every invariant currently stated only in prose or a comment, check whether
  it can be expressed as a type (a named shape, an enum instead of a string, a
  non-nullable field instead of a documented "must not be null").
- Acceptance signal: a change that violates the invariant fails to type-check, without
  running any test.

## 2. Add lint rules for what types cannot express

Import boundaries, naming conventions, and banned constructs are architecture decisions
that types alone do not enforce. Treat lint configuration as executable architecture
specification.

```text
# lint rule (pseudocode)
rule: slice "create-order" must not import from slice "cancel-order" internals
rule: no identifier built by string concatenation for domain dispatch
```

- Action: write lint rules for slice import boundaries, canonical naming, and any banned
  pattern named in [reference/principles.md](./principles.md) (for example
  reflection-based dispatch or ambient globals).
- Acceptance signal: a change that crosses a forbidden import boundary or reintroduces a
  banned construct fails lint in CI.

## 3. Write risk-scoped contract tests

An executable contract test is warranted at a configured boundary whose replacement can
affect correctness, compatibility, or security, such as a public API or a replaceable
component boundary under `R-REPL-001` and `R-REPL-002`. It is not required uniformly for
every slice.

- Action: for each boundary that warrants a contract test, write at least one test that
  exercises the contract as stated (not the implementation's internal steps). Place tests
  according to the project's configured capability and `[tests]` mapping; colocation is
  the `A-LOC-004` DEFAULT when the stack supports it.
- Acceptance signal: intentionally breaking the contract (for example, changing an output
  field's meaning) fails the contract test without any other code change.

## 4. Order CI gates to fail fast

Run gates in increasing cost order by default so a violation is caught at the cheapest
possible step: type check, then lint, then unit tests, then contract tests, then anything
slower. This is a cost-based optimization, not a pipeline invariant: a project may run a
cheaper contract test before a slow unit-test suite as long as every REQUIRED rule is
enforced before merge.

- Action: configure the CI pipeline in a cost-based order; type check normally runs before
  lint, lint before tests, and unit tests before slower integration or contract tests, but
  a cheaper contract test may run before a slow unit-test suite. Enforce every REQUIRED
  rule before merge and stop the pipeline at the first failure.
- Acceptance signal: a type error is reported without waiting for the test suite to run.

```text
# CI stage order (pseudocode)
stage type-check   # seconds
stage lint          # seconds
stage unit-tests     # tens of seconds
stage contract-tests  # minutes
stage clone-detection  # minutes, can run in parallel with contract-tests
```

Ordering by cost, not by importance, is what makes the pipeline fail fast: a
type error is nearly always cheaper to detect and more common than a contract
violation, so it belongs first even though both enforce REQUIRED rules.

## 5. Add a clone-detection job

Managed duplication (**A**) needs a mechanical signal, not a policy statement.

- Action: add a CI job that runs clone detection and reports blocks duplicated past your
  chosen threshold (see [apply-to-new-project.md](https://github.com/vshuraeff/garden/blob/master/docs/how-to/apply-to-new-project.md) step 7 for
  setting the threshold).
- Acceptance signal: the job produces a report on every CI run and the report is visible
  to whoever decides whether to extract an abstraction.

## 6. Extend verification beyond pre-merge gates

Pre-merge gates do not cover every verification level. `D-VER-001` requires each change
to identify the levels relevant to its risk.

- Action: define applicable runtime assertions (invariant checks that fire in production),
  telemetry or observability signals that reveal a post-deploy violation, and staged
  rollout as a verification gate through a canary or percentage rollout. When full
  verification is not feasible, record residual-risk acceptance as an explicit, owned,
  expiring decision under `D-VER-004`.
- Acceptance signal: the verification record states the result or why each level is not
  applicable; a residual-risk acceptance records its owner, supporting evidence, scope,
  and expiry.

## 7. Prefer runtime hooks and gates over instruction files for enforcement

An informal single-author practitioner report covering 166 Claude Code sessions found
compliance with a rule stated only in an instruction file at 25-40%, versus about 95%
when the same rule was enforced as a runtime hook or deterministic gate. It is not
peer-reviewed research. Use instruction files to explain, use gates to enforce.
([CLAIM-N001](./evidence-registry.md#claim-n001))

- Action: for every mechanizable REQUIRED rule you currently rely on an instruction file
  to convey, check whether it can instead be a lint rule, a type constraint, a
  pre-commit hook, or a CI gate; move it if it can.
- Acceptance signal: the rule now fails a build or a hook instead of depending on an
  agent reading and following a sentence in a context file.

## 8. Place LLM review after the gates, not instead of them

LLM code review is a useful complement but must never be the sole gate. One preprint,
evaluating 99 samples with its author's own four-agent system, reported a 39.7
percentage-point improvement over a single agent and a 50% false-positive rate for that
system. Its findings are hypotheses to verify, not verdicts or general proof that
multi-agent review works; consensus among samples from the same model is not independent
evidence. ([CLAIM-N003](./evidence-registry.md#claim-n003))

- Action: run LLM review only after type check, lint, and tests have passed; require each
  review pass to use a distinct lens and to cite file evidence for each finding; route
  findings back through a deterministic check (a new test, a new lint rule) rather than
  accepting them as final.
- Acceptance signal: no LLM review finding merges or blocks a change on its own; every
  accepted finding results in a new or modified deterministic gate, or is explicitly
  logged as a documented risk.

See [review-code-as-agent.md](./review-procedure.md) for how a reviewing agent should
use these gates during review.

## Next steps

- Applying this pipeline while scaffolding a new project:
  [apply-to-new-project.md](https://github.com/vshuraeff/garden/blob/master/docs/how-to/apply-to-new-project.md).
- Adding gates incrementally to an existing codebase:
  [retrofit-legacy-codebase.md](https://github.com/vshuraeff/garden/blob/master/docs/how-to/retrofit-legacy-codebase.md).
- The evidence behind the instruction-file compliance numbers:
  [explanation/why-agent-first-principles.md](https://github.com/vshuraeff/garden/blob/master/docs/explanation/why-agent-first-principles.md).

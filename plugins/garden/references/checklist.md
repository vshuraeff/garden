<!-- Generated from docs/reference/checklist.md. Do not edit directly. Run sync_references.py --write to update. -->
# GARDEN compliance checklist

## How to use this checklist

This checklist restates the rules from [principles.md](./principles.md) as
discrete, checkable items. Each item is tagged `[MUST]` or `[SHOULD]` and
carries the rule it maps to.

For an agent reviewer: evaluate each item against the code under review, and
cite file-and-line evidence for every answer, whether the item passes or
fails. Do not mark an item as passing without evidence; an unverifiable item
is a finding, not a pass. Report findings as hypotheses per
[review-code-as-agent.md](../how-to/review-code-as-agent.md), not verdicts.

For a CI script: items marked "mechanizable" below can be implemented as a
lint rule, static check, or test and run without a model in the loop; treat
those as the priority automation targets, since a rule enforced as a
deterministic gate is followed far more reliably than one stated only in an
instructions file. Items not marked mechanizable still belong in
human or agent review, but should be revisited periodically for whether a
mechanizable check can be added.

## G — Grep-first Discoverability

- [ ] `[MUST]` Every domain concept has exactly one canonical name, used in
      code, tests, docs, and error messages. (mechanizable: naming-registry
      lint)
- [ ] `[MUST]` Call sites are resolvable by static text search; no
      string-built identifiers, reflection-based dispatch, or
      convention-magic routing for domain logic. (mechanizable: lint rule
      banning dynamic identifier construction)
- [ ] `[MUST]` File and directory names match the concept names inside them.
- [ ] `[SHOULD]` Directory layout is flat and predictable rather than deeply
      nested.
- [ ] `[SHOULD]` Errors and log messages use grep-stable, unique phrases.

## A — Atomic Vertical Slices

- [ ] `[MUST]` Code is organized by capability (vertical slice), not by
      technical layer.
- [ ] `[MUST]` Each slice fits a one-context task: entry point, logic, data
      access, and tests together; functions are under approximately 50
      lines. (mechanizable: function-length lint)
- [ ] `[MUST]` Tests are colocated with the slice they verify. (mechanizable:
      colocation check)
- [ ] `[MUST NOT]` No abstraction is extracted before at least three
      concrete usages exist. (partially mechanizable: clone-detection
      signal in CI)
- [ ] `[SHOULD]` Slices communicate only through explicit interfaces; no
      slice reaches into another slice's internals.

## R — Regenerable Components

- [ ] `[MUST]` Every component has a contract (interface, behavioral spec,
      examples) precise enough to rewrite the component from scratch.
- [ ] `[MUST]` Contracts and specs are versioned next to the code they
      govern.
- [ ] `[MUST]` Dependencies at slice boundaries point at contracts (ports),
      not concrete implementations. (mechanizable: import-boundary lint)
- [ ] `[SHOULD]` Extension happens by adding adapters or implementations at
      explicit ports, not by editing unrelated components.
- [ ] `[SHOULD]` When code and contract disagree, the contract is corrected
      first and the code regenerated, not silently patched into divergence.

## D — Deterministic Verification

- [ ] `[MUST]` Every stated invariant exists as a type, lint rule, test, or
      CI gate; if it cannot be checked deterministically, it is documented
      as a risk, not stated as a rule.
- [ ] `[MUST NOT]` No merge or ship decision rests on an agent's own
      assessment of its output; a deterministic gate decides.
      (mechanizable: CI gate required for merge)
- [ ] `[MUST]` Lint configuration enforces import boundaries, naming rules,
      and layering as executable architecture, not convention.
- [ ] `[SHOULD]` LLM review runs as multiple passes with genuinely different
      lenses, and its findings are triaged as hypotheses to verify, not
      verdicts.
- [ ] `[SHOULD]` Violations surface at the earliest gate: type check before
      test, test before review.

## E — Explicit Everything

- [ ] `[MUST]` Dependencies are passed explicitly (parameters, constructor
      arguments), never via hidden globals or ambient state. (mechanizable:
      lint rule banning ambient/global access in domain code)
- [ ] `[MUST]` Every interface is fully typed; data crossing a boundary has
      a named, versioned shape. (mechanizable: type check)
- [ ] `[MUST NOT]` No required ordering between operations exists as
      unenforced temporal coupling.
- [ ] `[MUST NOT]` No magic values; every literal with meaning has a named,
      documented constant. (mechanizable: magic-value lint)
- [ ] `[MUST]` Errors are self-describing: what failed, why, and what the
      caller can do, in grep-stable wording.
- [ ] `[SHOULD]` Code favors boring, explicit constructs over clever,
      compact ones.

## N — Navigable Knowledge

- [ ] `[MUST]` The repository root has a short hand-written `CONTEXT.md` at
      most 200 lines; no autogenerated bulk dump. (mechanizable: line-count
      check)
- [ ] `[MUST]` Every significant directory has a README stating purpose,
      contracts, and links, so knowledge for an edit is at most one hop
      from the edit site. (see "significant directory" in
      [glossary.md](./glossary.md))
- [ ] `[MUST]` The "why" (intent, trade-offs, decision records) is
      human-authored; agent drafts are marked as such until human-approved.
- [ ] `[SHOULD]` Documentation follows progressive disclosure: a summary
      layer links down only where needed.
- [ ] `[SHOULD]` Docs that only restate what the code already shows have
      been deleted.

## Reading the result

An agent or CI job applying this checklist should report, per item: pass,
fail, or not applicable, each with cited evidence. A checklist run with
unresolved `[MUST]` items is a blocking finding; unresolved `[SHOULD]` items
are recorded but do not block on their own. See
[set-up-verification-gates.md](../how-to/set-up-verification-gates.md) for
wiring these items into CI.

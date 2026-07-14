---
name: audit
description: "Audit a codebase against the GARDEN checklist using its effective .garden.toml configuration, REQUIRED/DEFAULT/EXPERIMENTAL results, cited evidence, explicit unknowns, and missing-gate candidates. Use for requests such as GARDEN audit, GARDEN compliance check, audit this codebase against GARDEN, assess GARDEN adoption, or identify missing GARDEN gates."
---

# Audit GARDEN adoption

Read `references/checklist.md` relative to the plugin root before evaluating any item. Read the sibling `references/principles.md` for the complete rule text and `references/glossary.md` before applying defined terms. For `N-KNOW-004`, assess the public-boundary, separate-owner, non-obvious-decision, independent-edit, operational-obligation, and navigation-entry signals; do not infer a documentation requirement from file or subdirectory counts.

Read the effective project configuration before evaluating the checklist. Run `uv run --no-project <plugin-root>/tools/garden_cli.py config show <project-root>` and retain each value's `file` or `default` origin. If the command reports an invalid config, record the affected checklist items as `unknown` unless independent evidence resolves them; never substitute the schema defaults for an invalid project config.

Evaluate every checklist item against the effective config and cited project evidence. Use only these result states: `pass`, `fail`, `not-applicable`, and `unknown`. Missing evidence, ambiguous applicability, an out-of-scope stack, or an unavailable required check is `unknown`, never `pass`. Cite file-and-line evidence for every state and explain why a not-applicable classification is allowed by the rule's scope.

Use the checklist's normative levels exactly:

- A REQUIRED failure is a normative failure when the project fails the item without a valid, unexpired residual-risk acceptance permitted by that rule.
- A DEFAULT failure is a heuristic finding when no documented configuration exception covers it.
- An EXPERIMENTAL result is a heuristic observation. An unmeasured experiment does not block merely because it is unmeasured.

Surface every configured `[[exceptions]]` entry from the effective config. For each entry, report its rule ID, paths, owner, reason, and `review_after` expiry or review marker. Treat an item covered by an in-scope, valid, unexpired exception as satisfied through that exception only when the checklist item permits that exception format; report it as `pass (exception)` and cite the exception instead of presenting direct conformance. An incomplete, expired, out-of-scope, or disallowed exception does not satisfy the item.

Identify every item marked mechanizable in the checklist and prioritize an applicable lint rule, static check, or test over repeating manual review. Mechanize REQUIRED rules wherever the target stack permits it. Hooks and deterministic gates enforce a rule far more reliably than an instruction file alone. Preserve prose for intent, but make enforceable rules fail deterministically. [CLAIM-N001]

For every `fail` or `unknown` finding, report the stable rule ID, normative level, confidence, exact evidence, why the item failed or could not be evaluated, and concrete remediation or evidence needed to resolve it. Do not inflate confidence when applicability or evidence is incomplete.

Use this fixed report template, in this order:

## 1. Effective configuration and exceptions

List the command result, effective values relevant to the audit, their origins, and every configured exception with owner, reason, scope, and expiry or review marker. State whether each exception is valid for the checklist item it names.

## 2. REQUIRED items

| Principle | Pass | Fail | Not applicable | Unknown | Evidence references |
| --- | ---: | ---: | ---: | ---: | --- |
| G |  |  |  |  |  |
| A |  |  |  |  |  |
| R |  |  |  |  |  |
| D |  |  |  |  |  |
| E |  |  |  |  |  |
| N |  |  |  |  |  |

List every REQUIRED item with its state and cited evidence. For each failure or unknown, include confidence and concrete remediation. Mark a valid permitted residual-risk acceptance as `pass (exception)` rather than presenting the underlying evidence gap as direct conformance.

## 3. DEFAULT items

| Principle | Pass | Fail | Not applicable | Unknown | Evidence references |
| --- | ---: | ---: | ---: | ---: | --- |
| G |  |  |  |  |  |
| A |  |  |  |  |  |
| R |  |  |  |  |  |
| D |  |  |  |  |  |
| E |  |  |  |  |  |
| N |  |  |  |  |  |

List every DEFAULT item with its state and cited evidence. For each failure or unknown, include confidence and concrete remediation. Cite a valid documented configuration exception when it satisfies the item.

## 4. EXPERIMENTAL items

| Principle | Pass | Fail | Not applicable | Unknown | Evidence references |
| --- | ---: | ---: | ---: | ---: | --- |
| G |  |  |  |  |  |
| A |  |  |  |  |  |
| R |  |  |  |  |  |
| D |  |  |  |  |  |
| E |  |  |  |  |  |
| N |  |  |  |  |  |

List every EXPERIMENTAL item with its measurement state and cited evidence. For each failure or unknown, include confidence and a concrete next measurement or evidence step. Do not treat an unmeasured experiment as a normative failure.

## 5. Mechanizable-but-missing gates

List every checklist item marked mechanizable that is not currently enforced. Name the candidate lint rule, static check, test, hook, or CI gate and cite the evidence showing the gap.

Report findings against the checklist only. Do not include `compliant`, `approved`, `safe to merge`, or any equivalent self-certifying verdict in the audit output.

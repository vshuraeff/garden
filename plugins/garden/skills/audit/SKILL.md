---
name: audit
description: "Audit a codebase against the GARDEN compliance checklist with cited evidence, MUST/SHOULD findings, and missing-gate candidates. Use for requests such as GARDEN audit, GARDEN compliance check, audit this codebase against GARDEN, assess GARDEN adoption, or identify missing GARDEN gates."
---

# Audit GARDEN compliance

Read `references/checklist.md` relative to the plugin root before evaluating any item. Read the sibling `references/principles.md` for the complete rule text and `references/glossary.md` before applying defined terms such as significant directory.

Evaluate every checklist item. Cite file-and-line evidence for every pass, failure, and not-applicable result. Do not mark an item as passing without evidence; treat an unverifiable item as a finding.

Treat unresolved `[MUST]` items as blocking findings. Treat unresolved `[SHOULD]` items as non-blocking findings. Identify every item marked "mechanizable" in the checklist and prioritize an applicable lint rule, static check, or test over repeating manual review.

Mechanize MUST rules wherever the target stack permits it. The N-principle evidence reports roughly 25–40% compliance when a rule exists only in an instruction file and roughly 95% when the same rule is enforced by a runtime hook or deterministic gate. Preserve prose for intent, but make enforceable rules fail deterministically.

Use this fixed report template, in this order:

## 1. Summary table

| Principle | Pass | Fail | Not applicable | Evidence references |
| --- | ---: | ---: | ---: | --- |
| G |  |  |  |  |
| A |  |  |  |  |
| R |  |  |  |  |
| D |  |  |  |  |
| E |  |  |  |  |
| N |  |  |  |  |

List one row per principle. Include cited evidence for every count and item classification.

## 2. Blocking findings

List every unresolved `[MUST]` item. For each, give the checklist rule identifier, exact file-and-line evidence, why the item remains unresolved, and the concrete evidence or deterministic gate that would resolve it.

## 3. Non-blocking findings

List every unresolved `[SHOULD]` item. For each, give the checklist rule identifier, exact file-and-line evidence, why the item remains unresolved, and what would resolve it.

## 4. Mechanizable-but-missing gates

List every checklist item marked mechanizable that is not currently enforced. Name the candidate lint rule, static check, test, hook, or CI gate and cite the evidence showing the gap.

Report findings against the checklist only. Do not include `compliant`, `approved`, `safe to merge`, or any equivalent self-certifying verdict in the audit output.

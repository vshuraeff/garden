---
name: bootstrap
description: "Bootstrap a new GARDEN project by creating .garden.toml, choosing a capability strategy that fits the project type, defining public boundaries, and wiring deterministic gates. Use when starting fresh codebases, monorepos, or agent-ready systems in any language or tech stack."
---

# Bootstrap a GARDEN project

Read `references/principles.md` relative to the plugin root before applying the GARDEN rules. Read the sibling `references/glossary.md` before applying terms such as capability strategy, managed duplication, change-distance, or requisite context.

Treat every mechanizable REQUIRED rule as a gate requirement. Hooks and deterministic gates enforce a rule far more reliably than an instruction file alone. Keep prose for intent; encode enforceable rules in types, lint, tests, hooks, or CI. [CLAIM-N001]

Complete the steps in order. Do not begin the next step while its acceptance signal fails; correct the current artifact first.

1. Determine the project type.

   Action: Classify the project as `service`, `library`, `cli`, `monorepo`, `infra`, or `other` from its intended build, delivery, and ownership model.

   Acceptance signal: One supported `project.type` value describes the project, and any uncertainty that affects structure or gates is recorded for the project owner.

2. Discover the build, test, and source roots.

   Action: Inspect the language, package manager, build files, test runner, source directories, generated paths, and existing CI configuration. Identify which roots contain maintained source and tests for the selected project type.

   Acceptance signal: The proposed scan roots and globs include maintained source and tests while excluding generated, dependency, and build-output paths.

3. Create `.garden.toml`.

   Action: Run `uv run --no-project <plugin-root>/tools/garden_cli.py init <project-root>`, then review the detected `project.type`, scan roots, source globs, and context-file settings. Do not start from a registry-only activation workflow.

   Acceptance signal: The project has a schema v1 `.garden.toml` whose detected values match the project type and discovered roots.

4. Choose a capability strategy.

   Action: Propose a capability map that fits the project type and configure `capabilities.strategy` as `children`, `explicit`, `markers`, or `none`. A vertical slice is one allowed strategy, not a required root layout. Use the [service](../../../../docs/reference/configuration.md#service-example), [library](../../../../docs/reference/configuration.md#library-example), [monorepo](../../../../docs/reference/configuration.md#monorepo-example), and [infrastructure](../../../../docs/reference/configuration.md#infrastructure-example) examples as starting points instead of copying one structure across project types.

   Acceptance signal: The config states how each capability resolves to its code, state, tests, operational artifacts, boundaries, and owner, including any shared roots or explicit mappings. A `markers` strategy is labeled EXPERIMENTAL and its unresolved capability results are not treated as passes.

5. Identify public boundaries.

   Action: List published APIs, independently deployed components, persisted schemas, external integrations, trust boundaries, and other explicitly versioned boundaries. Configure their paths under `boundaries.public`; keep private internal modules outside that list.

   Acceptance signal: Every public boundary has an owner and classification, and private implementation modules are not mislabeled as public or versioned.

6. Add contracts at public boundaries.

   Action: Add `CONTRACT.md` or another accepted contract artifact only where a public boundary needs observable interface, behavior, errors, compatibility, ownership, or replacement evidence. Configure accepted names and required contract categories in `.garden.toml`. Do not impose a contract or artificial `Version:` line on every internal module.

   Acceptance signal: Each identified public boundary records the applicable replacement evidence and compatibility policy; omitted evidence categories are marked not applicable with a reason.

7. Configure deterministic gates.

   Action: Configure type checking, linting, unit tests, contract or integration tests, and clone detection as fail-fast CI gates where the stack supports them. Convert each mechanizable REQUIRED rule into the earliest reliable type, lint, test, hook, or CI check.

   Acceptance signal: Each stated mechanizable invariant maps to a reproducible gate, and missing or inapplicable verification levels are recorded rather than implied to pass.

8. Capture the initial baseline.

   Action: Record the date, measurement method, and starting value for median files opened per task, duplicate findings from clone detection, changed-module count, escaped regressions, CI rule coverage as the share of stated invariants enforced by deterministic gates, and unknown or incomplete audit count. A project may add search-miss rate as an EXPERIMENTAL measurement, but it is not part of the required baseline set.

   Acceptance signal: All six baseline fields are recorded with reproducible measurement methods so future retrofit passes can compare like with like.

9. Mark experiments explicitly.

   Action: Record any unvalidated rule, threshold, marker strategy, or measurement the project is trying as EXPERIMENTAL. Do not present an experiment as REQUIRED until the normative model and supporting evidence classify it that way.

   Acceptance signal: Every trial is labeled EXPERIMENTAL with an owner, measurement plan, and review point; no deterministic gate blocks merely because an experiment is unmeasured.

## Generate stack-specific gates

Detect the target project's language, package manager, build files, test runner, and existing CI configuration. Generate only stack-compatible artifacts; do not assume a language or toolchain.

Generate, at minimum:

- A linter configuration that acts as an executable architecture specification. Enforce naming and configured capability boundaries where supported; cross-capability access uses a declared interface, schema, adapter, or contract instead of private internals.
- A fail-fast CI pipeline in this order: type-check, lint, unit-tests, contract-tests, clone-detection. Keep type-check through unit-tests strictly sequential. Permit clone-detection to run in parallel with contract-tests, but only after unit-tests pass.
- A clone-detection job that reports duplicate findings. Treat the rule of three as a DEFAULT and record any override through the project's documented configuration exception.

Read the plugin's `references/principles.md` again when selecting each enforceable rule. Convert every mechanizable REQUIRED rule into the strongest stack-supported type, lint, test, hook, or CI gate; document an invariant that cannot be made deterministic as a risk rather than leaving it as prose.

Mark any agent-drafted "why" in a context file or contract as a draft until a human authors or approves it. Do not represent agent-generated intent, trade-offs, or decision records as human-approved.

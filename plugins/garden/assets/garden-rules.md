<!-- Generated from plugins/garden/rules/garden-rules.toml. Do not edit directly. Run generate_rules_digest.py --write to update. -->
# GARDEN project rules

Use `REQUIRED` for rules whose violation creates a demonstrable correctness,
compatibility, or security risk. Use `DEFAULT` for configurable recommendations
with a documented reason. Use `EXPERIMENTAL` only for measured hypotheses. Cite
the stable rule ID in reviews, exceptions, and risk records.

## G — Graph-resolvable Discoverability

- `G-DISC-001 [REQUIRED]` Make production domain relationships recoverable through grep, an AST or LSP, a symbol index, a route map, a plugin or schema registry, or generated wiring. Back dynamic dispatch with a machine-readable manifest, schema, registry, or generated map.
- `G-DISC-002 [REQUIRED]` Use one canonical name inside each bounded context. Add explicit translation maps at boundaries whose contexts use different names.
- `G-DISC-003 [REQUIRED]` Give cross-boundary errors stable machine-readable codes and structured fields. Human-readable text is not a compatibility key.
- `G-DISC-004 [DEFAULT]` Align files, symbols, routes, tests, and docs with the bounded context's canonical concepts or registry entries.
- `G-DISC-005 [DEFAULT]` Use the lowest-cost graph mechanism the stack can inspect reliably; direct references are not mandatory when a registry or generated graph is authoritative.

## A — Adaptive Capability Locality

- `A-LOC-001 [REQUIRED]` State how each production capability maps to its code, state, tests, operational artifacts, boundaries, and owner.
- `A-LOC-002 [REQUIRED]` Identify affected contracts and run relevant compatibility or integration checks when a change crosses a capability, trust, persistence, or deployment boundary.
- `A-LOC-003 [DEFAULT]` Minimize unrelated modules touched, boundary crossings, requisite context, and ownership handoffs for a typical capability change. Choose the physical layout that fits the stack.
- `A-LOC-004 [DEFAULT]` Colocate tests when the stack supports it; otherwise maintain a stable production-to-test map.
- `A-LOC-005 [DEFAULT]` Apply the Rule of Three before sharing an abstraction. Override it only for a documented boundary, security control, or platform constraint.
- Shared kernels, compiler passes, data pipelines, SDKs, infrastructure repositories, embedded targets, and generated code may use layouts suited to their constraints; document their capability strategy instead of forcing a vertical-slice root.

## R — Replaceable Components

- `R-REPL-001 [REQUIRED]` Record applicable replaceability evidence: public interface or schema, behavioral examples, characterization tests, property tests where applicable, compatibility tests, non-functional requirements, migration and rollback, observability, data ownership, and concurrency or ordering semantics. Mark omissions not applicable with a reason.
- `R-REPL-002 [REQUIRED]` Apply SemVer only to published APIs, independently deployed components, persisted schemas, external integrations, or boundaries explicitly designated as versioned. Track private internal modules through Git; do not add an artificial `Version:` line.
- `R-REPL-003 [REQUIRED]` Characterize legacy behavior before a replacement or behavior-preserving rewrite.
- `R-REPL-004 [REQUIRED]` Start a bug fix with a failing executable test or reproducer.
- `R-REPL-005 [REQUIRED]` Do not rewrite observable undocumented behavior without compatibility evidence for affected consumers.
- `R-REPL-006 [REQUIRED]` Define a greenfield public boundary's behavior and compatibility expectations before implementation. Do not apply contract-first rewriting to legacy code before characterization.
- `R-REPL-007 [DEFAULT]` Use declared interfaces, schemas, adapters, or ports when they reduce consumer coupling. Do not create an interface around a private module without replacement or test value.
- Keep `CONTRACT.md` and SemVer guidance for boundaries classified under `R-REPL-002`; no particular contract filename is required for other components.

## D — Defense-in-depth Verification

- `D-VER-001 [REQUIRED]` Record the result or not-applicable reason for each relevant level: static validation; unit or property tests; integration or contract tests; security or fuzz testing; runtime assertions and telemetry; canary or staged rollout; independent review; and residual-risk acceptance.
- `D-VER-002 [REQUIRED]` Run applicable types, lint, tests, and CI from versioned configuration. LLM review never substitutes for an executable check.
- `D-VER-003 [REQUIRED]` Do not hide a flaky check behind automatic retries or report retry-to-green as a clean pass.
- `D-VER-004 [REQUIRED]` Record an owner, supporting evidence, scope, and expiry for every human residual-risk acceptance.
- `D-VER-005 [REQUIRED]` An agent must not be the sole authority that its own change is correct or ready to ship.
- `D-VER-006 [DEFAULT]` Surface violations at the earliest useful gate without weakening higher-level checks.
- `D-VER-007 [DEFAULT]` Run relevant independent review lenses and treat LLM findings as hypotheses requiring confirmation.
- A passing deterministic gate is evidence, not proof that defects are absent.

## E — Explicit Boundaries and State

- `E-EXPL-001 [REQUIRED]` State shapes, validation, compatibility expectations, and ownership at public APIs, trust boundaries, and persistence formats.
- `E-EXPL-002 [REQUIRED]` Expose side effects, external dependencies, and state transitions at the boundary that controls them. Do not let hidden ambient state determine cross-boundary domain behavior.
- `E-EXPL-003 [REQUIRED]` Expose retry, timeout, authorization, and cross-boundary error policies, including stable error codes, structured fields, and owners.
- `E-EXPL-004 [DEFAULT]` Keep local explicitness proportionate. Do not require a named constant for every literal, full type ceremony inside a small function, manual injection for static dependencies, replacement of generated wiring, or abandonment of reasonable framework defaults.
- `E-EXPL-005 [DEFAULT]` Name or explain a literal only when it affects domain or operational behavior and is not obvious at its point of use.

## N — Nearby, Maintained Knowledge

- `N-KNOW-001 [REQUIRED]` Keep governing correctness, compatibility, security, and operational knowledge at a repository-addressable location linked from its boundary, with an owner and staleness trigger.
- `N-KNOW-002 [REQUIRED]` Keep intent, trade-offs, business rationale, risk acceptance, and ownership decisions human-authored.
- `N-KNOW-003 [REQUIRED]` Generate only derived facts such as API reference, dependency graphs, schema docs, CLI help, or config reference. Identify the source and regeneration path.
- `N-KNOW-004 [DEFAULT]` Add nearby navigation or decision docs when a directory is a public boundary, has a separate owner, contains non-obvious decisions, is edited independently, carries operational obligations, or is a navigation entry point. Do not use file-count or subdirectory-count thresholds.
- `N-KNOW-005 [DEFAULT]` Use progressive disclosure so a typical change loads only requisite context; no universal context-file name or line limit applies.
- `N-KNOW-006 [DEFAULT]` Give normative docs an owner, last-reviewed date, review trigger, and links to executable checks. Mechanical enforcement is planned.
- `N-KNOW-007 [DEFAULT]` Delete human-authored docs that only restate code or generated facts.

Record DEFAULT overrides and deferred EXPERIMENTAL measurements with the rule
ID, owner, reason, evidence, and review trigger. Record a missing REQUIRED check
as residual risk under `D-VER-004`, never as a pass.

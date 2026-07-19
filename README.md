# GARDEN

GARDEN is a system of six language-agnostic software design principles for the
agent-first era, where code is written, reviewed, and analyzed primarily by LLM agents
and humans set intent and constraints but rarely read the code line by line. The
metaphor: a codebase is a garden that agents continuously tend, and untended code grows
wild. GARDEN principles are the tending practices intended to keep a codebase navigable,
verifiable, and extensible across years of agent-driven changes.

## The six principles

| Letter | Name | One-liner |
|---|---|---|
| G | Graph-resolvable Discoverability | Production relationships are recoverable through a stated mechanism, and canonical names are scoped to bounded contexts with explicit translation maps at their boundaries. |
| A | Adaptive Capability Locality | Each project states a capability strategy that fits its stack; locality is judged by change-distance, boundary crossings, ownership, and requisite context rather than a prescribed tree. |
| R | Replaceable Components | Boundaries record the behavior and compatibility evidence needed for safe replacement, while versioning applies only where the boundary requires it. |
| D | Defense-in-depth Verification | Changes carry independent, reproducible evidence selected for their risks; executable gates and an authorized decision process prevent agent self-certification. |
| E | Explicit Boundaries and State | Inputs, outputs, side effects, state transitions, and operational policies are explicit at the boundaries where omission would change behavior or risk. |
| N | Nearby, Maintained Knowledge | Governed knowledge stays near its boundary, and navigation docs follow public-boundary, ownership, decision, independent-edit, operational, and entry-point signals rather than directory-size thresholds. |

## Evidence status

[Benchmark v1](docs/evidence/benchmark-v1.md) is a deterministic, non-agent
benchmark over fixed synthetic corpora. Its detection, evidence, and mutation
suites pass; migration remains a documented negative result because the
preregistered parity invariant conflicts with intentional configured-mode
detection fixes.

[Benchmark v2](docs/evidence/benchmark-v2.md) records the 2026-07-19 live
agent-value benchmark run. All 36 cell-runs passed across `garden_on` and
`garden_off`, so these tasks show a ceiling effect and no task-success delta.
The run measured enforcement overhead in tokens, wall-clock time, and estimated
cost. The agent-value benchmark exists and has run, but this corpus does not
demonstrate an outcome advantage for GARDEN.

## Who this is for

Both LLM agents that read, write, and review code via tools, and the human engineers
who set intent, approve trade-offs, and own the "why" behind a codebase. GARDEN assumes
neither party reads or holds the whole codebase in mind at once; it optimizes for
partial, repeated, tool-mediated attention rather than continuous human familiarity.

## How the docs are organized

This documentation follows the [Diataxis](https://diataxis.fr) framework: each page
belongs to exactly one of four quadrants, so you can go straight to the kind of content
you need instead of searching a single sprawling document.

- Start with the **tutorial** to learn GARDEN by building something small.
- Use the **how-to guides** when you have a concrete task to do.
- Use the **reference** docs when you need the authoritative statement of a rule or term.
- Read the **explanation** docs when you want to understand why GARDEN is shaped this way.

### Tutorial

- [Getting started](docs/tutorials/getting-started.md) — build a tiny link-shortener
  service while applying all six principles step by step.

### How-to guides

- [Apply GARDEN to a new project](docs/how-to/apply-to-new-project.md)
- [Migrate from GARDEN v0](docs/how-to/migrate-from-garden-v0.md)
- [Retrofit a legacy codebase](docs/how-to/retrofit-legacy-codebase.md)
- [Set up verification gates](docs/how-to/set-up-verification-gates.md)
- [Review code as an agent](docs/how-to/review-code-as-agent.md)

### Reference

- [Principles](docs/reference/principles.md) — the canonical statement of all six
  principles: definitions, rules, anti-patterns, examples.
- [Checklist](docs/reference/checklist.md) — a machine-friendly compliance checklist for
  agent reviewers and CI scripts.
- [Report schema](docs/reference/report-schema.md) — JSON contract for deterministic
  structural inspection results.
- [Rule registry](docs/reference/rule-registry.md) — canonical machine-readable rule
  metadata and the derived artifacts and drift checks that use it.
- [Glossary](docs/reference/glossary.md) — canonical meanings of GARDEN terms.

### Explanation

- [Why agent-first principles](docs/explanation/why-agent-first-principles.md) — the
  shift in who reads code, and why principles tuned for human IDE navigation misfire.
- [The GARDEN model](docs/explanation/the-garden-model.md) — the garden metaphor and how
  the six principles reinforce each other as a system.
- [Relation to classic principles](docs/explanation/relation-to-classic-principles.md) —
  what GARDEN keeps, weakens, or rejects from SOLID, DRY, YAGNI, and other classic
  principles, and why.

## Standalone reference document

[`docs/reference/principles.md`](docs/reference/principles.md) is self-contained: it
does not depend on any other file in this repository. You can copy it into any project
as a standalone, agent-facing statement of the GARDEN principles.

## Claude Code and Codex plugin

This repository serves as both a Claude Code and Codex plugin marketplace. Both
harnesses install the same `plugins/garden` package and load the same skills,
references, review policy, and hook implementation.

The GARDEN plugin provides bootstrap, retrofit, review, and audit skills; an isolated
reviewer for both harnesses; deterministic lifecycle hooks; and local inspection tools
through MCP and the `garden` CLI.

Claude Code:

```sh
claude plugin marketplace add vshuraeff/garden
claude plugin install garden@garden
```

Codex CLI:

```sh
codex plugin marketplace add vshuraeff/garden
codex plugin add garden@garden
```

See [`plugins/garden/README.md`](plugins/garden/README.md) for component details and
[`docs/how-to/install-codex-and-claude-plugin.md`](docs/how-to/install-codex-and-claude-plugin.md)
for installation and local-development commands.

This project is available under the [MIT License](LICENSE).

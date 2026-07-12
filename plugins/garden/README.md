# GARDEN Claude Code plugin

This plugin provides enforcement tooling for the GARDEN agent-first design principles:
bootstrap, retrofit, review, and audit workflows, with deterministic hooks for
mechanizable rules.

## Components

- `garden:bootstrap` applies GARDEN when starting a new project.
- `garden:retrofit` applies GARDEN to a legacy codebase.
- `garden:review` reviews code through the GARDEN lenses.
- `garden:audit` checks a codebase for compliance with the GARDEN checklist.
- `garden:start` installs an optional project UserPromptSubmit prompt-routing hook and/or
  project rules file; `garden:stop` removes that tooling.
- `garden-reviewer` is an isolated, read-only GARDEN-lens reviewer for use after gates
  run or when the implementer must not review its own work.
- PostToolUse hooks activate only when `naming-registry.txt` exists at the project root.
  They check the mechanizable MUST rules: the `CONTEXT.md` 200-line budget and the
  `CONTRACT.md` `Version:` line. They give advisory nudges for contract and test
  colocation practices that are not hard gates.

## Install

```sh
claude plugin marketplace add vshuraeff/garden
claude plugin install garden@garden
```

For local development from a clone:

```sh
claude plugin marketplace add ./garden
claude plugin install garden@garden
```

Alternatively, use the interactive `/plugin` command.

## Maintenance

Files in `references/` are verbatim copies of `docs/reference/principles.md`,
`docs/reference/checklist.md`, `docs/reference/glossary.md`, and
`docs/how-to/review-code-as-agent.md`. Re-sync them by hand whenever those source
files change.

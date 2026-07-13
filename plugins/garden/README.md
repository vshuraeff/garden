# GARDEN plugin for Claude Code and Codex

One plugin directory supports both harnesses. `.claude-plugin/plugin.json` and
`.codex-plugin/plugin.json` are thin packaging adapters; the working components remain
shared.

## Shared components

- `garden:bootstrap` applies GARDEN when starting a project.
- `garden:retrofit` applies GARDEN incrementally to an existing codebase.
- `garden:review` reviews a change through the six GARDEN lenses.
- `garden:audit` evaluates the complete compliance checklist.
- `garden:start` installs project instructions for Claude Code, Codex, or both;
  `garden:stop` removes only those instruction copies.
- `garden-reviewer` is the isolated, read-only reviewer used after deterministic gates.
  Claude Code loads it from the plugin; `garden:start` installs the schema-valid Codex
  project agent at `.codex/agents/garden-reviewer.toml`.
- `hooks/hooks.json` routes GARDEN prompts and checks changed files when a project-root
  `naming-registry.txt` activates the methodology.
- `garden_inspect_project` and `garden_check_file` expose the deterministic checks as
  read-only MCP tools. `bin/garden` exposes the same checks to a shell.

The hard hook checks cover the `CONTEXT.md` 200-line budget and the required
`Version: MAJOR.MINOR.PATCH` first line in `CONTRACT.md`. Missing contracts and
colocated tests are advisory because the hook cannot prove the intended slice boundary.

## Harness adapters

Claude Code discovers `.claude-plugin/plugin.json`, the Markdown agent, skills, hooks,
and `.mcp.json`. Codex discovers `.codex-plugin/plugin.json`, the shared skills, hooks,
and MCP config; project-scoped Codex agents are installed by `garden:start` because
Codex loads custom TOML agents from `.codex/agents/`, not plugin-root Markdown agents.

The shared MCP launcher accepts both plugin path models. The server requests workspace
roots from the client and confines every inspection to those canonical roots. Both
harnesses start the dependency-free Python server in `tools/garden_mcp.py`.

Codex command-approval `.rules` files are not bundled. Those files change sandbox
approval policy, while GARDEN rules are coding instructions. `garden:start` puts the
same `assets/garden-rules.md` content through the provenance-aware project installer.

## Install

`uv` must be available on `PATH`; every bundled Python entry point runs through
`uv run --no-project`, and maintainer tools run through `uvx`.

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

Start a new Codex session after installation. Open `/hooks` and review the plugin hook
definitions before trusting them. In Claude Code, run `/reload-plugins` after updating
an installed development copy.

## Maintenance

Files in `references/` are verbatim copies of `docs/reference/principles.md`,
`docs/reference/checklist.md`, `docs/reference/glossary.md`, and
`docs/how-to/review-code-as-agent.md`. Re-sync them whenever those source files change.

Run these checks before publishing:

```sh
uv run --no-project -m unittest plugins/garden/tools/test_garden_tools.py -v
uv run --no-project plugins/garden/tools/validate_package.py
uv run --with pyyaml /path/to/plugin-creator/scripts/validate_plugin.py plugins/garden
claude plugin validate plugins/garden
```

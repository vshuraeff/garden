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
  `.garden.toml` activates the methodology, with `naming-registry.txt` retained as a
  legacy fallback.
- `garden_inspect_project` and `garden_check_file` expose the deterministic checks as
  read-only MCP tools. `bin/garden` exposes the same checks to a shell.

The hard hook checks cover the `CONTEXT.md` 200-line budget and the required
`Version: MAJOR.MINOR.PATCH` first line in `CONTRACT.md`. Missing contracts and
colocated tests are advisory because the hook cannot prove the intended slice boundary.
A hook event builds one project scan shared by every affected file rather than scanning
once per file. A time-budget overrun is advisory and does not block the hook; an
entry-budget overrun is an error that blocks the hook like the existing hard checks.

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

`sync_references.py` defines the canonical `REFERENCE_PAIRS` for `references/`:

- `docs/reference/principles.md` -> `references/principles.md`
- `docs/reference/checklist.md` -> `references/checklist.md`
- `docs/reference/glossary.md` -> `references/glossary.md`
- `docs/how-to/review-code-as-agent.md` -> `references/review-procedure.md`
- `docs/evidence/evidence-registry.md` -> `references/evidence-registry.md`
- `docs/how-to/set-up-verification-gates.md` -> `references/set-up-verification-gates.md`
- `docs/reference/rule-registry.md` -> `references/rule-registry.md`
- `docs/reference/configuration.md` -> `references/configuration.md`

Re-sync these files whenever a source changes. Links between packaged sources are
rewritten to packaged-relative targets; links to unpackaged docs use GitHub URLs.
`validate_package.py` `validate_packaged_links()` enforces this self-containment, so
the installed plugin needs no source-repository checkout to navigate its references.

Run these checks before publishing:

```sh
uv run --no-project -m unittest discover -s plugins/garden/tools -p "test_*.py" -v
uv run --no-project -m unittest plugins.garden.tools.test_harness_smoke -v
uv run --no-project plugins/garden/tools/validate_package.py
uv run --with pyyaml /path/to/plugin-creator/scripts/validate_plugin.py plugins/garden
claude plugin validate plugins/garden
```

`test_harness_smoke.py` runs packaged copies through installed CLI binaries instead of
in-process fixtures and uses `unittest.skipTest` when either CLI is absent.

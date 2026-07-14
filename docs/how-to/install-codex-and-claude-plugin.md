---
owner: vshuraeff
last_reviewed: 2026-07-14
review_on:
  - major-release
---

# Install the GARDEN plugin in Codex or Claude Code

The repository publishes one `garden` package through two marketplace manifests. Use
the command for the harness where the plugin should be available. Installing it in both
does not duplicate the source package.

Install `uv` first and keep it on `PATH`. The plugin uses one Python toolchain surface:
`uv run --no-project` for runtime scripts and `uvx` for maintainer tools.

## Install from GitHub

For Codex CLI:

```sh
codex plugin marketplace add vshuraeff/garden
codex plugin add garden@garden
```

Start a new session so Codex loads the installed skills, hooks, and MCP tools.
Run `/hooks`, inspect the source and command definitions, then trust the current hashes
if they match this repository. Plugin hooks are skipped until trusted.

For Claude Code:

```sh
claude plugin marketplace add vshuraeff/garden
claude plugin install garden@garden
```

Use `/reload-plugins` when installing or updating from an existing Claude Code session.

## Test a local clone

Run the marketplace commands from the repository root.

```sh
codex plugin marketplace add .
codex plugin add garden@garden
```

```sh
claude plugin marketplace add .
claude plugin install garden@garden
```

Codex installs a cached copy rather than loading the marketplace source in place. After
changing the plugin, bump its shared version, reinstall it, and start a new session:

```sh
uv run --no-project plugins/garden/tools/plugin_version.py bump patch
```

Use `minor` for backward-compatible features or `major` for breaking changes. Before
`1.0.0`, incompatible (breaking) plugin changes may ship as `minor` instead; `patch`
stays for backward-compatible fixes and internal changes. The command updates the Codex
and Claude manifests together, and pull-request CI rejects plugin changes without an
increased version. Claude Code reloads an updated development plugin with
`/reload-plugins`.

## Activate project instructions

The installed hooks and MCP tools need no project copies. Invoke `garden:start` only
when the repository should also carry GARDEN instructions:

- Claude Code receives `.claude/rules/garden.md`.
- Codex receives a marked block in project-root `AGENTS.md` and the
  `.codex/agents/garden-reviewer.toml` project agent.

Invoke `garden:stop` to remove those copies. It does not uninstall the plugin and does
not remove `naming-registry.txt`, `CONTEXT.md`, contracts, or retrofit records.

## Verify loaded components

In Codex, use `/plugins` to inspect the installed package and `/hooks` for lifecycle
hooks. Ask Codex to list available GARDEN skills and tools in a new session; the MCP
server should expose `garden_inspect_project` and `garden_check_file`.

In Claude Code, use `/plugin` for package state, `/mcp` for the `garden` server, and
`/agents` for `garden-reviewer`. In Codex, run `garden:start` once for the repository,
start a new session, then use `/agent` to inspect reviewer threads.

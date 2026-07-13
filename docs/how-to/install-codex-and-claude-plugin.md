# Install the GARDEN plugin in Codex or Claude Code

The repository publishes one `garden` package through two marketplace manifests. Use
the command for the harness where the plugin should be available. Installing it in both
does not duplicate the source package.

## Install from GitHub

For Codex CLI:

```sh
codex plugin marketplace add vshuraeff/garden
codex plugin add garden@garden
```

Start a new session so Codex loads the installed skills, subagent, hooks, and MCP tools.
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
changing the plugin, update its Codex manifest cachebuster or version, reinstall it,
and start a new session. Claude Code reloads an updated development plugin with
`/reload-plugins`.

## Activate project instructions

The installed hooks and MCP tools need no project copies. Invoke `garden:start` only
when the repository should also carry GARDEN instructions:

- Claude Code receives `.claude/rules/garden.md`.
- Codex receives a marked block in the project-root `AGENTS.md`.

Invoke `garden:stop` to remove those copies. It does not uninstall the plugin and does
not remove `naming-registry.txt`, `CONTEXT.md`, contracts, or retrofit records.

## Verify loaded components

In Codex, use `/plugins` to inspect the installed package and `/hooks` for lifecycle
hooks. Ask Codex to list available GARDEN skills and tools in a new session; the MCP
server should expose `garden_inspect_project` and `garden_check_file`.

In Claude Code, use `/plugin` for package state, `/mcp` for the `garden` server, and
`/agents` for `garden-reviewer`.

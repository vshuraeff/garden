# Security

## What executes on the user's machine

The Claude Code package registers two hooks in
[`plugins/garden/hooks/hooks.json`](plugins/garden/hooks/hooks.json).
`garden-check.sh` runs after `Write` or `Edit`; `garden-prompt.sh` runs on
`UserPromptSubmit`. Each is a thin shell wrapper: it resolves
`PLUGIN_ROOT` or `CLAUDE_PLUGIN_ROOT`, checks for `uv`, and `exec`s
`uv run --no-project` with one Python entry point (`garden_hook.py` or
`garden_prompt_hook.py`). The wrappers contain no other plugin logic.

The hooks fail open with status 0 when infrastructure or their bounded input is
unavailable: a missing plugin root or `uv`, malformed or oversized input, an
inactive project, or an inaccessible file. They return status 2 only for a
deterministic, evidence-backed rule violation. The detailed behavior contract
is in [`plugins/garden/tools/CONTRACT.md`](plugins/garden/tools/CONTRACT.md).

`garden_mcp.py` is a dependency-free, stdio, newline-delimited JSON-RPC server.
It exposes exactly two read-only tools: `garden_inspect_project` and
`garden_check_file`. It accepts workspace roots only through the MCP client's
`roots/list` response, records at most 32 roots, and rejects a path outside a
registered root or one that resolves outside it through `..` or a symlink.
Messages are capped at 1 MiB. `urllib.parse` is used only to parse and unquote
the client's `file://` root URIs; it is not `urllib.request`.

## Confinement

The bounded walks described in
[`plugins/garden/tools/CONTRACT.md`](plugins/garden/tools/CONTRACT.md) stop at
depth 20, 10,000 entries, or two seconds per walk. Individual file reads stop
after 1 MiB. Walks prune dot-directories, `node_modules`, `vendor`, `build`,
`dist`, `target`, and symlinked directories.

For hooks, the checked path must resolve inside the active project root selected
from the hook event's `cwd`. For MCP calls, it must resolve inside a
client-registered root. Symlink escapes and unregistered roots are rejected or
ignored under that contract.

## Supply chain

The Python runtime tools use the standard library and local plugin modules. The
hooks run them with `uv run --no-project`, so runtime does not resolve a project
manifest, install dependencies, or fetch third-party packages.

`plugins/garden/tools/plugin_version.py` is separate maintainer tooling, not a
hook or MCP runtime entry point. When a maintainer runs
`plugin_version.py bump`, it uses `subprocess` to run `git` for version
bookkeeping and synchronizes the SemVer in the Codex and Claude plugin
manifests.

## Defensive properties validated by `test_garden_security.py`

[`plugins/garden/tools/test_garden_security.py`](plugins/garden/tools/test_garden_security.py)
exercises symlink-escape rejection for capability directories and a TOCTOU
file swap that degrades to a report rather than crashing or relying on stale
state. It also bounds pathological glob matching, handles malformed UTF-8 with
replacement rather than raising, and verifies interrupted atomic writes using a
temporary file, `fsync`, and `os.replace`.

GARDEN v1 is POSIX-only; Windows is unsupported. The supported-platform matrix
and the reason Windows path semantics are outside the configuration model are
documented in [the platform support reference](docs/reference/platform-support.md).

## What the plugin does not do

The tools contract states that inspection does not modify project source files.
The separate installer manages only provenance-marked rule files, `AGENTS.md`
blocks, and the Codex reviewer agent; its ownership and refusal rules are in
[`plugins/garden/tools/CONTRACT.md`](plugins/garden/tools/CONTRACT.md).

Before this document was written, this scan was run against every Python file in
the tools directory:

```sh
grep -rn -E "subprocess|eval\\(|exec\\(|os\\.system|socket\\.|urllib\\.request" plugins/garden/tools/*.py
```

Its `subprocess` matches are limited to `plugin_version.py` and `test_*.py`.
The latter are test infrastructure that starts the CLI, hook, or MCP process
under test; they are not hook or MCP runtime code processing user data. The
scan found no `eval(`, `exec(`, `os.system`, `socket.`, or `urllib.request`
occurrences. Accordingly, the tools make no outbound network calls, and the
hook and MCP runtime path has no arbitrary or dynamically constructed code
execution through those APIs. Advisory hook output includes only fixed rule
identifiers and counts, not absolute repository paths or project names, as
specified by the tools contract.

## Reporting a Vulnerability

Report vulnerabilities through this repository's GitHub Security tab using
**Report a vulnerability**, rather than a public issue. This documentation and
tooling plugin has no hosted service. Relevant reports are therefore most
likely to involve a path or symlink escape, a confinement bypass, hook
fail-open or fail-closed behavior, or a code-execution vector in the hook or
MCP runtime path.

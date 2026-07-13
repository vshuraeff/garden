Version: 1.0.0

# GARDEN deterministic tools contract

## Scope

The tools inspect local GARDEN project structure. They do not modify source files. The
project installer modifies only provenance-marked Claude rules, Codex `AGENTS.md`
content, and the Codex reviewer agent.

## Activation and confinement

A project is active when its canonical root contains `naming-registry.txt`. Hook paths
must resolve inside the active root selected from the hook event `cwd`. MCP paths must
resolve inside a `file://` root returned by the client through `roots/list`. Symlink
escapes and unregistered roots are rejected or ignored.

## Checks

- `CONTEXT.md` may contain at most 200 lines.
- The first non-empty `CONTRACT.md` line must match
  `Version: MAJOR.MINOR.PATCH`.
- Missing capability contracts and colocated tests are advisory findings.
- File reads stop after 1 MiB. Project walks prune dot directories,
  `node_modules`, `vendor`, `build`, `dist`, `target`, and symlinked directories; they
  stop at depth 20, 10,000 entries, or two seconds per bounded walk.

## Hook behavior

Hooks accept one JSON object on standard input, capped at 1 MiB. Malformed input,
unsupported event shapes, inaccessible files, inactive projects, and unavailable `uv`
fail open with exit status 0. Deterministic violations exit 2. Advisory
`additionalContext` contains only fixed rule identifiers and counts, never repository
paths or names.

## MCP behavior

The newline-delimited stdio server implements `initialize`, `ping`, `tools/list`,
`tools/call`, and the client `roots/list` exchange. Messages are capped at 1 MiB.
Malformed JSON receives JSON-RPC `-32700`; invalid requests receive `-32600`; unknown
methods receive `-32601`.

`garden_inspect_project` accepts one registered `root` and returns an active flag,
bounded findings, and error/advisory counts. `garden_check_file` accepts a registered
`root` plus a confined absolute or root-relative `path` and returns findings.

## Project installer behavior

The installer holds a per-project process lock, then writes through a temporary file,
`fsync`, and `os.replace`. Managed
files and `AGENTS.md` blocks contain a versioned SHA-256 ownership marker. Unmanaged,
malformed, duplicate, nested, or edited content is refused. `--force` may replace or
remove edited owned content but never unmanaged content.

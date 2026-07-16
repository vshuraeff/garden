# GARDEN repository context

GARDEN is a methodology and installable plugin for Claude Code and Codex. The two
packages are `plugins/garden/.claude-plugin/plugin.json` and
`plugins/garden/.codex-plugin/plugin.json`.

## Directory map

- `docs/` contains human-facing tutorials, how-to guides, reference material,
  explanations, evidence, and development documentation.
- `plugins/garden/tools/` contains deterministic Python tools and colocated
  `test_*.py` modules.
- `plugins/garden/skills/` contains skill definitions.
- `plugins/garden/hooks/` and `plugins/garden/assets/` contain shell adapters
  for hook and prompt integration.
- `plugins/garden/agents/` is the mapped `policy-agents` capability containing
  the reviewer subagent definitions.
- `plugins/garden/references/` contains generated plugin reference copies.

`docs/reference/principles.md`, `docs/reference/checklist.md`, and
`docs/reference/glossary.md` are hand-authored canonical sources.
`plugins/garden/tools/sync_references.py` renders their plugin copies under
`plugins/garden/references/`; run
`uv run --no-project plugins/garden/tools/sync_references.py --check` to check
for drift. CI checks the same rendered reference pairs through
`plugins/garden/tools/validate_package.py`.

## Activation and release

This root `.garden.toml` activates the repository. Inspect its effective
configuration with `uv run --no-project plugins/garden/tools/garden_cli.py config show .`.

Release changes use `uv run --no-project plugins/garden/tools/plugin_version.py bump <patch|minor|major>`,
which updates both plugin manifests together. Before `1.0.0`, breaking plugin
changes may use a MINOR bump; PATCH covers backward-compatible fixes and
internal changes.

## CI and confinement

The plugin workflow runs these commands in order:

- `uv run --no-project -m unittest discover -s plugins/garden/tools -p "test_*.py" -v`
- `uv run --no-project plugins/garden/tools/validate_package.py`
- `uv run --no-project plugins/garden/tools/validate_evidence.py`
- `uv run --no-project plugins/garden/tools/validate_docs.py`
- `uv run --no-project plugins/garden/tools/garden_cli.py config validate .`
- `uv run --no-project plugins/garden/tools/garden_cli.py inspect --strict .`
- `uv run --no-project plugins/garden/tools/garden_cli.py inspect --strict . >
  ${{ runner.temp }}/garden-report.json`, then
  `uv run --no-project plugins/garden/tools/validate_report.py
  ${{ runner.temp }}/garden-report.json`
- `uv run --no-project plugins/garden/tools/plugin_version.py check --base ...`
  on pull requests
- `uvx ruff check plugins/garden/tools && uvx ruff format --check plugins/garden/tools`
- `bash -n plugins/garden/hooks/garden-check.sh plugins/garden/assets/garden-prompt.sh`

`plugins/garden/tools/CONTRACT.md` is authoritative for tool activation and
confinement, bounded scan limits, and hook/MCP behavior. Read it before changing
the deterministic tools or adapters.

CI is defined under `.github/workflows/`; dot-directories are intentionally not
GARDEN capabilities because the scanner excludes them by design.

## Pointers and ownership

- `plugins/garden/tools/CONTRACT.md` defines the deterministic tools contract.
- `docs/evidence/evidence-registry.md` records evidence and citations.
- `.garden.toml` declares this repository's capability boundaries and exceptions.

The repository undergoes deterministic structural inspection under its own
rules. `garden-maintainers` owns the capability boundaries and exceptions in
`.garden.toml`.

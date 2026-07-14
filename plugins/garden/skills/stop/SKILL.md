---
name: stop
description: "Remove project-scoped GARDEN rules and reviewer configuration previously installed by garden:start. Use when asked to remove GARDEN project rules, disable project instructions, or via /garden:stop."
---

# Stop GARDEN project tooling

Remove only surfaces carrying valid provenance from `garden:start`.

1. Select the harnesses.

   Ask whether to remove Claude Code, Codex, or both project surfaces. Report which managed paths currently exist.

2. Run the deterministic remover.

   Invoke `uv run --no-project <plugin-root>/tools/garden_project.py remove --root <project-root> --harness <claude|codex|both>`. Do not manually edit the target files.

   The remover deletes only an owned `.claude/rules/garden.md`, an owned `.codex/agents/garden-reviewer.toml`, and the exact digest-marked GARDEN block in `AGENTS.md`. It preserves all surrounding `AGENTS.md` content and leaves unmanaged files untouched.

3. Handle edited managed content.

   If the remover reports an edited owned file or block, show the difference and ask before rerunning with `--force`. Never use `--force` on an unmanaged file or malformed/duplicate marker set.

4. Preserve GARDEN project artifacts.

   Never modify `.garden.toml`, its declared capability maps or future marker files, `naming-registry.txt`, `CONTEXT.md`, any `CONTRACT.md`, slice directories, or `retrofit-log.md`. Do not edit plugin-manager state, MCP configuration, hook trust, or user-level configuration.

5. Report every removal.

   List removed files and blocks. Explain that uninstalling or disabling the plugin is a separate plugin-manager action.

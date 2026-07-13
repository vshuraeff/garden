---
name: stop
description: "Remove project-scoped GARDEN instructions installed by garden:start without uninstalling the plugin. Use when asked to remove GARDEN rules, disable project GARDEN instructions, or via /garden:stop."
---

# Stop GARDEN project tooling

Remove only project instruction copies installed by `garden:start`.

1. Inspect both supported locations.

   Check `.claude/rules/garden.md` and the project-root `AGENTS.md` block between `<!-- garden:start -->` and `<!-- garden:stop -->`. Report which surfaces exist before changing them.

2. Confirm edited content.

   Ask before deleting `.claude/rules/garden.md`, because the user may have edited the copy. Ask before removing the managed `AGENTS.md` block when its contents differ from the plugin's current `assets/garden-rules.md`.

3. Remove only managed content.

   Delete `.claude/rules/garden.md` when confirmed. Remove only the marked GARDEN block from `AGENTS.md`, leaving all other project instructions byte-for-byte intact. Delete `AGENTS.md` only when it becomes empty after removing the block.

4. Preserve GARDEN project artifacts.

   Never modify `naming-registry.txt`, `CONTEXT.md`, any `CONTRACT.md`, slice directory, or `retrofit-log.md`. Do not edit plugin-manager state, MCP configuration, hook trust, or user-level configuration.

5. Report every removal.

   List the removed files and managed blocks. Explain that uninstalling or disabling the plugin itself is a separate plugin-manager action.

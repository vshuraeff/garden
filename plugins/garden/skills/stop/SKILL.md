---
name: stop
description: "Uninstall GARDEN project tooling previously installed by garden:start: remove the prompt-routing hook and/or project rules file. Use when asked to remove garden hooks, disable garden, \"убери garden-хуки\", \"отключи garden\", or via /garden:stop."
---

# Stop GARDEN project tooling

Remove only routing and fallback tooling installed by `garden:start`.

1. Remove the prompt-routing hook without disturbing other settings.

   Action: If `.claude/settings.json` exists and contains valid JSON, surgically remove only the `UserPromptSubmit` command-hook entry that runs `"$CLAUDE_PROJECT_DIR/.claude/hooks/garden-prompt.sh"`. Leave every other hook entry and top-level key intact. If an enclosing `UserPromptSubmit` item becomes empty, remove that item. If the `UserPromptSubmit` array becomes empty, remove that key. Keep `hooks` when it still has any other event types; otherwise remove the now-empty `hooks` object. Do not replace the settings file wholesale. Delete `.claude/hooks/garden-prompt.sh` if it is present.

   Acceptance signal: The garden command-hook entry and hook file are gone, while unrelated settings and hooks are unchanged.

2. Confirm rules-file deletion.

   Action: Use `AskUserQuestion` to ask for confirmation before deleting `.claude/rules/garden.md`, because the user may have edited it. Delete it only after confirmation.

   Acceptance signal: The rules file remains unless the user explicitly confirms deletion.

3. Preserve the project's GARDEN content.

   Action: Never modify `naming-registry.txt`, any `CONTEXT.md`, any `CONTRACT.md`, slice directory, or `retrofit-log.md`. This skill removes only routing and fallback tooling installed by `garden:start`.

   Acceptance signal: Project GARDEN artifacts remain untouched.

4. Report the removal.

   Action: List exactly the removed file paths and JSON entries.

   Acceptance signal: The user can account for every removed item.

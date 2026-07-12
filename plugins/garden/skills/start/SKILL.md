---
name: start
description: "Configure and install GARDEN tooling in the current project: set up the garden prompt-routing hook and project rules file for deterministic garden:* skill routing. Use when asked to set up garden in a project, enable garden hooks, \"настрой garden в проекте\", \"включи garden-хуки\", or via /garden:start."
---

# Start GARDEN project tooling

Complete the steps in order. Install only the components the user selects.

1. Verify whether the project is, or will become, a GARDEN project.

   Action: Check the project root for `naming-registry.txt`. If it is absent, ask whether to run `garden:bootstrap` for a new project, `garden:retrofit` for an existing codebase, or to continue installing tooling for a project that will adopt GARDEN shortly.

   Acceptance signal: The user has selected an adoption path or explicitly asked to continue without the registry.

2. Select the components.

   Action: Use `AskUserQuestion` with `multiSelect` enabled. Offer `prompt-routing hook` and `project rules file`; require at least one selection.

   Acceptance signal: The selected components are explicit.

3. Install the prompt-routing hook when selected.

   Action: Create `.claude/hooks/` if needed. Copy `${CLAUDE_PLUGIN_ROOT}/assets/garden-prompt.sh` to `.claude/hooks/garden-prompt.sh` in the target project and run `chmod +x` on the copied file. Read the project `.claude/settings.json`, or create it as `{}` when it is absent. If the existing file is invalid JSON, stop and ask the user to repair it rather than replacing it. Merge a `hooks.UserPromptSubmit` command-hook entry that runs `"$CLAUDE_PROJECT_DIR/.claude/hooks/garden-prompt.sh"`. Append it to an existing `UserPromptSubmit` array; do not replace other hook entries, hooks, or top-level settings.

   Acceptance signal: `.claude/hooks/garden-prompt.sh` is executable and `.claude/settings.json` contains the added project-scoped `UserPromptSubmit` command hook without unrelated changes.

4. Install the project rules file when selected.

   Action: Create `.claude/rules/` if needed. Copy `${CLAUDE_PLUGIN_ROOT}/assets/garden-rules.md` to `.claude/rules/garden.md` in the target project.

   Acceptance signal: `.claude/rules/garden.md` is present.

5. Report the installed components.

   Action: List exactly the installed file paths and state that `garden:stop` undoes the installed routing tooling.

   Acceptance signal: The user can identify every installed file and the uninstall skill.

6. Explain the routing and fallback behavior.

   Action: Explain briefly that trigger-rate measurements show weak models consult skills only about half the time regardless of description wording, so GARDEN projects use deterministic prompt routing under principle D: deterministic verification beats prose enforcement. State that both components are plain copies, so the project stays self-contained if the garden plugin is removed later.

   Acceptance signal: The user understands why the hook and copied rules file exist.

7. Keep settings project-scoped.

   Action: Never edit `.claude/settings.local.json` or any user-level settings file. This skill only touches the target project's `.claude/settings.json`.

   Acceptance signal: No local or user-level settings file is changed.

---
name: start
description: "Install project-scoped GARDEN instructions for Codex, Claude Code, or both. Use when asked to set up GARDEN in a project, enable GARDEN rules, configure both coding harnesses, or via /garden:start."
---

# Start GARDEN project tooling

The installed plugin already provides skills, the `garden-reviewer` subagent, MCP inspection tools, and `PostToolUse` plus `UserPromptSubmit` hooks. This skill adds project-scoped instruction copies so the rules remain visible even when a session does not trigger a skill.

1. Verify the adoption path.

   Check the project root for `naming-registry.txt`. If it is absent, ask whether to run `garden:bootstrap` for a new project, `garden:retrofit` for an existing codebase, or continue with rules installation for a project that will adopt GARDEN shortly.

2. Select the target harnesses.

   Ask whether to install instructions for Claude Code, Codex, or both. Use the current harness as the default. Do not assume that both are installed merely because this plugin supports both.

3. Install Claude Code rules when selected.

   Create `.claude/rules/` if needed and copy the plugin's `assets/garden-rules.md` to `.claude/rules/garden.md`. If the destination exists and differs, show the difference and ask before replacing it.

4. Install Codex instructions when selected.

   Read the plugin's `assets/garden-rules.md`. Add its content to the project-root `AGENTS.md` between these exact markers:

   ```text
   <!-- garden:start -->
   <!-- garden:stop -->
   ```

   Preserve every line outside the managed block. If `AGENTS.md` does not exist, create it with only the managed block. If a managed block already exists, replace only that block after showing any difference. Do not create `.codex/rules/*.rules`: Codex rules files control sandbox command approvals, while GARDEN rules are project instructions.

5. Report the installed surfaces.

   List each changed path and the selected harness. State that `garden:stop` removes only the project instruction copies. Explain that plugin hooks remain controlled by the plugin manager; Codex users review and trust their current hash through `/hooks`.

Do not edit user-level Claude or Codex configuration. Do not copy the plugin's MCP configuration or subagent files into the project; installed plugins provide those components directly.

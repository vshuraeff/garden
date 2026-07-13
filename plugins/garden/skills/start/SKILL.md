---
name: start
description: "Install project-scoped GARDEN rules and reviewer configuration for Codex, Claude Code, or both. Use when asked to set up GARDEN in a project, enable GARDEN rules, configure both coding harnesses, or via /garden:start."
---

# Start GARDEN project tooling

The installed plugin already provides skills, MCP inspection tools, and lifecycle hooks. This skill adds provenance-marked project instructions and the Codex reviewer agent through the plugin's atomic installer.

1. Verify the adoption path.

   Check the project root for `naming-registry.txt`. If it is absent, ask whether to run `garden:bootstrap`, run `garden:retrofit`, or continue because adoption will follow shortly.

2. Select the harnesses.

   Ask whether to install for Claude Code, Codex, or both. Use the current harness as the default. Do not infer that both are installed.

3. Run the deterministic installer.

   Invoke `uv run --no-project <plugin-root>/tools/garden_project.py install --root <project-root> --harness <claude|codex|both>`. Do not manually edit the target files.

   The installer creates only these managed surfaces:

   - Claude Code: `.claude/rules/garden.md`.
   - Codex: a digest-marked block in root `AGENTS.md` and `.codex/agents/garden-reviewer.toml`.

   It refuses malformed or duplicate markers and refuses files it does not own. If it reports that owned content was edited, show the difference and ask before rerunning with `--force`. `--force` must never replace an unmanaged file.

4. Report exact paths.

   List every installed surface and its harness. State that `garden:stop` removes only content carrying valid `garden:start` provenance. Codex users must start a new session to load the new project agent.

5. Explain hook trust.

   Plugin hooks remain controlled by the plugin manager. Codex users review and trust their current hash through `/hooks`; project installation does not modify hook trust or user-level configuration.

Do not edit user-level Claude or Codex configuration. Do not copy MCP configuration into the project.

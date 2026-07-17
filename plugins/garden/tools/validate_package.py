#!/usr/bin/env -S uv run --no-project
"""Repository-local deterministic validation for both plugin package surfaces."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

from sync_references import REFERENCE_PAIRS, render
from validate_docs import markdown_links


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PLUGIN_ROOT.parent.parent


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def plugin_markdown_files() -> list[Path]:
    roots = (
        PLUGIN_ROOT / "references",
        PLUGIN_ROOT / "skills",
        PLUGIN_ROOT / "assets",
        PLUGIN_ROOT / "agents",
    )
    paths = {
        path
        for root in roots
        if root.exists()
        for path in root.rglob("*.md")
        if path.is_file()
    }
    for path in (PLUGIN_ROOT / "README.md", PLUGIN_ROOT / "tools" / "README.md"):
        if path.is_file():
            paths.add(path)
    return sorted(paths)


def validate_packaged_links() -> None:
    for path in plugin_markdown_files():
        content = path.read_text(encoding="utf-8")
        for _, raw_target in markdown_links(content):
            target = raw_target.strip()
            if target.lower().startswith(("http://", "https://", "mailto:")) or (
                target.startswith(("#", "/"))
            ):
                continue
            target_path = target.partition("#")[0].split("?", maxsplit=1)[0]
            if not target_path:
                continue
            resolved = (path.parent / target_path).resolve()
            source = path.relative_to(REPOSITORY_ROOT).as_posix()
            require(
                resolved.is_relative_to(PLUGIN_ROOT),
                "packaged link self-containment violation: "
                f"{source} links to {raw_target} outside plugins/garden",
            )
            require(
                resolved.is_file(),
                "packaged link self-containment violation: "
                f"{source} links to missing target {raw_target}",
            )


def validate() -> None:
    claude = load_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")
    codex = load_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    require(isinstance(claude, dict), "Claude manifest must be an object")
    require(isinstance(codex, dict), "Codex manifest must be an object")
    require(
        claude.get("name") == codex.get("name") == "garden", "manifest names differ"
    )
    require(claude.get("version") == codex.get("version"), "manifest versions differ")

    for field in ("name", "version", "description", "author"):
        require(bool(codex.get(field)), f"Codex manifest misses {field}")
    for field in (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
    ):
        require(
            bool(codex.get("interface", {}).get(field)),
            f"Codex interface misses {field}",
        )
    require(codex.get("skills") == "./skills/", "unexpected Codex skills path")
    require(codex.get("mcpServers") == "./.mcp.json", "unexpected Codex MCP path")

    mcp = load_json(PLUGIN_ROOT / ".mcp.json")
    require(
        isinstance(mcp, dict) and set(mcp) == {"mcpServers"},
        ".mcp.json must contain only mcpServers",
    )
    require("garden" in mcp["mcpServers"], "garden MCP server is missing")
    require(
        "uv run --no-project" in json.dumps(mcp),
        "MCP server must use the uv runtime",
    )

    hooks = load_json(PLUGIN_ROOT / "hooks" / "hooks.json")
    require(
        isinstance(hooks, dict) and isinstance(hooks.get("hooks"), dict),
        "hooks are invalid",
    )
    require("PostToolUse" in hooks["hooks"], "PostToolUse hook is missing")
    require("UserPromptSubmit" in hooks["hooks"], "UserPromptSubmit hook is missing")

    marketplace = load_json(
        REPOSITORY_ROOT / ".agents" / "plugins" / "marketplace.json"
    )
    require(marketplace.get("name") == "garden", "unexpected Codex marketplace name")
    entry = marketplace.get("plugins", [None])[0]
    require(
        isinstance(entry, dict) and entry.get("name") == "garden",
        "marketplace entry is missing",
    )
    require(
        entry.get("source", {}).get("path") == "./plugins/garden",
        "marketplace path is invalid",
    )

    agent = tomllib.loads(
        (PLUGIN_ROOT / "agents" / "garden-reviewer.toml").read_text(encoding="utf-8")
    )
    for field in ("name", "description", "developer_instructions"):
        require(bool(agent.get(field)), f"Codex agent misses {field}")

    executables = (
        PLUGIN_ROOT / "bin" / "garden",
        PLUGIN_ROOT / "hooks" / "garden-check.sh",
        PLUGIN_ROOT / "assets" / "garden-prompt.sh",
        PLUGIN_ROOT / "tools" / "garden_cli.py",
        PLUGIN_ROOT / "tools" / "garden_hook.py",
        PLUGIN_ROOT / "tools" / "garden_mcp.py",
        PLUGIN_ROOT / "tools" / "garden_project.py",
        PLUGIN_ROOT / "tools" / "garden_prompt_hook.py",
        PLUGIN_ROOT / "tools" / "plugin_version.py",
        PLUGIN_ROOT / "tools" / "validate_package.py",
    )
    for executable in executables:
        require(executable.stat().st_mode & 0o111 != 0, f"not executable: {executable}")

    for source, copy in REFERENCE_PAIRS.items():
        copy_content = copy.read_bytes().decode("utf-8")
        require(copy_content == render(source), f"reference drift: {copy}")

    validate_packaged_links()


def main() -> int:
    try:
        validate()
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
    ) as error:
        print(f"package validation failed: {error}", file=sys.stderr)
        return 1
    print("package validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

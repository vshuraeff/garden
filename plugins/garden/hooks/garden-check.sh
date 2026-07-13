#!/usr/bin/env bash

plugin_root=${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}
[ -n "$plugin_root" ] || exit 0
command -v uv >/dev/null 2>&1 || exit 0

exec uv run --no-project "$plugin_root/tools/garden_hook.py"

#!/usr/bin/env bash

plugin_root=${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}
[ -n "$plugin_root" ] || exit 0

exec python3 "$plugin_root/tools/garden_hook.py"

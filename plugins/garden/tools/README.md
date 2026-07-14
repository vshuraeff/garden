# GARDEN tool implementation

`garden_core.py` owns bounded project discovery and checks. `garden_hook.py` and
`garden_prompt_hook.py` adapt lifecycle JSON without changing policy. `garden_mcp.py`
exposes read-only tools after MCP root registration. `garden_project.py` owns atomic
project instruction installation and removal.

The shell-facing entry point is `../bin/garden`. Run the colocated tests with:

```sh
uv run --no-project -m unittest discover -s plugins/garden/tools -p "test_*.py" -v
```

Every installable plugin change requires an explicit SemVer bump. Update both harness
manifests together with:

```sh
uv run --no-project plugins/garden/tools/plugin_version.py bump patch
```

Replace `patch` with `minor` for backward-compatible features or `major` for breaking
changes. Pull-request CI compares the plugin version with the base revision and rejects
plugin changes that do not increase it.

The public behavior and limits are defined in `CONTRACT.md`.

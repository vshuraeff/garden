# GARDEN tool implementation

`garden_core.py` owns bounded project discovery and checks. `garden_hook.py` and
`garden_prompt_hook.py` adapt lifecycle JSON without changing policy. `garden_mcp.py`
exposes read-only tools after MCP root registration. `garden_project.py` owns atomic
project instruction installation and removal.

The shell-facing entry point is `../bin/garden`. Run the colocated tests with:

```sh
uv run --no-project -m unittest plugins/garden/tools/test_garden_tools.py -v
```

The public behavior and limits are defined in `CONTRACT.md`.

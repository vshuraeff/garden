# Toy shop fixture

This stdlib-only project is the fixed source fixture for agent benchmark v2. `shop.checkout` and the JSON emitted by `cli.main` are public contracts. Capability code lives under `capabilities/`; repository-level composition belongs in `shop.py`.

The checked-in test suite is green. T1 is the only task that starts with a failing test: the benchmark runner injects `tests/test_t1_regression.py` into T1 workdirs before their baseline commit. T2 and T3 receive the checked-in clean baseline. Prompt and verifier directories are benchmark metadata and are not copied into agent workdirs.

Run the clean suite from this directory with:

```sh
uv run --no-project -m unittest discover -s tests -p 'test_*.py' -v
```

Read `BOUNDARIES.md` before changing capability imports. Each capability's `CONTEXT.md` defines its public module and forbidden dependencies.


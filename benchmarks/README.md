# GARDEN Benchmark v1

Benchmark v1 measures deterministic GARDEN plugin behavior against checked-in
synthetic corpora. It performs no LLM or agent runs.

The `corpus/` directory contains benchmark inputs and independent labels,
`schemas/` defines result contracts, `lib/` contains shared deterministic
helpers, and the root TOML and JSON files pin the protocol, toolchain, gates,
and rule-family mapping. Result-producing scripts emit machine-readable data
for later validation and reporting.

Run the complete benchmark with:

```sh
uv run --no-project benchmarks/run.py
```

Run the configured-detection suite alone with:

```sh
uv run --no-project benchmarks/run_detection.py
```

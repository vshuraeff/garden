# GARDEN plugin baseline

Baseline commit: `9f009ffcd2b46e0b30b34611da3466751335b35d` (branch `master`).

## Environment

- `uv --version`: `uv 0.11.28 (Homebrew 2026-07-07 x86_64-apple-darwin)`
- `uv run --no-project python --version`: `Python 3.14.0`

## Command results

| Command | Result | Wall time |
|---|---|---|
| `uv run --no-project -m unittest plugins/garden/tools/test_garden_tools.py -v` | `Ran 31 tests in 1.337s` — `OK` | ~1.5s |
| `uv run --no-project plugins/garden/tools/validate_package.py` | `package validation passed` | ~0.05s |
| `uvx ruff check plugins/garden/tools` | `All checks passed!` | ~0.34s |
| `uvx ruff format --check plugins/garden/tools` | `9 files already formatted` | ~0.05s |
| `bash -n plugins/garden/hooks/garden-check.sh` | exit 0, no output | negligible |
| `bash -n plugins/garden/assets/garden-prompt.sh` | exit 0, no output | negligible |

Test suite (31 tests total): `GardenCoreTests` (8), `GardenHookTests` (8), `GardenMcpTests` (4), `GardenProjectTests` (5), `PackageTests` (6), in `plugins/garden/tools/test_garden_tools.py`.

## Deterministic checks (`plugins/garden/tools/garden_core.py`)

Project activation: a directory is an active GARDEN project when a `naming-registry.txt`
file exists in it or an ancestor. `find_project_root` walks up at most
`MAX_ROOT_SEARCH_DEPTH = 31` levels from the resolved start path.

Scan budgets, enforced by `_walk_files` and `_bounded_binary_lines`:

- `MAX_SCAN_SECONDS = 2.0` — wall-clock budget for one directory walk; exceeding it raises
  `ScanLimitExceeded`.
- `MAX_SCAN_ENTRIES = 10_000` — cumulative directories + files visited across the walk.
- `MAX_SCAN_DEPTH = 20` — directories at this depth are not descended into further.
- `MAX_CHECKED_FILE_BYTES = 1_048_576` — per-file read budget for line-oriented checks
  (`CONTEXT.md`, `CONTRACT.md`); reading past it raises `ScanLimitExceeded`.

Directories named `node_modules`, `vendor`, `build`, `dist`, `target`, or starting with
`.`, are skipped during the walk and never descended into. Symlinked directories are
excluded from `dirs` and not followed (`followlinks=False`).

Rules, keyed by `Finding.rule`:

- `N-context-budget` (error) — `CONTEXT.md` at the project root exceeds
  `CONTEXT_LINE_BUDGET = 200` lines. Only checked if the file exists; a missing
  `CONTEXT.md` produces no finding.
- `N-context-scan-limit` (error) — reading `CONTEXT.md` hit `MAX_CHECKED_FILE_BYTES`.
- `R-contract-version` (error) — a capability's `CONTRACT.md` exists but its first
  non-empty line does not match `Version: [0-9]+\.[0-9]+\.[0-9]+` exactly (via
  `re.fullmatch`). A missing `CONTRACT.md` does not trigger this rule; `R-component-contract`
  covers that case instead.
- `R-contract-scan-limit` (error) — reading `CONTRACT.md` hit `MAX_CHECKED_FILE_BYTES`.
- `R-component-contract` (advisory) — a capability directory (the first path component
  under the project root) that contains a checked source file has no `CONTRACT.md`.
- `A-colocated-tests` (advisory) — a capability has no file or directory anywhere in its
  subtree whose lowercased name contains the substring `test` or `spec`. Detection walks
  the whole capability subtree (bounded by the same scan budgets) and caches the result
  per capability.
- `D-project-scan-limit` (error) — `inspect_project`'s directory walk hit a scan budget;
  reported against path `.`.

Source-file filtering (`_is_source_file`), used to decide which files count toward
capability detection and the `A`/`R` rules above:

- Names starting with `.` are excluded.
- Exact names `Dockerfile`, `Makefile`, `LICENSE`, `NOTICE`, `CHANGELOG`, `Gemfile`,
  `Gemfile.lock`, `Pipfile`, `Pipfile.lock`, `Rakefile`, `Procfile` are excluded.
- Suffixes `.md`, `.txt`, `.json`, `.yml`, `.yaml`, `.toml`, `.lock` (case-insensitive)
  are excluded — JSON, YAML, and TOML files never count as source.
- Any path with a component starting with `.` or equal to `node_modules`, `vendor`,
  `build`, `dist`, or `target` is excluded.
- A path needs at least two components (capability directory + file) to be considered;
  files directly at the project root are never attributed to a capability.

`inspect_project` builds its candidate set from `CONTEXT.md`, every `*/CONTRACT.md` one
level down, and the first source file found per top-level capability directory
(`sources.setdefault`, so only one representative file per capability is inspected for
the `R-component-contract` / `A-colocated-tests` advisories). Findings are deduplicated
by `(severity, rule, path, message)`.

## Known limitations

- Capability identity is exactly the first path component under the project root
  (`relative.parts[0]`); there is no configuration for nested or multi-root capability
  layouts.
- Colocated-test detection is a substring match on file/directory names (`"test"` or
  `"spec"` in the lowercased name); it does not parse test framework markers, imports, or
  distinguish fixtures/mocks from actual tests.
- JSON, YAML, and TOML files are excluded from source-file detection entirely, so a
  capability whose only checked content is config-format code has no signal for
  `A-colocated-tests` or `R-component-contract`.
- Missing required files are not detected as such: a missing `CONTEXT.md` produces no
  finding (only an oversized one does), and a missing project-root `naming-registry.txt`
  simply means the project is not active rather than an error.
- `R-contract-version` and `R-contract-scan-limit` only run when a capability's
  `CONTRACT.md` already exists; there is no check enforcing that a capability must
  contain a `CONTRACT.md` (`R-component-contract` is advisory, not an error).
- All scan and file-size budgets are hardcoded module constants; none are configurable
  per project.

# Getting started with GARDEN

In this tutorial, we will build a small link-shortener service with two capabilities:
`shorten` turns a long URL into a short code, and `resolve` turns that code back into
the long URL. We will choose a capability-slice layout for this service, record that
choice in `.garden.toml`, and make the public contract, tests, state, ownership, and
verification paths discoverable.

The capability-slice layout is one valid GARDEN strategy for this example. GARDEN also
supports framework-standard, explicitly mapped, marker-based, and ungrouped layouts;
it does not require vertical slices for every project.

## What you will build

The finished example has a configured `children` capability strategy, a naming
registry scoped to the link-shortener context, a machine-readable capability map, a
published HTTP contract, replacement evidence, tests in a separately mapped tree,
explicit state dependencies, a boundary lint rule, and a maintained context entry
point.

## Step 1 — Initialize the project

Create an empty project directory and let GARDEN write its conservative schema-v1
configuration:

```sh
mkdir link-shortener
garden init link-shortener
cd link-shortener
```

`garden init` writes only `.garden.toml` and prints its path. It does not move files or
create a source layout. We will now replace the detected defaults with choices for this
service.

## Step 2 — Choose Adaptive Capability Locality

For this service, `shorten` and `resolve` are useful ownership and change units. We
will keep their production code under separate children of `src/`, keep shared state
in a declared shared root, and map a separate test tree back to those capabilities.

Create the directories:

```sh
mkdir -p api src/shorten src/resolve src/shared tests/shorten tests/resolve
```

Replace `.garden.toml` with:

```toml
schema_version = 1

[project]
type = "service"
context_files = { any_of = ["CONTEXT.md"] }

[scan]
roots = ["src"]
include = ["**/*.impl"]
exclude = ["**/dist/**"]

[capabilities]
strategy = "children"
roots = ["src"]
depth = 1
shared_roots = ["src/shared"]

[tests]
patterns = ["tests/**"]
association = "test-roots"
test_roots = { "tests/shorten" = "src/shorten", "tests/resolve" = "src/resolve" }

[contracts]
required_for = ["published-api"]
accepted_names = ["openapi.yaml", "replacement-evidence.md"]

[boundaries]
public = ["api"]

[naming]
registry = "link-shortener-naming.txt"
required = true

[documentation]
root_context_required = true
max_context_lines = 120
```

Run the schema and confinement check:

```sh
garden config validate .
```

The command reports `.garden.toml` as valid. Notice that the test files do not need to
be colocated with production code: `tests.test_roots` gives GARDEN a stable path from
each test directory to the capability it verifies. The 120-line context limit is this
project's configured budget, not a universal GARDEN threshold.

## Step 3 — Make relationships graph-resolvable

Graph-resolvable Discoverability requires production relationships to be recoverable
through a stated mechanism. For this example, use a bounded-context naming registry
and a machine-readable capability map.

Create `link-shortener-naming.txt`:

```text
short code: short_code
long URL: long_url
link: link
create link: shorten
resolve link: resolve
```

These names are canonical inside the link-shortener bounded context. If another
context uses different vocabulary, record a translation at that boundary instead of
forcing one repository-wide term.

Create `capabilities.yaml`:

```yaml
capabilities:
  shorten:
    operation: "POST /links"
    code: src/shorten
    state: src/shared/link_store.impl
    tests: tests/shorten
    contract: api/openapi.yaml
    owner: link-service
  resolve:
    operation: "GET /links/{short_code}"
    code: src/resolve
    state: src/shared/link_store.impl
    tests: tests/resolve
    contract: api/openapi.yaml
    owner: link-service
```

The map connects each operation to its code, state, tests, public contract, and owner.
The naming registry is now configured project data; `.garden.toml`, rather than the
registry's mere presence, is the primary GARDEN activation mechanism.

## Step 4 — Define the public boundary before its implementation

The `api/` directory is this service's declared public boundary. Replaceable
Components requires evidence appropriate to that boundary, while Explicit Boundaries
and State requires the input, output, validation, compatibility, state, and ownership
decisions to be visible there. A file named `CONTRACT.md` is not the only accepted
artifact.

Create `api/openapi.yaml` with the two operations:

```yaml
openapi: 3.1.0
info:
  title: Link shortener API
  version: 1.0.0
paths:
  /links:
    post:
      operationId: shorten
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [long_url]
              properties:
                long_url: { type: string, format: uri }
      responses:
        "201":
          description: Link created or returned from existing state
          content:
            application/json:
              schema:
                type: object
                required: [short_code]
                properties:
                  short_code: { type: string, pattern: "^[a-z0-9]{6}$" }
        "400":
          description: Invalid URL with error_code invalid_long_url
  /links/{short_code}:
    get:
      operationId: resolve
      parameters:
        - name: short_code
          in: path
          required: true
          schema: { type: string, pattern: "^[a-z0-9]{6}$" }
      responses:
        "200":
          description: Link resolved
          content:
            application/json:
              schema:
                type: object
                required: [long_url]
                properties:
                  long_url: { type: string, format: uri }
        "404":
          description: Unknown code with error_code unknown_short_code
```

Create `api/replacement-evidence.md`:

```markdown
# Link shortener API replacement evidence

Owner: link-service

- Compatibility: the published HTTP API is a designated versioned boundary and uses
  SemVer. Breaking request or response changes require a new major version.
- Behavior: shortening the same long_url returns the existing short_code; resolving a
  stored short_code returns its long_url.
- Errors: invalid_long_url and unknown_short_code are stable machine-readable codes.
- Data ownership: this tutorial uses process-local state owned by link-service; there
  is no persisted schema.
- Concurrency and ordering: not applicable to this single-process walkthrough. Define
  and test them before using a concurrent or distributed store.
- Migration and rollback: there is no persisted migration. Roll back by restoring the
  previous service build.
- Observability: count requests and stable error codes per operation.
```

Only the published HTTP API carries `version: 1.0.0`. The private `.impl` files below
use Git history and do not receive artificial versions. Schema v1 validates and
resolves the `contracts` and `boundaries` declarations but does not yet enforce their
artifacts during project inspection, so the project's CI must check that the two files
exist and validate the OpenAPI document.

## Step 5 — Start Defense-in-depth Verification with failing tests

The test tree is separate from `src/`, but the `test_roots` mapping in `.garden.toml`
makes the association deterministic. Create `tests/shorten/shorten.test`:

```text
test "shorten returns a six-character short_code":
    store = in_memory_link_store()
    result = shorten("https://example.com/a/long/path", store, fixed_code("a1b2c3"))
    assert result.short_code == "a1b2c3"

test "shorten is idempotent for a repeated long_url":
    store = in_memory_link_store()
    first = shorten("https://example.com/a/long/path", store, fixed_code("a1b2c3"))
    second = shorten("https://example.com/a/long/path", store, fixed_code("z9y8x7"))
    assert first.short_code == second.short_code

test "shorten rejects a malformed long_url":
    assert_error_code("invalid_long_url"):
        shorten("not-a-url", in_memory_link_store(), fixed_code("a1b2c3"))
```

Create `tests/resolve/resolve.test`:

```text
test "resolve returns the stored long_url":
    store = in_memory_link_store({"a1b2c3": "https://example.com/a/long/path"})
    result = resolve("a1b2c3", store)
    assert result.long_url == "https://example.com/a/long/path"

test "resolve reports an unknown short_code":
    assert_error_code("unknown_short_code"):
        resolve("z9y8x7", in_memory_link_store())
```

Run the project's test command now. All five tests fail because the implementation is
absent. That failure is the first executable evidence for the behavior in the public
contract; it is not replaced by an agent's review.

## Step 6 — Implement with explicit state and enforce the capability boundary

Create the shared store and pass it into both capabilities. The pseudocode keeps state
and code generation visible instead of reading hidden ambient dependencies:

```text
# src/shared/link_store.impl

function in_memory_link_store(initial_links = {}):
    return store supporting find_by_long_url, find_by_short_code, and put

# src/shorten/shorten.impl

function shorten(long_url, store, generate_short_code):
    if not is_well_formed_absolute_url(long_url):
        raise error(code = "invalid_long_url", field = "long_url")

    existing = store.find_by_long_url(long_url)
    if existing:
        return { short_code: existing.short_code }

    short_code = generate_short_code()
    store.put(short_code, long_url)
    return { short_code: short_code }

# src/resolve/resolve.impl

function resolve(short_code, store):
    link = store.find_by_short_code(short_code)
    if not link:
        raise error(code = "unknown_short_code", field = "short_code")
    return { long_url: link.long_url }
```

Rerun the tests; all five now pass. Then express this invariant in the native syntax of
the project's linter or dependency checker:

```text
rule "no-cross-capability-internals":
    forbid src/shorten/** importing src/resolve/**
    forbid src/resolve/** importing src/shorten/**
    allow src/shorten/** importing src/shared/link_store.impl
    allow src/resolve/** importing src/shared/link_store.impl
```

Run that rule in CI with the tests and the OpenAPI check. If either capability reaches
into the other's private implementation, the gate fails without depending on a
reviewer to remember the selected layout.

## Step 7 — Add Nearby, Maintained Knowledge

Create `CONTEXT.md` as the maintained entry point selected by `.garden.toml`:

```markdown
# Link shortener context

Owner: link-service
Last reviewed: 2026-07-16
Review trigger: capability ownership, public API, state model, or verification changes

- Effective GARDEN configuration: .garden.toml
- Canonical names for this bounded context: link-shortener-naming.txt
- Capability code, state, tests, contracts, and owners: capabilities.yaml
- Published API and replacement evidence: api/
- Required gates: config validation, tests, dependency lint, and OpenAPI validation
```

This file links to governing artifacts without restating them. The project selected it
as the root entry point and gave it an owner, a review date, a staleness trigger, and a
local line budget.

## Step 8 — Follow the requisite context for an expiry change

Consider a follow-up task: links expire 30 days after creation, and resolving an
expired `short_code` returns `link_expired`.

Start at `CONTEXT.md`, then use `capabilities.yaml` to identify the affected public
contract, shared state, capability code, tests, and owner. Update
`api/openapi.yaml` and `api/replacement-evidence.md` first, add failing tests for the
creation timestamp and expiry result, then change the shared store and the two
capability implementations. Finish by running config validation, all five existing
tests plus the new expiry tests, dependency lint, and OpenAPI validation.

The required files are bounded by this project's declared capability graph and the
risk of this change. GARDEN does not impose a universal path-count rule: the project
uses progressive disclosure so a contributor loads the requisite context without
guessing which code, contract, state, tests, or decisions govern the behavior.

You have now applied all six current principles: Graph-resolvable Discoverability in
the naming and capability maps, Adaptive Capability Locality in the selected service
layout, Replaceable Components in the boundary evidence, Defense-in-depth Verification
in the executable gates, Explicit Boundaries and State in the API and injected store,
and Nearby, Maintained Knowledge in the governed context entry point.

## Where to go next

- [Apply GARDEN to a new project](../how-to/apply-to-new-project.md)
- [Retrofit a legacy codebase](../how-to/retrofit-legacy-codebase.md)
- [Set up verification gates](../how-to/set-up-verification-gates.md)
- [Review code as an agent](../how-to/review-code-as-agent.md)

For the normative levels, stable rule IDs, and allowed exceptions behind this
tutorial, see [the principles reference](../reference/principles.md). For every
`.garden.toml` key used here, see the
[configuration reference](../reference/configuration.md).

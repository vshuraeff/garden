# Getting started with GARDEN

This tutorial builds a tiny link-shortener service from nothing, applying all six
GARDEN principles as you go. It has two capabilities: `shorten` (turn a long URL into a
short code) and `resolve` (turn a short code back into the long URL). Follow the steps
in order; each one produces a concrete file and something you can observe. There are no
optional branches here — if you want task-specific guidance afterward, the how-to guides
linked at the end cover that.

## What you will end with

A directory tree with one vertical slice per capability, a contract file per slice, a
failing-then-passing contract test, a lint rule that enforces a boundary, a short
context file, and a simulated agent task that a fresh agent can complete by reading only
files within one hop of the edit site.

## Step 1 — Start a name registry

Before writing any code, fix the canonical names for the concepts this service will
use. This is Grep-first Discoverability (G) applied first: pick one name per concept so
every later file, test, and error message can reuse it without inventing synonyms.

Create `naming-registry.txt`:

```
short code: short_code
long URL: long_url
link: link
create link: shorten
resolve link: resolve
```

Observe: from now on, no file in this tutorial calls `short_code` a "slug" or "token",
and no file calls `resolve` a "lookup" or "get". One canonical name per concept.

## Step 2 — Scaffold the vertical slices

Atomic Vertical Slices (A) means organizing by capability, not by technical layer.
Create one directory per capability, each holding its own entry point, logic, and
tests — not a shared `controllers/`, `services/`, `models/` split.

```
link-shortener/
  naming-registry.txt
  shorten/
    CONTRACT.md
    shorten.test
    shorten.impl
  resolve/
    CONTRACT.md
    resolve.test
    resolve.impl
```

Observe: `shorten/` and `resolve/` do not import each other's internals. Each is small
enough to read in one sitting, and each will hold its own tests rather than a separate
top-level `tests/` tree.

## Step 3 — Write the contract before the code

Regenerable Components (R) requires a contract precise enough that the component could
be rewritten from scratch against it. Write the contract for `shorten` first, before any
implementation exists.

Create `shorten/CONTRACT.md`:

```
Version: 1.0.0

# contract: shorten

## input
- long_url: string, must be a well-formed absolute url

## output
- short_code: string, 6 lowercase alphanumeric characters, unique among stored links

## behavior
- given a long_url not seen before, shorten creates a new link and returns its
  short_code
- given a long_url already stored, shorten returns the existing short_code
  (idempotent)
- given a malformed long_url, shorten fails with an invalid_long_url error

## errors
- invalid_long_url: long_url is not a well-formed absolute url
```

Observe: this file mentions no implementation detail (no storage engine, no framework).
It is the durable artifact; `shorten.impl` below is expendable against it.

## Step 4 — Write a failing contract test

Deterministic Verification (D) means the contract is checked in executable form before
any implementation exists. Translate the contract into a test that currently fails
because `shorten.impl` does not exist yet.

Create `shorten/shorten.test` (pseudocode):

```
test "shorten returns a 6-character short_code for a new long_url":
    result = shorten("https://example.com/a/long/path")
    assert length(result.short_code) == 6
    assert result.short_code matches "^[a-z0-9]{6}$"

test "shorten is idempotent for a repeated long_url":
    first = shorten("https://example.com/a/long/path")
    second = shorten("https://example.com/a/long/path")
    assert first.short_code == second.short_code

test "shorten rejects a malformed long_url":
    assert_raises(invalid_long_url):
        shorten("not-a-url")
```

Observe: running the test suite now reports three failures with a clear
`shorten is not defined` (or equivalent) error — the gate exists and is red before the
code exists, not after.

## Step 5 — Implement against the contract

Write the smallest implementation that turns the three tests green. Keep it inside
`shorten/shorten.impl`; nothing here reaches into `resolve/`.

```
# shorten/shorten.impl

store = {}  # long_url -> short_code, private to this slice

function shorten(long_url):
    if not is_well_formed_absolute_url(long_url):
        raise invalid_long_url(long_url)

    if long_url in store:
        return { short_code: store[long_url] }

    short_code = generate_short_code()  # 6 lowercase alphanumeric characters
    store[long_url] = short_code
    return { short_code: short_code }
```

Observe: rerunning the test suite turns all three `shorten` tests green. Repeat steps
3–5 for `resolve/` (contract, failing test, implementation) before moving on; the
tutorial omits that repetition here for brevity, but a real pass through GARDEN does
not skip it.

## Step 6 — Add a lint boundary rule

Deterministic Verification (D) treats lint configuration as executable architecture
spec, not convention. Encode the vertical-slice boundary from step 2 as a rule instead
of a comment.

Create `lint-rules.md` (or your linter's native config, expressed the same way):

```
# import boundary rule

rule "no-cross-slice-internals":
    forbid: shorten/* importing anything from resolve/* except resolve/CONTRACT.md
    forbid: resolve/* importing anything from shorten/* except shorten/CONTRACT.md
```

Observe: if a later change makes `resolve.impl` reach directly into `shorten`'s private
`store`, the lint gate fails on that change — the boundary is enforced mechanically, not
by someone remembering to review for it.

## Step 7 — Write the root context file

Navigable Knowledge (N) requires a short, hand-written context file rather than an
autogenerated dump. Keep it under roughly 200 lines and load-bearing only.

Create `link-shortener/CONTEXT.md`:

```
# link-shortener context

- canonical names: see naming-registry.txt
- one vertical slice per capability: shorten/, resolve/
- every slice has a CONTRACT.md; read it before editing that slice's impl
- import boundary: a slice may depend on another slice's CONTRACT.md, never its impl
- tests are colocated with the slice they verify; a green test suite is required
  before any change is considered done
```

Observe: this file states only what is not already obvious from opening the directory
tree — it does not restate the contracts themselves, and it links to
`naming-registry.txt` and each slice's `CONTRACT.md` rather than duplicating their
content.

## Step 8 — A simulated agent task: add expiry

Now simulate handing this codebase to a fresh agent with a one-sentence task: "links
should expire 30 days after creation; resolving an expired short_code should fail."

Follow what that agent needs to read, in hop order:

1. `CONTEXT.md` (root, one hop) — points it at `naming-registry.txt` and the relevant
   slice
   contracts.
2. `shorten/CONTRACT.md` and `resolve/CONTRACT.md` (one hop from `CONTEXT.md`) — the
   agent updates both contracts first: `shorten` now records a creation time, `resolve`
   now checks it and can fail with a new `link_expired` error.
3. `shorten/shorten.test`, `resolve/resolve.test`, `shorten/shorten.impl`,
   `resolve/resolve.impl` (one hop from each contract) — the agent adds a failing test
   per updated contract, then updates each implementation to turn it green.

Observe: the agent never had to open a directory outside `link-shortener/`, never had to
guess a name (the registry already defines `link`, `short_code`, `resolve`), and the
lint boundary rule from step 6 did not need to change, because expiry is internal to
each slice's own contract and implementation. All requisite context for the change —
`CONTEXT.md`, two contracts, two tests, and two implementations — fits in a single agent
context window.

## Where to go next

You have now touched all six principles once: G in the name registry, A in the slice
scaffold, R in the contracts, D in the failing-test-first workflow and the lint rule, E
implicitly in the typed contract inputs/outputs and named `invalid_long_url` /
`link_expired` errors, and N in the context file and hop-distance discipline.

For task-specific guidance beyond this walkthrough, see:

- [Apply GARDEN to a new project](../how-to/apply-to-new-project.md)
- [Retrofit a legacy codebase](../how-to/retrofit-legacy-codebase.md)
- [Set up verification gates](../how-to/set-up-verification-gates.md)
- [Review code as an agent](../how-to/review-code-as-agent.md)

For the authoritative statement of each rule you applied here, see
[the principles reference](../reference/principles.md).

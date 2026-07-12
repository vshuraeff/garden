# GARDEN glossary

Terms below are used with exactly the meaning given here throughout this
documentation set. Each entry links to the principle section in
[principles.md](./principles.md) where the term is normative.

**agent** — An LLM-driven program that reads, writes, and reviews code via
tools. Normative across all six principles; see
[principles.md](./principles.md).

**canonical name** — The single name a concept has across the codebase;
synonyms break grep-first discovery. Normative in
[G — Grep-first Discoverability](./principles.md#g--grep-first-discoverability).

**context file** — The short hand-maintained `CONTEXT.md` file loaded by
agents at session start. Normative in
[N — Navigable Knowledge](./principles.md#n--navigable-knowledge).

**context rot** — Degradation of agent performance as a session grows;
primarily a state-tracking failure rather than a reasoning failure.
Motivates [N — Navigable Knowledge](./principles.md#n--navigable-knowledge).

**context window** — The finite token budget an agent can attend to at
once. Bounds the sizing rules in
[A — Atomic Vertical Slices](./principles.md#a--atomic-vertical-slices).

**deterministic gate** — A check (type check, lint rule, test, or CI job)
that passes or fails identically on every run, independent of any model.
Normative in
[D — Deterministic Verification](./principles.md#d--deterministic-verification).

**hop distance** — The number of link or directory traversals between an
edit site and the knowledge required to edit it safely; the GARDEN target is
at most one hop. Normative in
[N — Navigable Knowledge](./principles.md#n--navigable-knowledge).

**indirection tax** — The extra search-and-read cost every layer of
indirection (deep inheritance, dynamic dispatch, dependency-injection magic)
imposes on an agent; it also raises hallucination risk. Motivates
[G — Grep-first Discoverability](./principles.md#g--grep-first-discoverability)
and the rejections listed in
[R — Regenerable Components](./principles.md#r--regenerable-components).

**magic value** — A literal whose meaning is not discoverable at its use
site. Prohibited under
[E — Explicit Everything](./principles.md#e--explicit-everything).

**managed duplication** — Tolerating duplicate code until a clone-detection
signal in CI justifies extracting an abstraction, instead of abstracting
preemptively. Normative in
[A — Atomic Vertical Slices](./principles.md#a--atomic-vertical-slices).

**one-context task** — A task whose requisite context fits comfortably in a
single agent context window. The sizing target for
[A — Atomic Vertical Slices](./principles.md#a--atomic-vertical-slices).

**premature abstraction** — An abstraction created before at least three
concrete usages exist; it costs agents more than the duplication it removes.
Prohibited under
[A — Atomic Vertical Slices](./principles.md#a--atomic-vertical-slices).

**progressive disclosure** — Layering knowledge so an agent loads a short
summary first and follows links only when needed. Normative in
[N — Navigable Knowledge](./principles.md#n--navigable-knowledge).

**regenerability** — The property that a component can be rewritten from
scratch against its contract without ripple effects. Defines
[R — Regenerable Components](./principles.md#r--regenerable-components).

**requisite context** — The minimum set of files and facts an agent must
load to perform a task correctly. Sizing basis for
[A — Atomic Vertical Slices](./principles.md#a--atomic-vertical-slices) and
[N — Navigable Knowledge](./principles.md#n--navigable-knowledge).

**self-certification** — An agent declaring its own output correct without
a deterministic gate; forbidden under
[D — Deterministic Verification](./principles.md#d--deterministic-verification).

**significant directory** — A directory is significant if it contains a
`CONTRACT.md`, has two or more subdirectories, or contains more than five
source files. Normative in
[N — Navigable Knowledge](./principles.md#n--navigable-knowledge).

**spec drift** — Divergence between a spec or contract and the code that
claims to implement it. Addressed in
[R — Regenerable Components](./principles.md#r--regenerable-components).

**temporal coupling** — A hidden requirement that operations happen in a
particular order, not expressed in types or signatures. Prohibited under
[E — Explicit Everything](./principles.md#e--explicit-everything).

**vertical slice** — A module containing everything one capability needs
(entry point, logic, data access, tests) rather than a horizontal layer.
Defines [A — Atomic Vertical Slices](./principles.md#a--atomic-vertical-slices).

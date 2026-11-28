> **AI agent instructions (organization-wide):** Before working on code, issues, or pull requests, read and follow the [organization `AGENTS.md`](https://github.com/atto-lang/.github/blob/main/AGENTS.md), including its **merge-first stealth-development policy**. Honor any repository-local `AGENTS.md`, explicit holds, and GitHub-enforced rules.

# atto-rx-channels

Reactive streams and observable adapters for AttoLang channels.

## Naming migration and language authority

This repository is maintained at [atto-lang/atto-rx-channels](https://github.com/atto-lang/atto-rx-channels); use `https://github.com/atto-lang/atto-rx-channels.git` for Git remotes and canonical `.atto` source examples. The normative language contract is [atto-spec](https://github.com/atto-lang/atto-spec), with executable guest evidence tracked by [atto-platform-conformance](https://github.com/atto-lang/atto-platform-conformance). Follow current ownership, borrowing, effects, actor, and syntax rules there; do not infer implemented features from a README or unexecuted CI.

## Purpose

Adapters between AttoLang channels and observable/stream-style interfaces.

## API and contract expectations

- Expose general-purpose interfaces that are usable without an Atto commercial account.
- Document data/ownership semantics, error behavior, and supported runtimes.
- Keep protocol and serialization details portable across relevant AttoLang backends.

## Development and testing

Use checked-in implementation and CI for actual commands. Add behavior-focused tests, including negative cases and lifecycle edge cases; distinguish local unit tests from executed multi-backend conformance.

The [bounded guest worker pipeline](docs/worker-pipeline.md) executes on the
explicit Java/Graal pin in `pipeline-compiler.lock`. Its [example](examples/worker_pipeline.atto)
prints `1, 4, 9, 16, 25, 36` on separate lines, then total `91`. The implementation
and lifecycle tests are real `.atto` guest programs. See that document for the
reproduction command, exact evidence boundary and unresolved legacy Rx gates.

## Project status

This describes intended scope, not a verified feature matrix. Consult the source tree and exact-commit CI results for implementation status.

## Ecosystem

- [AttoLang](https://github.com/atto-lang)
- [Language specification](https://github.com/atto-lang/atto-spec)
- [Cross-platform conformance](https://github.com/atto-lang/atto-platform-conformance)

## Repository ownership and contribution routing

**Belongs here:** Adapters between typed AttoLang directional channels and observable/reactive streams, delivery and subscription lifecycle.

**Belongs elsewhere:** Base channels and actor scheduler semantics in compiler/runtime repos; task combinators in atto-rx-tasks; stream operators in atto-rx.

**Security and portability boundary:** Preserve exactly-one-winner select, FIFO per edge, bounded buffers, cancellation rollback and critical-section nonblocking guarantees.

AttoLang is the canonical project name; new source, examples and documentation use `.atto` and the `atto-lang` repository organization. This README defines scope, not feature readiness.

**Acceptance:** name exact source SHA/tree, runtime/toolchain, positive and negative checks and execution receipt before claiming support. Host-only tests and empty CI steps do not prove guest execution.

## Legacy migration and verification gates

The historical predecessor is [ores-truffle-oreslang/rx-oreslang-channels](https://github.com/ores-truffle-oreslang/rx-oreslang-channels), now archived. This repository is maintained at [atto-lang/atto-rx-channels](https://github.com/atto-lang/atto-rx-channels); do not infer an ID-preserving transfer or source parity from naming or imported history. Preserve working legacy `.ores` inputs and package/CLI aliases until their compiler-backed `.atto` replacements and consumers are verified.

Typed reactive/channel adapters, backpressure, cancellation and ownership tests belong here; untrusted actor message internals and transferring closures across isolation boundaries do not. [atto-lang](https://github.com/atto-lang) owns language, portable libraries, compilers, tooling, tests and examples; [atto-co](https://github.com/atto-co) separately governs hosted deployment, tenant infrastructure, identity and billing. Future transfers or carve-outs require separate source/target owner authorization, independent security review and rollback ownership. Inventory exact SHA/tree, numeric ID, history, access, visibility, protections, PRs, releases, packages, consumers, Actions/runners, secrets, applications, webhooks, deploy keys and Pages. Never mirror private source without explicit authorization. Verify identity/history and restored controls after any authorized transfer, then execute exact-head tests before changing consumers. Zero-step jobs are NOT_EXECUTED; host-only checks do not establish compiled guest execution or production readiness.

Historical planning: [coordination issue #26](https://github.com/ores-truffle-oreslang/.github/issues/26) and [migration runbook #25](https://github.com/ores-truffle-oreslang/.github/pull/25).

## Pull/push bounded-flow reference model (TARGET, not guest support)

See [the pull/push reactive-admission contract](docs/PULL_PUSH_CONTRACT_V1.md) and its
[source-free protocol model](src/flow-port-model.mjs). Run the model assertions with
`node --test test/flow-port-model.test.mjs` (Node 20+). These tests **do not**
certify compiled AttoLang, any runtime backend, cross-backend parity, or a
zero-GC allocation profile. All concrete guest APIs remain unverified.

## Draft bounded queue tickets

See [the bounded queue contract](docs/bounded_queue_v1.md) and its [conformance vectors](conformance/bounded_queue_v1.json). This draft changes the legacy compiler pin; the complete legacy suite and the queue lifecycle fixtures must be executed on that pin before promotion. The separate worker-pipeline compiler pin remains unchanged.

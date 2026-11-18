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

# atto-rx-channels

Reactive streams and observable adapters for AttoLang channels.

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

AttoLang is the public name; preserve existing Oreslang/.ores compatibility and use canonical .atto for new portable library source. This README defines scope, not feature readiness.

**Acceptance:** name exact source SHA/tree, runtime/toolchain, positive and negative checks and execution receipt before claiming support. Host-only tests and empty CI steps do not prove guest execution.

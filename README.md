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

## Project status

This describes intended scope, not a verified feature matrix. Consult the source tree and exact-commit CI results for implementation status.

## Ecosystem

- [AttoLang](https://github.com/atto-lang)
- [Language specification](https://github.com/atto-lang/atto-spec)
- [Cross-platform conformance](https://github.com/atto-lang/atto-platform-conformance)

## Pull/push bounded-flow reference model (TARGET, not guest support)

See [the pull/push reactive-admission contract](docs/PULL_PUSH_CONTRACT_V1.md) and its
[source-free protocol model](src/flow-port-model.mjs). Run the model assertions with
`node --test test/flow-port-model.test.mjs` (Node 20+). These tests **do not**
certify compiled AttoLang, any runtime backend, cross-backend parity, or a
zero-GC allocation profile. All concrete guest APIs remain unverified.

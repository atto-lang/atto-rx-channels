# Rx Oreslang: typed errors, `?`, Stream and Channel adapters (v1 draft)

**Status: design + contract only. No changed runtime or compiler pin.**
Upstream language contract:
https://github.com/ores-truffle-oreslang/oreslang-common-source/blob/feat/elm-functional-contracts-20261015/docs/QUESTION_PROPAGATION_AND_REACTIVE_ERRORS_V1.md

## Audited current surface

`src/rx.ores` provides pull-oriented `Observable<T>`,
`Subscription<T>`, `StreamEvent<T>`, bounded single-consumer
`FramedPipe<T>`, `from_future` and `from_channel`.
`Subscription.next(): Option<T>` is legacy, conflating completion and
cancellation; `next_event()` distinguishes them. Native source
exceptions/typed `raise` are not yet compiler-supported, and
`first_required` uses panic-inducing `expect`. Do not advertise
lossless error conversion based on a panic.

## Proposed additive API (snake_case)

- `StreamEvent<T,E>` with distinct `next(T)`, `complete`,
  `error(E)`, and `cancelled`. Use explicit fixed nominal tags;
  avoid encoding a terminal error as `None`.
- `Observable<T>.map`, `.and_then`, `.map_err` (when error
  channel is typed), `.materialize_error`, `.terminate_on_err`,
  `.observe_on(actor)` (only if capability-safe).
- `from_future(Future<T>)`, `from_stream(Stream<T>)`,
  `from_channel(Channel<Frame<T,E>>)`; `to_channel(capacity)` and
  `to_stream()` when resource ownership is proven. Adapter creation
  does not implicitly drain the source.
- `first_result(): Future<Result<Option<T>,E>>` distinguishes an
  ordinary terminal typed error from an empty successful stream; explicit
  cancellation remains its own terminal outcome, not `None` or `Err`.

## Protocol invariants

1. Exactly one terminal claim: completed, cancelled, or failed; never
   deliver NEXT after terminal. No duplicate terminal frame.
2. Values and terminal frames preserve per-producer FIFO; a successful
   `complete()` Future represents the terminal write actually accepted
   by the channel, not merely an eager flag.
3. Channel close, explicit error frame, consumer cancellation, and a
   failed Future are distinct events. Do not convert `raise`/`panic`
   or cancellation to `Result.Err` as though they were ordinary errors.
4. Materialized `Err(e)` is data, so `map` operates on its whole
   payload unless an explicit `map_ok` or `terminate_on_err` is used.
5. `?` operates inside a *single* callable returning Result/Option;
   it does not unwind an entire Observable pipeline or cancel producer
   tasks. Observable handlers need an explicit `terminate_on_err`
   and typed error channel.
6. No inline callback execution on Future completion threads. Deliver
   work through existing scheduler lanes; no actor carrier reentrancy.
7. Backpressure is end-to-end: no hidden unbounded registrations, one
   outstanding pull on a subscription, bounded frame buffering, proper
   rendezvous behavior for capacity zero.
8. Cancellation and termination release registrations/subscriptions
   once, including racing close/fail/cancel, without closing caller-owned
   raw channels or shared Futures.

## Acceptance evidence

Add positive and negative Oreslang source fixtures using the locked
compiler **after** the language/runtime actually admits typed frames and
guest exceptions. Tests: exactly-once terminal transitions, error-as-data,
failure propagation, cancellation race, per-source order, finite
backpressure, single subscription, resource ownership, no Zalgo, and
same semantic traces after future native support.

Do not modify `compiler.lock` or claim executable parity in this PR.

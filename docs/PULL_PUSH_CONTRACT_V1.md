# AttoLang pull/push collection and reactive-admission contract v1

**TARGET / NOT IMPLEMENTED OR CERTIFIED.** This repository supplies a **source-free JavaScript reference model**, not an AttoLang compiler, runtime, ownership checker, scheduler, or ABI. The tests prove properties of this model only.

This is an additive companion to the existing cross-backend `contracts/v1/observable-stream-channel.md` in `oreslang-source.java` and `.llvm` and to the AttoLang draft language specification. Do not change the existing v0 wire/terminal ABI by inference from this model.

## Types and control

- `Iterator<T>` is synchronous *pull*: a consumer calls `next()` and owns the yielded value. Lazy `map`/`filter`/`take` must not secretly collect. `Option<T>` distinguishes value from end, including nested `Option` payloads.
- `AsyncIterator<T>`/`ReadableStream<T>` is asynchronous pull: exactly one active reader lease, bounded outstanding reads and actor-continuation-aware cancellation; returning a Future does not mean an OS thread is parked.
- `Observable<T>` is *push* and must declare cold/hot behavior, single-reader/work-sharing/broadcast mode, callback scheduling, termination, and a finite overflow policy. A raw push callback with no demand or bound is not a safe `Flow`.
- A demand-aware `Flow<T>` / `Subscription<T>` is push with explicit `request(n)` credits. `n` must be positive, representable, and limited; every delivered NEXT consumes one outstanding credit. Delivery, buffered items, checked-out items, retained waiters and copied/frozen payloads must be separately quota-accounted.
- `Channel<T>` is typed *unicast* ownership transfer. A capacity-zero channel is a rendezvous, not a capacity-one queue. Multiple consumers are work-sharing, not broadcast. `Observable.from_ch(ch)` MUST NOT silently start multiple independent readers: an exclusive default is preferred; an explicit work-sharing adapter may admit multiple, and broadcast requires bounded per-subscriber state.
- `Future<T>` (one result), `Task<T>` (eager structured computation), `TaskStep<T>` (lazy single-use computation), `Channel<T>` (unicast), and stream/observable values remain semantically distinct.

## Safety invariants

1. **Admission is not processing:** successful `try_send` transfers one value and reserves quota, not handler completion, I/O flush or peer receipt. An unsuccessful `try_send(value)` returns the same *owned* `value` in a typed failure, without implicit drop or copy. The model's `offer()` simulates this property; it does not verify the AttoLang borrow checker.
2. **Demand bounds delivery:** no NEXT without credit, no integer overflow, no negative request. `Flow` demand is independent of mailbox processing reservations. An adapter MUST reserve downstream slot/byte capacity before pulling an upstream value or retaining a producer waiter.
3. **Account real retained memory:** quotas cover queued + in-flight/unacknowledged values, temporary conversion/copied bytes, producer waiters, selects and fanout. A bounded queue alone cannot prove bounded memory if waiting tasks/callbacks are unbounded.
4. **One terminal:** `COMPLETE` drains committed FIFO items first. `ERROR`/`CANCELLED` settle or drop undelivered queue entries **exactly once**; committed consumer deliveries must remain charged until their physical ACK/retirement. No post-terminal NEXT or resurrection after cancellation. Preserve the existing canonical `Result<Option<T>, Option<E>>` consumer signal, distinguishing NEXT, COMPLETE, CANCELLED, and ERROR including nested Option payloads.
5. **Loans do not escape:** source ownership `rt take` on successful admission; rejected sends retain ownership. `rt copy` requires `Copy`; `rt share` requires verified immutable/shared rights. Borrowed or mutable actor-state references cannot escape a callback, suspension, queue or isolate without a proven safe lifetime. State changes require sealed `critical-read`/`critical-write` discipline.
6. **Cancellation is fenced:** linearize admission vs close/cancel, detach producer waiters once, refund transferred credit once, and defer physical reclamation until outstanding continuations, native operations and consumer loans retire. Generation tickets deny stale producers, deliveries, and ACKs after a completed restart.
7. **No host callback on reactor:** callbacks must execute on an authorized actor/task scheduler, with reentrancy, panic, cancellation and supervision policy. The model intentionally has no callbacks, threads, fairness, or cross-actor transfer.
8. **No hidden GC claim:** lazy/fused operators may avoid *intermediate* collections on a native zero-tracing-GC path, but boxed values, host managed backends, closure captures, retained fanout and adapters must be measured. This document does not claim absolute zero allocation/GC.

## Reference model scope and deliberate exclusions

`src/flow-port-model.mjs` tests a single-producer/consumer **try-admission** state machine with finite demand, byte/slot/in-flight limits, successful ownership move, failed-offer return, FIFO, capacity-zero rendezvous, terminal handling, generation fencing and exactly-once queue dropping. **No claim of thread-safety or linearizability under real concurrent host threads** follows from a single-threaded test. It does not implement real `async send`, fair multiselect, per-domain waiter quotas, physical allocator reclamation, actor mailbox or native I/O. A production implementation must test all of these independently.

## Required backend conformance (release gate)

For Java/GraalVM, LLVM native AOT, Wasm, Forge, .NET Native AOT (and any promoted backend), require identical `.atto` positive and compile-negative fixtures, actual guest execution, cancellation/close races, cross-suspension loan rejection, capacity=0 and capacity>0 tests, budget overflow, exhausted waiter quota, fail-before-publication ownership retention, malformed cross-domain capabilities, shutdown quiescence, and deterministic terminal encoding. Native builds require sanitizers/ownership/drop instrumentation, while managed builds need allocation/GC observations. Do not mark any target PASS from this reference model, a parser-only check, or source-free CI. A private-source mirror to another organization requires source-owner authorization and immutable blob/tree verification; Actions minutes alone do not authorize transfer.

Run the local model: `node --test test/flow-port-model.test.mjs` (Node 20+).

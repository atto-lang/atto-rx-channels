# BoundedQueue<T> v1 contract

Status: draft source contract. This document does not claim compiler/runtime execution.

## Purpose

`BoundedQueue<T>` is a userland policy layer over Oreslang `Channel<T>`. It does **not** add another scheduler, mailbox, lock manager, or transport. The channel runtime remains responsible for bounded buffering, rendezvous, waiter retention, atomic select arbitration, cancellation-safe loser removal, and deterministic selection.

The queue adds a reusable typed surface for operations that need explicit one-attempt cancellation tickets and close/drain semantics.

## Surface

- `bounded_queue<T>(capacity, typed_none) -> BoundedQueue<T>`
- `new_ticket() -> Result<QueueTicket, String>`
- `try_push(value, ticket) -> Result<bool, String>`
- `push_blocking(value, ticket) -> Result<bool, String>`
- `try_pop() -> Result<Option<T>, String>`
- `pop_blocking() -> Option<T>`
- `close() -> bool`
- `is_closed() -> bool`

`_blocking` means the Oreslang continuation may suspend. It never authorizes parking an actor carrier thread.

## Ticket contract

A `QueueTicket` is one-shot. It can be cancelled before or while its push attempt is pending. It cannot be reused after any terminal push outcome. Cancellation after settlement returns false.

Tickets carry the queue generation at issuance. Close increments the generation before releasing the queue state permit. An unclaimed ticket issued before close is therefore stale and a later push attempt returns `Err("stale-ticket")`.

Current v1 tickets are execution-domain-local capabilities because they contain a cancellation channel. They are not actor messages and must not cross actor boundaries.

## Push linearization

`try_push` is immediate and leaves no waiter on `full`.

`push_blocking` performs one priority select:

1. ticket cancellation;
2. queue close;
3. queue write admission.

Therefore a cancellation or close that is already observable at arbitration wins over an uncommitted write. Once the write arm commits, later cancellation cannot revoke the admitted value.

Multiple blocked callers register independently with the same underlying `Channel<T>`. The channel coordinator owns waiter ordering and cancellation-safe removal. This wrapper does not maintain a second waiter list.

## Receive and close

Receive ordering is FIFO for values already admitted to the underlying channel.

`pop_blocking` gives the item arm priority over close. Closing therefore does not discard already-admitted buffered values:

- buffered/admitted values drain first;
- once closed and empty, `pop_blocking()` returns `None`;
- `try_pop()` returns `Ok(None)` for closed+drained and `Err("empty")` for open+empty.

Close is idempotent and rejects new ticket issuance.

## Result meanings

Push errors in this source slice:

- `full`: immediate attempt found no capacity; no waiter retained;
- `cancelled`: ticket cancellation won before write commit;
- `closed`: queue closure won before write commit;
- `stale-ticket`: ticket was issued in an earlier queue generation;
- `ticket-used`: the one-shot ticket was already claimed/settled.

These string errors are a compiler-compatible v1 source surface. The intended language-level endpoint is nominal Error subclasses / Result error types without changing the state machine.

## Fairness and multiple waiters

The wrapper intentionally does not promise a second, library-defined fairness algorithm. Pending write ordering inherits `Channel<T>` arbitration. Required conformance:

- no cancelled waiter may later deliver;
- freeing one slot admits at most one pending writer;
- admitted payload FIFO must not be violated;
- a cancelled older writer must not prevent a later live writer from progressing;
- close must settle all pending pushes without admitting them after closure;
- pending-registration limits must fail closed rather than grow without bound.

Java currently has runtime machinery for pending registration quotas and cancellation-safe pending writer removal. Explicit queue-level regression tests are still required before promoting this contract.

## Ownership and allocation

`BoundedQueue<T>` and `QueueTicket` are local capabilities. Do not send them through actor mailboxes.

Steady-state target:

- LLVM: no mandatory heap allocation per already-provisioned enqueue/dequeue;
- Java/GraalVM: reuse bounded channel/waiter storage where possible and measure managed allocations;
- WASM/.NET/Forge: preserve the same observable state machine and bounded waiter policy.

The v1 source object currently allocates one ticket object and small marker channels per ticket. That is acceptable for semantic validation but **not** the final zero-allocation runtime representation. Native backends should lower tickets to compact generation/slot records or equivalent preallocated waiter storage.

## Promotion gates

1. Exact pinned Java compiler `--check` for `src/bounded_queue.ores`.
2. Execute `tests/bounded_queue_ticket.ores` against its exact output oracle.
3. Java runtime regression for two pending writers, cancellation of the older writer, and progress of the later writer.
4. Close-vs-cancel-vs-admit race tests.
5. Pending waiter quota tests.
6. Same semantic vectors on Java, LLVM, .NET, WASM, and Forge.
7. Allocation and reclamation measurements.

Zero-step Actions jobs are `NOT_EXECUTED`, never source failures or passes.

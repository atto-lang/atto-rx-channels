# BoundedQueue<T> v1 contract

Status: draft integration contract. No exact-head compiler/runtime pass is claimed until real runner steps execute.

## One queue capability

`BoundedQueue<T>`, `QueueTicket`, `QueuePush<T>`, and `QueuePop<T>` are compiler/runtime-owned local capabilities. Rx does **not** wrap `Channel<T>` with a second queue implementation and does not maintain another waiter list.

`src/bounded_queue.ores` is now only a package-level factory:

- `bounded_queue<T>(capacity, max_pending) -> BoundedQueue<T>`

The normative Java source implementation is draft #2312, stacked on runtime #2311 and channel substrate contract #2310.

## Source surface

- `BoundedQueue.new<T>(capacity[, max_pending]) -> BoundedQueue<T>`
- `new_ticket() -> QueueTicket`
- `try_push(value, ticket) -> QueuePush<T>`
- `push_async(value, ticket) -> Future<QueuePush<T>>`
- `try_pop() -> QueuePop<T>`
- `pop_async() -> Future<QueuePop<T>>`
- `close() -> bool`
- `is_closed() -> bool`
- `capacity() / generation() / pending_registrations()`

`QueuePush<T>` exposes `status: Symbol` and `take_value() -> Option<T>`.
`QueuePop<T>` exposes the same pair.

## Ownership invariant

Only `#admitted` permanently transfers a pushed payload into the queue.

Every non-admitted terminal push—`#full`, `#cancelled`, `#closed`,
`#stale_ticket`, `#ticket_used`, or `#resource_limit`—must return the **exact original payload** through `QueuePush<T>.take_value()`.

The caller's original binding is moved at push invocation. For move-only `T`, recovery must occur through the returned `QueuePush<T>`; the original binding cannot be reused. `QueuePush<T>` and `QueuePop<T>` are Copy only when `T` is Copy. Otherwise `take_value()` consumes the result view.

This keeps rejection/cancellation zero-copy and prevents silent destruction of move-only values.

## Ticket and admission linearization

A ticket is one-shot and carries queue generation + sequence identity.

Pending admission uses the backend's canonical channel/select registration. The contract forbids a second library waiter queue.

The authoritative race is:

1. ticket cancellation may win while the write is still uncommitted;
2. closing the **actual item channel** settles uncommitted writes as closed;
3. write commit permanently admits the payload.

A successful cancellation can never revoke a committed payload. Closing never discards already-committed FIFO values.

No consumable synthetic close token is permitted.

## Multiple waiters

Required behavior:

- live pending writers preserve deterministic registration/admission order;
- one freed slot commits at most one pending writer;
- cancelling an older writer detaches it;
- the cancelled payload is returned exactly once and never appears in the queue;
- a later live writer can progress;
- close settles all uncommitted writers and returns each rejected payload;
- pending-registration retention is finite and exhaustion returns `#resource_limit` with the exact payload.

## Close and receive

Close is idempotent and advances generation before terminal channel closure becomes visible.

Already-committed values remain FIFO-readable after close. Once closed and drained, `QueuePop<T>.status == #closed_drained`.

An unclaimed ticket from the pre-close generation returns `#stale_ticket` and its attempted payload is returned through `take_value()`.

## Confinement

Queue and ticket handles are synchronized Copy capabilities only within one execution domain. They cannot cross actor-callable/mailbox boundaries. Actor-to-actor transport remains ActorRef/mailbox based.

## Backend state

- Java #2310: channel FIFO/cancel/close substrate tests.
- Java #2311: first-class runtime queue with bounded waiter budget and ownership-preserving PushResult.
- Java #2312: source builtins, ownership/typechecker/evaluator integration, source execution fixtures.
- LLVM #1198: native pending-writer FIFO/cancellation substrate tests; source select/write lowering still blocked by #325.
- .NET #262: native pending-writer FIFO/cancellation substrate tests; source static select still blocked by #216.
- WASM #189: selectable pending-write substrate required.
- Forge #149: selectable bounded-channel substrate and deterministic/preallocated waiter storage required.

Runtime substrate, source lowering, and guest execution are separate evidence gates.

## Allocation targets

- LLVM/Forge: no mandatory general-heap allocation per already-provisioned steady-state enqueue/dequeue; preallocated queue/waiter metadata preferred.
- Java/GraalVM: reuse bounded channel/waiter storage and measure managed allocations.
- .NET/WASM: preserve the same bounded state machine and measure retention/reclamation.

## Promotion gates

1. Exact Java #2310/#2311/#2312 stack executes with real JDK/Maven steps.
2. Rx exact head executes against its pinned Java #2312 head.
3. Two independently scheduled local producers pass FIFO/cancellation/recovery fixtures.
4. Close-vs-cancel-vs-admit and waiter-budget tests execute.
5. Move-only full/cancel/close paths return exact payload identity.
6. Java, LLVM, .NET, WASM, and Forge execute the same conformance vectors independently.
7. Allocation/reclamation measurements land.

Zero-step Actions jobs are `NOT_EXECUTED`, never source failures or passes.

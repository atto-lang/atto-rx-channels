# BoundedQueue<T> v1 contract

Status: draft source/reference contract. This document does not claim compiler/runtime execution.

## Purpose and layer boundary

`src/bounded_queue.ores` is the readable source-level reference state machine for the bounded-queue v1 contract. It is intentionally built over `Channel<T>` and adds no scheduler, mailbox, lock manager, or second waiter list.

It is **not the final multi-producer capability representation**. Ordinary user classes containing channel handles remain move-only, while a true queue handle must be copyable within one execution domain so independently scheduled local producers can share the same synchronized admission authority. Java draft #2311 implements that first-class runtime reference directly over `ChannelRuntime.Channel<T>`.

The source wrapper remains useful for syntax checking, single-owner semantic fixtures, result/oracle review, and cross-backend contract readability.

## Reference source surface

- `bounded_queue<T>(capacity, typed_none) -> BoundedQueue<T>`
- `new_ticket() -> Result<QueueTicket, String>`
- `try_push(value, ticket) -> Result<bool, String>`
- `push_blocking(value, ticket) -> Result<bool, String>`
- `try_pop() -> Result<Option<T>, String>`
- `pop_blocking() -> Option<T>`
- `close() -> bool`
- `is_closed() -> bool`

`_blocking` means the Oreslang continuation may suspend; it never authorizes parking an actor carrier thread.

## Ticket contract

A ticket represents one push attempt. Cancellation before admission is sticky; a terminal attempt cannot be reused. Tickets carry the queue generation at issuance. Close advances the generation before closing the item channel, so an unclaimed pre-close ticket is stale.

The reference source ticket contains local Channel capabilities and therefore must not cross actor boundaries.

The first-class runtime form in Java #2311 strengthens this: a claimed pending ticket delegates cancellation authority to the exact underlying channel-write Future, so cancellation loses atomically once that write selection is committed.

## Push linearization

`try_push` is immediate and retains no pending writer on `full`.

The blocking reference path races ticket cancellation against the actual channel write. Queue close is **not** represented by a consumable synthetic close token. Instead, `close()` closes the actual `items` channel.

Therefore the authoritative runtime linearization is:

1. ticket cancellation may win while the write remains uncommitted;
2. `Channel.close()` may settle an uncommitted pending write as closed;
3. write commit permanently admits the value.

A committed write cannot later be revoked by cancellation or close.

This avoids the unsafe design where one waiter consumes a "closed" marker and briefly hides closure from another waiter.

## Receive and close

`Channel.close()` preserves committed buffered values and rejects all later/uncommitted writes under the channel coordinator.

Consequently:

- already-admitted values remain FIFO-readable after close;
- closed + drained is terminal;
- the reference `try_pop()` maps closed+drained to `Ok(None)`;
- open+empty remains `Err("empty")`;
- `pop_blocking()` returns `None` only after closed data is fully drained.

Close is idempotent.

## Multiple waiters and fairness

The contract forbids a library-maintained duplicate waiter queue. Multiple pending producers must be represented by the backend's canonical Channel/select waiter machinery.

Required behavior:

- live pending writers preserve deterministic registration/admission order;
- freeing one slot commits at most one pending writer;
- cancelling an older pending writer removes it;
- that cancelled payload never appears later;
- the later live writer can then progress;
- close settles all uncommitted pending writers without admitting them;
- waiter retention is bounded and fails closed at its configured limit.

Java #2310, Java #2311, LLVM #1198 and .NET #262 contain focused source/runtime regressions for portions of this contract. They remain unexecuted until their exact heads receive real runner steps.

## First-class runtime endpoint

The final local multi-producer primitive should be a compiler/runtime-known `BoundedQueue<T>` capability, similar to `Channel<T>`, not an ordinary class wrapping a channel.

Java #2311 currently defines the reference runtime with:

- one-shot generation-bound tickets;
- finite waiter budget;
- immediate Full without retained registrations;
- channel-native pending writes;
- ticket-only cancellation authority;
- actual-channel close;
- deterministic drain;
- wrong-queue ticket rejection;
- stale generation rejection.

A follow-on source-lowering stack will expose typed Symbol outcomes and a `QueuePop<T>` view while keeping `BoundedQueue<T>` and `QueueTicket` local to the execution domain.

## Ownership and allocation

Neither queue handles nor tickets may cross actor mailboxes. Actor-to-actor transport remains ActorRef/mailbox based.

Targets:

- LLVM: no mandatory general-heap allocation per already-provisioned steady-state enqueue/dequeue; preallocate queue/waiter metadata where possible.
- Java/GraalVM: reuse bounded storage/waiter structures and measure managed allocations.
- .NET/WASM/Forge: preserve the same bounded admission/cancellation/close state machine.

The current source reference allocates ticket objects/marker channels and is not an allocation target.

## Promotion gates

1. Exact pinned Java compiler checks the source reference and fixture.
2. Exact Java #2311 runtime tests execute with real JDK/Maven steps.
3. Source-visible first-class queue lowering executes with two independently scheduled local producers.
4. Close-vs-cancel-vs-admit adversarial tests execute.
5. Pending waiter quota tests execute.
6. Same backend-neutral vectors execute independently on Java, LLVM, .NET, WASM and Forge.
7. Allocation/reclamation measurements land.

Zero-step Actions jobs are `NOT_EXECUTED`, never source failures or passes.

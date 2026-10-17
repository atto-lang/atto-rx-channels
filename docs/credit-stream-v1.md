# Typed credit-gated stream experiment (draft v2)

This source-only experiment is stacked on the hardened Rx subscription work in
PR #19. `CreditPipe<T,E>` is one publisher + one subscriber in one Ores
execution domain. It is not `ActorStream<T>`, a multicast Subject, or a compiler
builtin `Stream<T>`.

## Canonical typed signal

`next_signal(): Result<Option<T>, Option<E>>` is the common reactive signal ABI:

| Signal | Meaning |
| --- | --- |
| `Ok(Some(value))` | NEXT(value) |
| `Ok(None)` | COMPLETE |
| `Err(None)` | CANCELLED |
| `Err(Some(error))` | explicit typed ERROR(error) |

The outer Result/Option layers are protocol-owned. Values of
`T = Option<U>` and `T = Result<A,B>` remain ordinary NEXT data, e.g.
`Ok(Some(None))` and `Ok(Some(Err(dataError)))`.

`fail(E)` explicitly publishes a typed terminal error. It is not an automatic
conversion of guest `throw`, `raise`, `panic`, host failure, or runtime
cancellation into data.

## Demand and bounded publication

`subscribe()` claims the unique reader. `request()` issues exactly one event
credit. A second request before that event is observed returns false.

`send(T)`, `complete()`, and `fail(E)` consume one issued credit and return
`Future<Option<SelectResult>>`. Their publication select is ordered:

1. private cancellation control;
2. frame write.

Index 1 means the frame write won; index 0 means cancellation won. Capacity zero
is true rendezvous. Only one producer publication and one consumer pull are
admitted at a time.

The writer slot remains claimed until `next_signal()` consumes the frame or
consumer cancellation revokes the publication. Thus a buffered write Future may
settle early without admitting an unbounded second producer registration.

## Linearized source state

All destructive marker read/restore probes are serialized by the private
capacity-one `state_busy` gate. The gate covers only synchronous state
observation/claim turns. It is never held across `await`, `nb select`, user
callbacks, or producer/consumer rendezvous.

`next_signal()` registers its stop-vs-frame select outside the gate. After a
frame wins, it re-enters the state gate before exposing the frame so a committed
consumer cancellation suppresses later NEXT/terminal delivery. A frame may
already have been consumed by the winning select; cancellation cannot undo a
committed channel transfer.

`cancel()` revokes unused producer demand and the writer slot, then signals both
private stop channels outside `state_busy`. An already issued consumer request
remains claimed until `next_signal()` observes CANCELLED, so cancellation is a
real terminal outcome rather than a fabricated “missing request” error.

## Ownership boundaries

The frame channel is private and carries only
`Result<Option<T>,E>`. The compiler pin is Java PR #1193 head
`f840d86744faa2a9d310ca062ad25afb0458d909`, which rejects recursively nested
callables and runtime capabilities from `Channel<T>` payloads, including
Channel/Future/mutex/iterator/select state hidden inside nominal fields.

Consumer cancellation never closes or cancels an unrelated producer Future,
actor, or external channel. Live CreditPipe, Channel, subscription, iterator and
scheduler/select capabilities remain execution-domain local.

## Promotion gates

This is still a draft. Before promotion:

- execute Java #1193 exact head and full JDK25 Maven verification;
- execute this exact Rx head under its exact `compiler.lock`;
- stress cancel vs frame commit, terminal vs cancel, cap=0/cap=1 and teardown;
- prove actor/async boundary rejection of live transport/cursor state;
- add LLVM/.NET/Wasm/Forge negative or positive parity as appropriate;
- keep legacy `StreamEvent<T>` explicitly lossy; the canonical typed signal is
  `Result<Option<T>, Option<E>>`.

The checked-in Python reference model is host-only invariant evidence, not
Oreslang compiler/runtime evidence.

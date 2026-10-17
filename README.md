# rx-oreslang-channels

A userland reactive stream library written in **Oreslang**. It uses bounded/rendezvous channels, `readch`, `nb writech`, `try` probes, dynamic `select`/`nb select`, and `await`. It follows the pointerless ownership model throughout. `src/rx.ores` is a plain file/code unit, not a synthetic package or module wrapper; callers import the file with `import * as ...` and/or select declarations by relative path. It has no dependency on `std/rx` and adds no Java reactive implementation.

This library lives outside core/std-lib. The core rx-ores implementation can evolve independently while this version exercises Oreslang's channel and source-frame suspension APIs.

## Run

Install JDK 25, Maven, Python 3, and Git, and authenticate Git for the private ores-truffle-oreslang repositories, then:

```sh
python3 scripts/setup.py
source .work/env.sh
python3 scripts/test.py
```

`compiler.lock` pins exact Java current-main integration commit `f840d86744faa2a9d310ca062ad25afb0458d909` (draft Java PR #1193). Current Java main already contains Future/channel select, waiter detachment, cancellation-revocation fencing, and retained-arm budgets; #1193 adds the Rx-required recursively data-only `Channel<T>` policy, including rejection of nested runtime capabilities, plus focused Rx cancellation regressions. This pin is intentionally **draft-only** until the integration head itself runs JDK25/full Maven. Setup fetches the pinned commit; it does not modify your compiler checkout or `std/rx`.

You can also set `ORES_CLASSPATH` to an existing compatible compiler's `target/classes` plus its Maven dependency classpath. Set `JAVA` to the Java executable if necessary.

## Channel source with async/await

```ores
import * as rx_channels from './src/rx.ores';
import class FramedPipe, Subscription, StreamEvent from './src/rx.ores';

pub async fnc main(): void {
  // Current compiler needs a typed None witness for generic inference.
  val Option<int> element_type = None;
  val FramedPipe<int> pipe = rx_channels.framed_pipe(0, element_type);
  val Future<void> producing = pipe.send(42);
  val Subscription<int> sub = pipe.subscribe();

  val StreamEvent<int> item = sub.next_event();
  stdio.println(item.value.unwrap());
  await producing;

  val Future<void> finishing = pipe.complete();
  stdio.println(sub.next_event().is_complete());
  await finishing;
  return;
}
```

The reference compiler currently rejects generic `async fnc` declarations and async instance methods. The generic library therefore uses **ordinary methods whose source bodies suspend**. `Subscription.next()` returns `Option<T>` at the source level; call it directly inside a resumable source workflow. Internally, channel subscriptions use `nb select`, whose value form is `Future<Option<SelectResult>>`; awaiting it yields the current Ores continuation rather than parking an actor carrier. `send()` and `complete()` return real `Future<void>` registrations that callers explicitly `await`. `from_future()` adapts an existing Future. See [examples/channel_async.ores](examples/channel_async.ores) and [examples/pipeline.ores](examples/pipeline.ores).

Imports of generic functions currently use the module-qualified direct-call form. Explicit types on imported results retain useful checking across the current import boundary.

## API

| Operation | Behavior |
| --- | --- |
| `from_values(Array<T>)` | Takes ownership of its move-only array; separate cursor per subscription |
| `from_channel(Channel<Option<T>>)` | Hot input with one consumer; no background pump |
| `from_future(Future<T>)` | One shared Future result, then completion |
| `map(Observable<A>, Fnc<A, B>)` | One transform per demanded item |
| `filter(Observable<T>, Fnc<T, bool>)` | Iterative pulls until a predicate accepts; the callback receives temporary read access |
| `take(Observable<T>, int)` | At most N items, then cancels upstream |
| `merge_channels(left, right)` | Fair deterministic merging of two channel inputs |
| `first_result(Observable<T>)` | **Recoverable path:** `Result<Option<T>, Object>`; cancellation in `finally` |
| `first(Observable<T>)` | Compatibility helper returning `Option<T>`; panics on `Err`; cancellation in `finally` |
| `first_required(Observable<T>)` | Returns `T`, fails on empty rather than returning `None` (native Future-valued `first()` is a future integration target) |
| `framed_pipe(capacity, typedNone)` | **Preferred:** privately owns one writer/channel and admits one subscriber |
| `pipe.send(value)` / `pipe.complete()` | Legacy Future-returning writes; terminal-safe but callers must bound/await pending registrations |
| `pipe.send_blocking(value)` / `pipe.complete_blocking()` | **Preferred strongest backpressure path:** one delivery credit is held until the write Future settles; suspension is non-parking |
| `pipe.subscribe()` | Claims the single subscriber; duplicate calls fail |
| `framed_sender(Channel<Option<T>>)` | Creates checked `FramedSender<T>` for ordered terminal writes |
| `writer.send(value)` | Rejects sends after completion; returns write `Future<void>`; direct callers can still accumulate pending registrations |
| `writer.send_blocking(value)` / `writer.complete_blocking()` | Serialize one in-flight delivery across actual settlement using a private delivery credit |
| `writer.complete()` | Claims termination exactly once and writes `None`; repeats fail |
| `subscription.next_signal()` | **Preferred closed typed signal:** `Result<Option<T>, Option<Object>>` = `Ok(Some(T))` NEXT, `Ok(None)` COMPLETE, `Err(None)` CANCELLED, `Err(Some(error))` ERROR |
| `subscription.next_event_result()` | Legacy-object compatibility projection from `next_signal()`; `Err(error)` is never rewritten to `complete` |
| `subscription.next_event()` | Legacy compatibility projection; panics on `Err`; event tags remain `next`, `complete`, or `cancelled` only |
| `subscription.is_complete()/is_cancelled()/is_failed()` | Query mutually arbitrated terminal state; failure is not completion |
| `send(channel, value)` | Legacy **unchecked** raw helper; caller must uphold terminal protocol |
| `complete(channel)` | Legacy **unchecked** raw helper; does not close the channel |
| `observable.subscribe()` | Creates an independent subscription state |
| `subscription.next_result()` | **Recoverable path:** `Result<Option<T>, Object>`; one outstanding pull; `Err` is terminal failure data |
| `subscription.next()` | Compatibility wrapper around `next_result()`; panics on ordinary `Err` |
| `subscription.cancel()` | Idempotent cancellation; returns true only once |

Oreslang's source ownership model is pointerless. Callback types stay ordinary, for example `Fnc<int, bool>` or `Fnc<T, bool>`; a first-class callback call receives temporary read access without encoding a C/Rust-style pointer type. If code needs a named borrow beyond one call expression it uses `rt borrow value`, not `&value`.

```ores
val Fnc<int, bool> even = |value| -> {
  return value % 2 == 0;
};
```

The library and test runner reject pointer-style callback types, unary address-of borrows, and pointer declarations.

## Checked legacy event construction (staged)

`StreamEvent<T>` is currently a **legacy three-tag projection**, not a
cross-family typed terminal ABI. Its constructor now rejects unknown tags,
`next` with no payload, and `complete`/`cancelled` with a payload.
`Some(None)` remains a legal `Next` event when `T = Option<U>`.
`is_terminal()` is true only for `complete` and `cancelled`.

This prevents accidental malformed *objects* but does not supply
typed `Error(E)` events. The existing `marked()` read-and-restore helper
is intrinsically non-atomic; it is valid only while a dedicated source-level
state permit serializes all accesses to that marker, or when a marker has
exactly one owner. The `Subscription` methods `next_result()`, `cancel()`, `is_complete()`,
`is_cancelled()`, `is_failed()`, `claim_finished()`, and `claim_failed()` now protect
marker observations/terminal claims with a separate short-lived
`state_busy` capacity-one channel. That permit is **not held during**
`pull()`, user callbacks, or `dispose()`. A cancelled pull may have
already consumed a frame that cannot be undone. This is a candidate
source-level state protocol, **not** proven race-free guest execution.

`next_result()` preserves ordinary upstream failures as `Result.Err(Object)` through `map`, `filter`, and `take`. `next_signal()` adds a **closed, exhaustively matchable terminal projection using compiler-owned ADTs**: `Ok(Some(T))` NEXT, `Ok(None)` COMPLETE, `Err(None)` CANCELLED, and `Err(Some(error))` ERROR. This keeps `T = Option<U>` (`Ok(Some(None))`) and `T = Result<A,B>` ordinary data unambiguous. `next_event_result()` is now only a compatibility conversion from that typed signal, while legacy `next()` / `next_event()` remain panicking wrappers. `FutureSubscription` uses an atomic stop-channel/Future select so cancellation can detach its waiter without cancelling the borrowed producer. Still missing: a future ergonomic nominal/sealed `StreamEvent.Error<E>` spelling once the language has closed user-defined ADTs; compile-time enforcement that legacy Future-returning sends are awaited; rigorous multi-producer handling,
cross-actor isolation and scheduler-level race tests. Until real pinned
compiler tests run, do not advertise lossless
`Observable`/`Stream`/`Channel` conversion or full parity.
See [common-source contract #61](https://github.com/ores-truffle-oreslang/oreslang-common-source/pull/61)
and [runtime hardening issue #18](https://github.com/ores-truffle-oreslang/rx-oreslang-channels/issues/18).

## Subscription state and cancellation audit

The original `Subscription.next()` tested terminal markers, then registered
`pulling` in a **separate** operation. Concurrent `cancel()` or natural
completion could interleave between those steps, and `cancel()` similarly
read-and-restored markers outside any common gate.

A short-lived `state_busy` write-held permit now covers:

- OPEN/terminal check together with the one-outstanding-pull admission
- cancellation versus natural-completion-versus-failure terminal claims
- `is_complete()`, `is_cancelled()`, and `is_failed()` state observations

Pending `pull()` remains outside the permit so a cancelling task can enter,
claim cancellation and invoke `dispose_once()`. `FutureSubscription` no longer
raw-awaits its producer: it selects between `SelectCase.read(stopped)` and
`SelectCase.future(pending)`. A stop win detaches the Future waiter without
cancelling the shared producer. This relies on current-main compiler integration #1193;
the underlying Future-select primitive has historical exact-tree evidence from Java #880, but this Rx exact head
has not yet executed under the pinned compiler, so bounded cancellation latency
is still an **unverified integration claim**, not release evidence.

Even the short state permit is backed by normal channel wait registrations;
this implementation has no independently proven bound on an adversarial
number of simultaneous callers. The native scheduler/ownership layer must
enforce execution-domain confinement and admission budgets.

## Stream contract

- The preferred `FramedSender<T>` transports `Some(value)` then exactly one `None`, claiming termination before submitting the terminal write. A capacity-one **admission permit** now serializes `send()`, `complete()`, and `is_complete()` terminal checks *on that sender instance*. This closes the destructive-marker observation window **for those sender methods only**; it does not establish an atomic shared `Subscription` state, protect alternate sender/raw-channel aliases, or cancel pending delivery. The permit is released after write **registration**, not after its Future settles, to preserve rendezvous progress. Duplicate completion and sender writes after the claim fail. Completion is registered after earlier writes through the same sender.
- **Important ownership limit:** `FramedSender` is single-writer, task/actor-local state. It cannot enforce the protocol against code that retains and writes directly to the underlying raw Channel. The older raw `send(channel)` and `complete(channel)` functions remain for compatibility but are unchecked. A native channel-close adapter is the eventual stronger boundary.
- A submitted completion `Future<void>` must be awaited. When capacity is zero or the queue is full, it can remain pending until a consumer receives the terminal frame.
- Capacity zero is rendezvous; positive capacity bounds accepted writes. Legacy `send()` does not spin or drop when full, but its admission permit does **not** cap outstanding write Futures. Callers must retain/await each returned Future. Prefer `send_blocking()` / `complete_blocking()` when strict source-level backpressure is required: a private one-token delivery credit is held across `await delivery` and restored in `finally`, so that path admits at most one unsettled delivery per sender without parking a carrier.
- Pull operators have no prefetch queue. `take(0)` consumes nothing. `take(N)` cancels upstream immediately after its Nth value. Filter uses a loop rather than recursive callbacks.
- Each channel input has one subscriber. `from_channel` and `merge_channels` now reject a second `subscribe()` on the same Observable instead of handing out competing readers; one completion frame cannot terminate multiple consumers. This is **not multicast**. Use distinct channels for fan-out. The two merge inputs must be distinct channels.
- Merge keeps reusable FAIR select sets, removes completed inputs from selection, and finishes only when both complete. Cancellation uses a select control arm, allowing the runtime to remove losing read registrations.
- Dynamic `select from` returns `Option<SelectResult>`; `nb select from` returns native `Future<Option<SelectResult>>`; `try select from` remains an immediate `Option<SelectResult>` probe.
- Cancellation leaves the producer's channel open and preserves values not claimed by a winning selection. A read that already won a race may have consumed its value before cancellation.
- For backward compatibility, `next(): Option<T>` returns `None` on both cancellation and natural completion. Prefer `next_signal()` when terminal cause matters: it is closed and typed across NEXT / COMPLETE / CANCELLED / ERROR. `next_event()` remains the legacy three-tag object projection and cannot itself carry ERROR.
- Termination cleanup is claimed exactly once across completion, failure, and explicit cancellation. `cancel()` after natural completion returns false, and does not re-dispose a completed subscription.
- Future sources retain the producer's lifetime. `FutureSubscription` atomically selects its private stop channel against the shared Future; cancellation signals stop, the losing Future listener is detached, and the producer Future remains independently awaitable. If the Future already won, the subscription's terminal-state check suppresses post-cancel delivery.
- Ordinary operator/Future failures use the recoverable `Result` path: `next_result()`, operator `pull_result()`, and `first_result()` preserve `Err(Object)` without converting it to completion. `next_signal()` maps that failure to `Err(Some(error))`; cancellation is the distinct `Err(None)`. Legacy `next()`, `next_event()`, operator `pull()`, and `first()` remain compatibility wrappers that use `Result.expect`. `finally` clears demand and disposes upstream even when a stronger panic/cancellation signal bypasses ordinary `catch`.
- `Array<T>` is move-only on the pinned compiler. `from_values` accepts ownership of that array, so the caller must not access or mutate it after transfer. `rt copy` on move-only arrays is **not yet supported** without `Symbol.rtCopy` lowering, and must not be silently treated as a shallow alias. Replay shares the captured collection across subscriptions; nested mutable objects still require explicit safe ownership or immutability. Use channels for owned mutable payloads.
- Channels and subscriptions stay in their execution domain. They cannot cross actor mailboxes; use ActorRef/mailbox protocols for actor-to-actor transport. Function/closure values are deliberately not channel payloads: callbacks remain local and channels carry data. Structured actor cancellation remains runtime-owned.

This is an initial pull-oriented implementation, not complete Rx operator parity. Timed operators, multicast subjects, variadic merge, an ergonomic nominal/sealed stream-event ADT spelling, and static enforcement for callers that choose the legacy Future-returning sender API need additional work.

## Validation

The test runner type/ownership-checks the library, examples, and every test program, then executes each with a timeout and checks exact output or an expected failure. Coverage includes replay and array ownership rejection, completion ordering, checked sender double-close/send-after-close rejection, natural completion vs cancellation events, cleanup-at-most-once, `first_required` on present/empty sources, operator composition, no prefetch, fair merge, rendezvous backpressure, Future adaptation, upstream failure, and invalid take counts. The existing `.github/workflows/test.yml` builds the pinned compiler and runs the suite when its `ORES_COMPILER_READ_TOKEN` read-only secret is present. Historical funded Java regressions used exact-tree private mirrors and blob-identity checks. In this audit, a fresh alternate private runner was verified and a source-free protocol oracle passed, but the attempted full private Rx/compiler mirror was blocked by a safety check and was not bypassed. Therefore no current Rx guest-runtime pass is claimed. Local validation uses existing Git authentication.

## Compiler compatibility checkpoint (2026-10-06)

This repository tracks compiler PRs #398/#399/#404/#405/#406/#408/#409/#410/#411/#412 as **unmerged proposals**, without changing its stable compiler pin or API behavior. See [docs/compiler-pr-sync.md](docs/compiler-pr-sync.md) for rx-oreslang-channels-specific migration invariants, dependencies and validation gates.

## Ownership and lifecycle audit (October 2026)

`framed_pipe(capacity, typedNone)` is the recommended entry point when the stream owns its channel. Its transport and sender are private and it accepts only one subscriber; this eliminates external raw-write bypass of the terminal sentinel for this API. Existing `framed_sender(rawChannel)` and `from_channel(rawChannel)` remain compatibility adapters without this enforcement. The sender and subscription now serialize their *own* relevant marker accesses with separate permits, but raw marker probes remain non-atomic and the runtime has not been race-certified. `Subscription.dispose_once()` is private to prevent external callers from triggering cleanup independently of terminal state. `pull()` and `dispose()` are still public override hooks pending support for protected class methods, and must not be called directly. Native `std/rx` remains the eventual authority on structured cancellation.

**Generic factory note:** The pinned compiler forbids public constructors on file-private classes and explicit generic type arguments on imported function calls. For now create a typed `None` value (for example `val Option<int> witness = None;`) and call `rx_channels.framed_pipe(0, witness)`. The witness is *not* a stream value and is checked to be `None`; it only enables generic parameter inference. This avoids exposing the pipe's raw channel while respecting file-private class visibility.

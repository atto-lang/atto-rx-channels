# Observable implementation comparison (prototype contract)

These repositories are **competing userland experiments**, not three adapters around one hidden implementation. Do not merge them or choose an official implementation on anecdotal timing results. The final Oreslang library may be hybrid, but it must be selected using correctness, usability, composability, ownership and real workload performance.

| Experiment | Execution mechanism | Observable consumption | Demand/backpressure |
| --- | --- | --- | --- |
| [rx-ores-callbacks](https://github.com/ores-truffle-oreslang/rx-ores-callbacks) | Direct synchronous callback composition; no `await`, `Future`, or channel | Push to `subscribe(on_next)` | A callback returns `false` to stop **synchronously**; not a general asynchronous buffer protocol |
| [rx-ores](https://github.com/ores-truffle-oreslang/rx-ores) | Pull subscriptions, native `Future<T>` and `await` suspension | `Subscription.next()` | One outstanding pull, no speculative prefetch |
| [rx-oreslang-channels](https://github.com/ores-truffle-oreslang/rx-oreslang-channels) | Pull subscriptions with bounded/rendezvous `Channel` frames and `select` | `Subscription.next()` | Demand, bounded channel capacity, single-consumer restrictions on owned pipes |

## Shared functional baseline

- Cold finite source: `from_values`; ordered `map`, `filter`, `skip`, `take`; early-stop semantics. Every `skip(n)` discards exactly the first `n` upstream values, emits no skipped values and rejects negative counts. `skip(0)` is identity; `skip(n)` with `n` greater than source length emits nothing.
- Error behavior must be explicit; never silently translate `Result`, `Option`, `Future`, `Channel` and `Observable` into one another. Operator callback exceptions must not masquerade as normal end-of-stream.
- Track source consumption **separately** from downstream emission. The callback variant's current `subscribe` returns the number of original source values consumed, including those rejected by filters or skipped, **not** the number emitted to the terminal callback.
- Pull variants must preserve demand and propagate cancellation upstream exactly once, including errors and early `take`. Callback variant stops cooperatively via return `false`; no claim that a synchronous callback invocation itself is asynchronously nonblocking.
- Use Oreslang's pointerless ownership semantics. No implicit `self` capture and no implicit conversion of callback-containing payloads into channel-sendable values.
- `from_values` is finite/cold in intent; verify actual compiler ownership behavior for multiple subscriptions before claiming replayability across all types. Hot multicasting, error-as-data, fairness, overflow/drop policies and multi-subscriber behavior are independent future experiments.

## RxGo ideas worth testing, not copying blindly

[ReactiveX/RxGo v2](https://github.com/ReactiveX/RxGo) uses channels and staged pipelines. It distinguishes `FromChannel` from eager `FromEventSource`, lazy from eager observation, sequential vs pooled operators, connectable observables and explicit buffered/drop backpressure strategies. Implement these behind *separate named tests and benchmark scenarios* rather than silently changing this prototype's demand contract. RxGo's goroutine-per-stage assumptions are not Oreslang actor guarantees.

## Performance and adoption gates

1. **Conformance:** same downstream sequence, order, exact source-consumption counts, terminal state, negative-parameter errors, callback failure, cancellation-before/during pull, once-only cleanup, bounded buffers, no leaks or livelocks. Include independent sources and single-subscriber protocol tests where applicable.
2. **Composability/usability:** typed operator signatures, readable call sites, native `Stream`/`Future`/channel bridges with ownership-safe explicit adapters, actor-safe cancellation and structured error handling. Keep a fourth **streams-native** design as a candidate; do not simulate it by renaming channel or callback code.
3. **Benchmark:** identical input and logical pipeline, same compiler commit/tree, warmups, run order, iteration count and hardware; validate semantics before timing. Record CPU time, allocations/op, peak resident memory, scheduler wakeups, p50/p95 latency, throughput, producer/consumer imbalance and cancellation latency, not just process wall time. Publish raw samples and configuration.
4. **Caution:** the current microbenchmark uses different terminal operations: pull variants sum the downstream values (6 + 8 + 10 = 24); callback variant reports five upstream items consumed and scales by eight to 40. For 20,000 iterations that means expected printed values of 480000 (pull/channels) and 800000 (callbacks). These are **distinct assertions**, not equivalent checksums; do not treat this benchmark as a fair final ranking until a common downstream terminal accounting API is validated.
5. **Decision:** establish passing cross-backend JVM/Graal and LLVM conformance, independent actor-ownership proofs, repeatable measurements with confidence intervals, and non-microbenchmark end-to-end results. Select or combine implementations only after these gates.

Validation currently remains pinned per repository via `compiler.lock`; a proposed PR is not proven by static inspection alone. Run the repository's `scripts/test.py` with its exact compiler pin, then rerun representative programs and benchmark on the same compiler revision before merging.

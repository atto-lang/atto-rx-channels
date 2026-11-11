# Executable Java/Graal channel milestone

`src/worker_pipeline.atto` contains the producer, worker, collector coordination,
cancellable write admission and one-shot shutdown policy. Java supplies the
existing channel/select/scheduler capabilities; Python only invokes processes and
compares outputs. `tools/ChannelPipelineGuestProbe.java` observes the existing
runtime's selection counters for testing and adds no guest capability.

This is a **cooperative, same-domain** two-producer/two-worker pipeline. The
coordinator dispatches each FIFO job as data to a worker, then drains the result
queue. It grants the next pair of producer turns only after settling every
producer and worker write from the current pair. It does not promise independently
scheduled actor workers, parallel CPU execution, multicast, or arbitrary producer
fairness. Actor transport must use ActorRef/mailbox data protocols; neither
channels nor callbacks are sent to another actor here.

## Bound and lifecycle

Each edge has capacity one. A pair of writes therefore retains at most one
buffered scalar and one pending write registration per edge. There is no app
waiter list, prefetch collection or unbounded Future array. The collector
deliberately waits until both worker writes have been submitted before reading.
`pipeline_bounds.atto` exposes both full-edge observation points; the test-only
probe requires exactly one live selection/arm at each. FIFO is asserted for two
blocked producers. Round-robin turn grants give each producer and worker one
turn per round; channel registration order governs delivery on each edge.

`offer()` selects cancellation before write admission in one priority select.
Cancellation of a blocked older writer removes its write arm and allows the
later live writer to advance. A cancellation issued after a write commits cannot
revoke that data. `shutdown()` uses one immediate claim and closes both queues
only once. A failing third producer triggers shutdown while two other writers
are blocked; both writes fail and the previously committed item still drains.
Every positive fixture requires zero live coordinator selections and arms at its
last guest output **before context teardown**, and again after teardown.

## Reproduce

Use an isolated clean checkout of the compiler in `pipeline-compiler.lock`, JDK
25, Maven, Python 3, and authenticated access to that private repository:

```sh
export JAVA_HOME=/path/to/jdk-25
python3 scripts/test_pipeline.py --compiler /path/to/clean/compiler \
  --output /path/outside/this/repo/evidence --repeat 20
```

The harness verifies both compiler commit and tree, requires clean app/compiler
checkouts, builds with `mvn -q -DskipTests clean package`, checks every new guest
module/fixture, compiles the observation probe and executes every positive
fixture 20 times. The JSON receipt records exact application/compiler identities,
commands, exit statuses, expected/actual stdout, stderr and source digests.
Output mismatch or retained waiters fails the process. Two negative fixtures
must be rejected at the actor boundary. This validates Java/Graal only; LLVM,
Wasm, Rust/Cranelift, Forge and .NET are **NOT EXECUTED** for this pipeline.

## Reconciled migration and remaining compatibility gates

The destination's initial history and ownership documentation are retained.
Legacy source history is imported with a merge parent; no source ref is changed.
`docs/legacy-channel-library.md` preserves the legacy README without replacing
the AttoLang README. The destination ownership PR #1 is an ancestor of this work.

Source proposals are reconciled as follows:

| Proposal | Treatment |
| --- | --- |
| #19 | Inherited subscription/signal and delivery-credit work via #23 |
| #22 | Terminal-winner fix inherited via #23 |
| #23 | Checked blocking-only sender API retained; not reintroduced as a competing sender |
| #20 | Explicit-credit stream remains a separate experiment; not merged or advertised as executable here |
| #26 | Factory targets native `BoundedQueue`/`QueueTicket` types absent from this compiler; not imported as a working queue |
| #27 | Fixture/bootstrap confinement reconciled with newer main's inventory tests |

The migrated `src/rx.ores` is **not certified** on the new pipeline compiler.
Its `Subscription.cancelled = Channel.new<bool>(1)` field initializer is rejected
by construction-effect admission. `scripts/test.py` also rejects the inherited
`test_native_rx_async.ores` before compilation because it has no stdout/failure
oracle; that fixture still calls the Future-returning sender surface superseded
by #23. Those are concrete legacy compatibility gates, not passes or failures of
the new standalone pipeline. Its old `compiler.lock` and workflow remain legacy
configuration; the pipeline uses its separate, explicit pin and harness.

Compiler PR #2310's four pending-writer runtime tests were executed as an exact
test-blob overlay on the pipeline compiler, together with the existing channel
runtime and select-quota tests. This is supplemental host/runtime evidence,
not execution of the entire historical PR head. It pins FIFO, cancellation,
post-admission commitment and close/drain behavior required by this pipeline.
See the execution receipt for the exact test blob and command. Local execution
was available; no budget fallback, source-org merge-check bypass, repository
transfer, release or deployment was performed.

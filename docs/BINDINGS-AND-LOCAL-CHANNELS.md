# Bindings and local-channel contract

Follow [compiler PR #411](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/411): `const x` fixed/read-only; `val x` fixed/mutable (= `const mut x`); `let x` rebindable/read-only; `let mut x` rebindable/mutable.

`case msg = readch(input) -> { ... }` binds read-only by default; `case val msg` allows owned referent mutation but no rebinding; `case mut msg` abbreviates `case let mut msg`. A losing case must not consume a message or transfer ownership. `select` yields actor execution when no cases are ready; `nb select<T>` returns a tracked `Future<T>`; detached `do nb select` needs bounded outstanding registrations.

Execution-domain-local channels may transport **owned** closures/function values and owned object references. Writes transfer move-only ownership to the channel; borrowed payload types are rejected transitively because a buffer or pending registration may outlive the borrow. Nonblocking select registration owns every candidate move-only write payload immediately. **Actor mailboxes remain serialized/frozen** and may never carry raw pointers, functions, borrows, local channel/select capabilities, or mutable alias graphs. The pinned compiler revision implements this local-channel distinction and the callable-payload test is positive, not an expected compile failure.

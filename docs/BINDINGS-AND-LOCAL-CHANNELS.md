# Bindings and local-channel contract

Follow [compiler PR #411](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/411): `const x` fixed/read-only; `val x` fixed/mutable (= `const mut x`); `let x` rebindable/read-only; `let mut x` rebindable/mutable.

`case msg = readch(input) -> { ... }` binds read-only by default; `case val msg` allows owned referent mutation but no rebinding; `case mut msg` abbreviates `case let mut msg`. A losing case must not consume a message or transfer ownership. `select` yields actor execution when no cases are ready; `nb select<T>` returns a tracked `Future<T>`; detached `do nb select` needs bounded outstanding registrations.

Local-only channels may eventually transport safe closures and owned/borrowed object references, with compiler-checked domain/lifetime/capture rules. **Actor mailboxes remain serialized** and may never carry raw pointers, functions, borrows, or mutable alias graphs. Current pinned compiler still rejects callable `Channel<T>`, and its negative tests must remain until local-only capability is implemented.

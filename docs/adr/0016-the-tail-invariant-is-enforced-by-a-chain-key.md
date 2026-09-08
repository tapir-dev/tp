# The KV-cache tail invariant is enforced by a chain key, not a list of exceptions

The provider context may only grow at the tail: any insertion before the
previous tail invalidates the provider's KV cache and multiplies cost. The
obvious enforcement is a list of named exceptions — compaction, fork, tree
navigation — checked against at each request. That list is wrong on its first
day, because the prefix also changes when the model changes, when the thinking
level changes, and when the context files are re-rendered, none of which touch
the conversation tree.

So the invariant is stated over a **chain key** instead: session, surface,
model, thinking level, and the hash of the resolved system prefix. A request
whose chain key differs from its predecessor's starts a new chain, and no
comparison is owed. A request whose chain key matches but whose encoded prefix
is not an extension of its predecessor's is a bug. The list of exceptions
disappears into the key, and the key is a type rather than a comment.

The structure underneath it does most of the work: a request is a pure function
of the active branch, which is the only part of a session that becomes model
context, and the only exposed mutation appends at the leaf. There is no API that
accepts an arbitrary message list, so "insert before the tail" is not an
operation that exists. A partial stream from a failed attempt is discarded
rather than appended, which is what makes a reissued attempt prefix-identical by
construction rather than by care.

## Consequences

- **A chain key change is a real cost, so it is measured.** Every transition is
  a paid KV cache miss; it emits a measurement rather than passing silently.
  This is the second use of the key, and the reason it beats an exception list
  on more than tidiness.
- **The check is split across two crates.** The encoder computes the prefix
  fingerprint and the chain key and returns them as data — a fact about bytes.
  The agent holds the previous pair and compares. The seam crate therefore
  still does not know what a second attempt is.
- **A violation is a `debug_assert!` in debug and a measurement in release.** It
  is not an event: the event taxonomy freezes its lifecycle variants, and a
  cache invalidation is a cost, not a terminal state.

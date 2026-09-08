# The event taxonomy is closed in code and open on the wire

The event union has to satisfy two rules that read as opposites: the project
values prefer small closed enumerations so exhaustiveness checking and
recovery-case coverage stay tractable, and the v1 scope line requires a
taxonomy versioned and serializable for an external consumer that must tolerate
a version it was not built against. We satisfy both by splitting where the
enumeration is closed from where it is open: in Rust the union is a closed
enum, matched exhaustively; on the wire a reader must ignore an unknown `type`
and unknown fields on a known variant, and must never fail on either.

Ignoring the unknown is only safe if the unknown can never be load-bearing, so
the tolerance rule carries a second half that makes it provable rather than
hopeful. Variants split in two: **lifecycle variants** (`*_start`, `*_end`,
`agent_settled`) plus `entry_appended` are **frozen** — they may not be added
to, removed from, or re-meant within a taxonomy version — and everything else
is **informational**. A variant may be added within a version only if a reader
that ignores it still reaches the same terminal state and the same durable
transcript. Every informational variant in v1 clears that bar: `*_update` is
recoverable from the matching `*_end`, `queue_update` and `context_usage` carry
full snapshots so a missed one is replaced by the next, and the retry pair is
cosmetic because the outcome still arrives on the closing variant of whatever
was retried.

The version itself is a single integer declared once, in the session header,
and it has no minor component: within a version every permitted change is
additive, and additive change is invisible to a conforming reader, so a minor
would be a number nobody could observe. A reader that sees a version it does
not know refuses at line one rather than misreading the rest of the stream.

## Considered options

- **Per-event `v`**, mirroring the per-entry `v` of the session format. Rejected
  because the two formats differ in lifetime, not in style: an entry is stored
  and reread years later by an arbitrary binary, so it must carry its own
  version, while an event is read once by one reader in one sitting. Repeating
  the version on `message_update` costs bytes on the highest-frequency variant
  of the stream and buys nothing.
- **No version field at all in v1**, as the configuration format chose.
  Rejected because configuration has no external consumer and the event stream
  does; declaring an integer is not the migration machinery the project values
  warn against, and there is none in v1.
- **A second, narrower union projected for the headless consumer.** Rejected
  because the in-process payload had already been bounded on the headless
  consumer's behalf when tool-execution updates were capped at a tail window —
  a cost only worth paying if there is one union.

## Consequences

Adding a lifecycle pair later — a checkpoint, say — is a new taxonomy version,
not an additive change. That is the price of the tolerance rule being provable,
and it is deliberate: a consumer that silently drops a new terminal state is
the failure this rule exists to prevent.

The frozen set and the recoverability rule are not prose. The frozen set is a
list in code, and a conformance test drives a reader built for version N
against a stream carrying every N+1 informational variant, asserting it reaches
the same terminal state and the same transcript.

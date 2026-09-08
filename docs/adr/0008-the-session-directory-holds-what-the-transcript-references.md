# The session directory holds what the transcript references

A session's on-disk files must die together, because the transcript references
them: an `Image` block names a blob, a truncated tool result names a spill file,
and an operation's outcome is durable in the sidecar before it is in the JSONL.
If any of them outlives or predeceases the transcript, the transcript is either
lying or lossy.

Two closed decisions had already reached for the same mechanism independently —
the session is a **directory** so deletion is one call, and blobs live inside it
so they "inherit that with no new mechanism" — but neither stated it as a rule,
so the next file placed itself elsewhere and split the session across two XDG
roots. The rule is therefore stated rather than left to be re-derived:

> Everything the transcript references lives inside the session directory.
> Everything that references nothing, and that nothing references, lives outside
> it.

The test is **reference**, not regenerability and not size. A spill file is
regenerable in spirit and can reach 100MB, and it is still inside, because a
truncation marker points at it. The frame-writer debug tap and the diagnostics
log are both derived from a session and are still outside, because nothing in
the transcript names them — they take the session id only as a filename
disambiguator.

Rejected: placing files by whether they are user-valuable. That is the reading
that produced the split. It is a judgement made per file, at the moment the file
is invented, by whoever invents it — which is exactly when the deletion
invariant is least visible.

## Consequences

- The one-item property becomes structural. A new session-scoped file inherits
  co-location, the single trash call, and the sidecar's lifetime guarantee
  without anyone remembering to grant them.
- The subdirectories of a session directory are a **closed enum**, and it gates
  **fork**, not cleanup. Deletion needs no exhaustiveness — it is one directory.
  Fork does: fork copies entries verbatim, so it must copy the files those
  entries reference, or deleting a source breaks its fork. A new subdirectory
  breaks the build until someone decides whether fork copies it.
- The rule reaches past the session. Anything deriving a file from a session id
  must apply the test and land on one side deliberately, which is a constraint
  on every surface that has not shipped yet, not only on the ones that have.
- The session id does **not** address the directory: the path is bucketed by a
  key derived from the cwd. Nothing may build an id-to-path index and promote it
  to a source of truth.
- The worst case per session is now bounded by the spill cap times the number of
  operations that spilled, in a root the user considers valuable. Accepted: the
  cap exists to stop one wrong command from filling a disk, not to budget a
  session, and the user's remedy is a single deletion.

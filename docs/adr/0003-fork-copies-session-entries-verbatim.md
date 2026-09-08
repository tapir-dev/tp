# Fork copies session entries verbatim

A fork or clone writes a new session file that begins with a **verbatim copy** of
the source entries, ids preserved, rather than referencing the session it came
from. The same `entry_id` then exists under two `session_id`s, which is what makes
`(session_id, entry_id)` the address rather than `entry_id` alone. The
`forked_from` pointer in the new session's header is provenance only; nothing
dereferences it to load a session.

## Why

`(session_id, entry_id)` has to stay stable across fork and clone — an address
that does not survive branching makes any later search projection unbuildable —
and entry ids are minted once at intent and never regenerated. Copying satisfies
that structurally: the id in the fork *is* the id in the source, because the
bytes were copied. Nothing has to enforce it.

Exactly one link changes in the copy: the first copied entry's `parent_id`
becomes the new session header's id. Every other `parent_id` is untouched, which
is what preserves the tree shape.

## Considered options

- **Reference the source session.** Rejected on three counts. Loading stops being
  "read one file" and becomes a transitive walk, so a chain of forks is a
  resolution graph. Deleting a source breaks every fork of it — badly, because
  deletion prefers the system trash, so the source disappears from view while
  still existing on disk. And the address that had to stay stable would then
  depend on another file still being there.
- **Regenerate ids in the copy.** Rejected outright: it is the failure the
  stability requirement exists to prevent.

## Consequences

Disk duplication is real but bounded by the length of the copied span, in a
format that is plain text.

There is deliberately **no durable leaf pointer** anywhere in the design, and it
follows from the same reasoning. The leaf is the last node in file order, so a
copied file carries its own leaf with it and cannot disagree with a pointer kept
elsewhere. Tree navigation and `reset-leaf` are in-memory cursor operations; the
next append records the move exactly, by its `parent_id`. The cost is that
navigating and quitting without appending loses the cursor position — it loses no
content, and a reader who expects to find where the leaf is persisted should stop
looking.

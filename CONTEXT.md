# tp

A single-binary terminal coding agent whose every user-facing surface is data
rather than code.

## Language

### Sessions

**Entry**:
One line of a session's JSONL file, and the unit everything in a session is
addressed by. Identified across the whole product by the pair
`(session_id, entry_id)`.
_Avoid_: Record (means something narrower here), row, event, item

**Envelope**:
The fixed set of keys every entry carries regardless of its type — `id`,
`parent_id`, `timestamp`, `type`, `v`, `body` — readable without interpreting
the body. Frozen for all time, because it is the one part no version field can
describe.
_Avoid_: Header (means the `session` entry here), wrapper, metadata

**Node**:
An entry with a non-null `parent_id`, and therefore part of the conversation
tree. Branch-scoped: a fork taken before a node does not inherit it.
_Avoid_: Tree entry, conversation entry

**Session record**:
An entry with a null `parent_id` and a type other than `session`. Scoped to the
whole session rather than to a branch, and resolved last-wins.
_Avoid_: Annotation, metadata entry, sidecar entry

**Leaf**:
The tip of the active branch: the last node in file order. It is derived, never
stored.
_Avoid_: Head, tip, cursor

**Active branch**:
The chain of nodes from the leaf back to the root, and the only part of a
session that becomes model context.
_Avoid_: Current thread, main line, active path

**Fork**:
A new session whose file begins with a verbatim copy of an earlier span of
another session's entries, ids preserved.
_Avoid_: Copy, split, checkout

**Clone**:
A new session that duplicates the active branch of another as-is, discarding
its other branches.
_Avoid_: Duplicate, snapshot

**Tree navigation**:
Moving the leaf within the same session, without creating a file. The third
branching operation alongside fork and clone, and the only one that leaves no
trace until something is appended.
_Avoid_: Rewind, checkout, time travel

**Branch summary**:
The entry hung at a new leaf after tree navigation, recording a summary of the
span that was abandoned and pointing back at the leaf that was left. A distinct
mechanism from compaction, which cuts context rather than annotating a move.
_Avoid_: Checkpoint, snapshot, summary (ambiguous with compaction's)

**Accumulator**:
The cumulative set of files read and modified, carried on every entry that
summarizes, so that the newest one is always complete. Unions across repeated
summarization and across branches; never resets.
_Avoid_: File list, tracker, manifest

**cwd key**:
The directory name that buckets a working directory's sessions on disk. A
readable slug plus a hash, derived and never parsed back — the authoritative
working directory lives in the session's own header.
_Avoid_: Path hash, mangled path, session key

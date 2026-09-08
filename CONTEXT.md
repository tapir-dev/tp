# tp

A single-binary terminal coding agent whose every user-facing surface is data
rather than code.

## Language

### Tool execution

**Draft**:
The complete set of tools the model is told about, as one immutable value
derived from configuration, directory trust, and the active skills. It is
rebuilt from scratch whenever any of those changes, and snapshotted per turn, so
a call always settles under the same draft that produced it.
_Avoid_: Registry (implies register/unregister, which do not exist), tool list,
catalogue

**Descriptor**:
The data half of a tool: name, description, argument schema, replay policy, and
whether it mutates files. Carries no behaviour, and is the only part the model
ever sees.
_Avoid_: Definition, spec, manifest

**Disabled**:
Absent from the draft, and therefore absent from the system prompt and not
callable. There is no state in which a tool is described to the model but
refused on call.
_Avoid_: Off, hidden, restricted

**Source truncation**:
Cutting a tool's output where the bytes are produced, keeping a head and a tail
with a marker between them, once it passes 50KB or 2000 lines. Distinct from
compaction elision.
_Avoid_: Truncation (ambiguous: two exist), clipping, trimming

**Compaction elision**:
Shortening an already-recorded tool result when serialising history for a
summarisation request, so that request cannot blow its own budget. Distinct from
source truncation, and applied to a different copy of the same text.
_Avoid_: Truncation (ambiguous: two exist), summarisation

**Spill file**:
The on-disk destination for output past the source-truncation limit, named by
`full_output_path` on the result so the model can read the part it was not
given. Lives with the session, not with the operation, and is bounded in its own
right.
_Avoid_: Overflow file, log, dump

**Mutation queue**:
The per-path serialisation of file-mutating tool calls, keyed on the
canonicalised path and ordered by position in the tool call list. It converts a
silent lost update into a visible failure; it is not a lock, and nothing waits
on it except a mutation.
_Avoid_: File lock, write lock, path mutex

**Publication tick**:
The session-owned interval at which accumulated tool output becomes an update on
the event stream. Owned by the session rather than by the renderer, because
headless has the tick and no renderer.
_Avoid_: Frame (belongs to rendering), poll, refresh

**Replay policy**:
A tool's declaration of what an interrupted call should tell the model — that it
is safe to retry, or that the external outcome is unknown. It does not authorise
the harness to re-run anything.
_Avoid_: Idempotency, retry policy, safety class

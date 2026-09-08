# tp

A single-binary terminal coding agent whose every user-facing surface is data
rather than code.

## Language

### Session storage

**Session directory**:
The one directory holding everything a session's transcript references — the
JSONL, the sidecar, blobs, spill files — and the unit of deletion, so a session
is one item in the trash rather than several. Its path is bucketed by a key
derived from the cwd, so the session id alone does not address it.
_Avoid_: Session folder, session path, session store (that is the API over it)

**Spill file**:
The file a tool's output overflows into once it crosses the truncation limit,
named by the operation that produced it and pointed at by the truncation marker
in the tool result. Lives as long as the transcript that references it, not as
long as the operation that wrote it, because the model may read it many turns
later.
_Avoid_: Overflow file, output file, dump, tool log

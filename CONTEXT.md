# tp

A single-binary terminal coding agent whose every user-facing surface is data
rather than code.

## Language

### Messages

**Message**:
The entry type carrying one turn of the conversation, and the only entry type
whose body is a tagged union. Its shape is fixed by its role.
_Avoid_: Turn (a turn is one assistant response plus its tool calls), chat
message, prompt

**Role**:
The discriminant of a message — `user`, `assistant`, `tool_result` or `shell` —
and the single field every rule about a message is checkable against. Distinct
from the role a dialect puts on the wire, which it is mapped to.
_Avoid_: Kind, message type, speaker

**Content block**:
One element of a message's ordered content array: text, thinking, a tool call,
or an image. Only the last block of a message can be incomplete, which is what
makes partiality positional rather than a flag.
_Avoid_: Part, segment, chunk, content item

**Attestation**:
A provider's original content block, kept verbatim and tagged with the dialect
that minted it, so a surface demanding its own bytes back receives them
unchanged rather than re-serialized.
_Avoid_: Signature (that is one provider's name for what an attestation
carries), raw block, provenance

**Blob**:
Binary content addressed by the hash of its bytes and stored inside the session
directory, referenced from a content block rather than embedded in it.
_Avoid_: Attachment, asset (means a bundled product file here), file

**Shell message**:
The transcript record of a command the user ran directly, outside the agent
loop. Carries whether it reaches the model, because the brief requires both a
variant that does and one that does not.
_Avoid_: Bash message, command output, terminal message

### Interruption

**Frame**:
One durable, normalised record of a single content-block delta, written to the
sidecar during streaming. Expressed in `tp`'s own vocabulary, never the
provider's, so its meaning does not depend on the dialect version that wrote it.
_Avoid_: Event, chunk, token, stream record

**Fold**:
Reconstructing an interrupted assistant message from its frames at recovery. A
pure function of the frames alone.
_Avoid_: Replay, recovery, reconstruction

**Frame degradation**:
Losing frames that had already been received, because backpressure stopped the
sidecar append. The third and last thing in this product that content can lose,
alongside source truncation and compaction elision, and deliberately not called
truncation.
_Avoid_: Truncation (means two other things here), frame loss, dropping

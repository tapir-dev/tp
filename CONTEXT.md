# tp

A single-binary terminal coding agent whose every user-facing surface is data
rather than code.

## Language

### Events

**Event**:
A value published on the event stream: the one vocabulary `tp` versions and
promises to an external consumer. Carries content, which is what separates it
from a span.
_Avoid_: Message (names an entry type here), notification, update, signal

**Event stream**:
The ordered sequence of events for one session. One stream serves both the
in-process renderer and the headless consumer; the headless surface adds an
envelope around it and never a second vocabulary.
_Avoid_: Feed, channel, bus, event log

**Lifecycle variant**:
An event variant that opens or closes something — a run, a turn, a message, a
tool execution, a provider request, a compaction. The frozen set: no lifecycle
variant may be added, removed, or re-meant without a new taxonomy version.
_Avoid_: Boundary event, control event

**Informational variant**:
An event variant a conforming reader may ignore and still reach the same
terminal state and the same durable transcript. The only kind that may be added
within a taxonomy version.
_Avoid_: Optional event, auxiliary event

**Taxonomy version**:
The single integer, declared once in the session header, naming which event
vocabulary a stream speaks. Has no minor: within one version every change is
additive, and additive change is by construction invisible to a conforming
reader.
_Avoid_: Schema version, protocol version, `v` (names the per-entry body
version)

**Entry announcement**:
The rule that exactly one event announces any given entry, carrying that
entry's envelope and body verbatim. A message is announced by `message_end`;
every entry type without a lifecycle of its own by `entry_appended`.
_Avoid_: Entry event, append notification

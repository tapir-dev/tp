# tp

A single-binary terminal coding agent whose every user-facing surface is data
rather than code.

## Language

### Headless

**Stream header**:
The first line of a headless stream, declaring the protocol version and the
session it belongs to. It is not an event, and it is not the transcript's
`session` entry.
_Avoid_: session header (that names the first entry of `session.jsonl`), preamble, banner

**One-shot run**:
A headless invocation carrying a single prompt, which streams JSON lines and
terminates. Distinguished from the deferred bidirectional surface by having no
command channel.
_Avoid_: print mode, batch mode, non-interactive mode

**Protocol version**:
The single integer versioning a headless stream in its entirety — framing, the
stream header, the command and response grammar, the exit codes, and the event
union together.
_Avoid_: taxonomy version, schema version

**Rejection**:
A response refusing a command on the command's own terms, before any run comes
into existence. Distinct from a run that started and failed.
_Avoid_: error, failure

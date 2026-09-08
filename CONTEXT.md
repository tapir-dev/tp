# Context

## Glossary

### Diagnostics

**Diagnostic**:
One record emitted through `tracing` for a human to read after something went
wrong. It may carry content — prompts, payloads, file contents, paths — is
local-only, and never reaches a sink. The sibling of a Measurement, which is
typed so that it cannot carry content at all; the two are deliberately separate
mechanisms and collapsing them is what ADR-0006 exists to prevent.
_Avoid_: log line, log event, trace (that is the tree of Measurements), span

**Diagnostics log**:
The file diagnostics are written to: one per run, not one per session, in the
`state` root outside any session directory, because nothing in a transcript
references it and it is read after something went wrong — including after the
session it describes has been deleted. The session id travels inside it as a
field rather than in its name, which is what survives a fork mid-run.
_Avoid_: log file, tp.log, session log (that is the transcript)

**Run**:
One execution of the `tp` process, from start-up to exit. Not a session: a run
may open several sessions as the user forks or switches between them, and a
session may span many runs as it is resumed. Diagnostics are scoped to the run;
the transcript is scoped to the session.
_Avoid_: invocation, process, launch, instance

**Frame tap**:
The debug capture at the frame writer, writing the raw byte stream and a
per-frame JSONL sidecar beside the diagnostics log. Named for what it taps
rather than for being a debug facility, because the provider tap is a second tap
on the same axis and "the debug output" would name neither. Scoped to the run
like everything else the axis writes, so the retention count reaches it.
_Avoid_: debug tap, ANSI dump, frame log

**Provider tap**:
The debug capture at the provider seam, writing one JSONL per run beside the
diagnostics log and the frame tap's files. Its unit is the Exchange rather than
the request, and it holds both the request as the seam received it and the
request as it was sent, because the bugs it exists to find live in the
difference between them.
_Avoid_: request dump, provider log, wire log

**Exchange**:
One request to a provider surface and the reply to it, taken together and
identified by an operation id and an attempt number. A reissue after a retry is
a second Exchange under the same operation id, not a continuation of the first.
The unit the provider tap captures, because a request without its reply names
what was sent and not why it failed.
_Avoid_: call, round trip, provider request (that is one half of it)

**Wire frame**:
One unit a transport splits a reply into before any dialect sees it: an SSE
event, or a record in a binary event stream. Distinct from a Frame, which is one
pass of the render loop — the two words met for the first time when the provider
tap had to write the former beside the frame tap's capture of the latter.
_Avoid_: frame, chunk, event (that is what a dialect decodes one into)

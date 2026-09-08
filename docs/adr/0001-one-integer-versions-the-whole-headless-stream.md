# One integer versions the whole headless stream

A headless stream is two things a consumer depends on at once: an envelope
(LF framing, the stream header, the command/response grammar, the exit codes)
and the event union carried inside it. They are owned by different decisions and
change for different reasons, so two integers were on the table. We chose
**one** — `protocol_version`, declared in the stream header, refused at line one
if unknown — because a consumer that must reconcile two independently moving
version numbers has to encode the compatibility matrix between them, and no
reader written against a stream ever wants a version it can satisfy on one axis
and not the other.

## Consequences

- A change confined to the envelope bumps the same integer as a change to the
  event union, so **a consumer that only reads events is invalidated by a
  framing change it does not care about**. This is the price of the single
  integer, and it is accepted rather than mitigated: there is no minor
  component, and no per-line version.
- The tolerance rule is what keeps the bump rare, and it now spans both halves:
  within a version a reader ignores an unknown event `type`, an unknown field on
  a known line, and an unknown value of an open enum such as a rejection
  `reason`. Only a change that a conforming reader cannot ignore is a bump.
- The name `taxonomy_version` no longer describes what the integer governs. It
  is renamed `protocol_version`, widening what it versions while leaving the
  mechanism — one integer, in the header, no minor, refuse at line one — exactly
  as it was.

# Diagnostics may carry content; credentials cannot

Telemetry and diagnostics are two mechanisms, and ADR-0006 made that split
enforceable on one side only: a measurement's attribute value type has no
free-string case, so attaching a prompt to a measurement fails to compile. This
ADR states the other side, because a rule that is enforced in one direction and
merely absent in the other reads as an oversight, and the next person to look
will assume diagnostics were forgotten rather than decided.

> A diagnostic may carry anything the process holds — prompts, completions, tool
> arguments and results, file contents, provider payloads and headers, paths.
> The one exclusion is a resolved credential, and it is enforced by the type
> rather than by review.

The permissiveness is doing work, not being tolerated. Diagnostics are where a
developer debugging a provider bug expects to find the payload, and a
diagnostics mechanism that excluded content would leave that developer with
nothing and no second mechanism to reach for. The exclusion is drawn at the one
value with no debugging fidelity to lose: a resolved secret is wrapped in a type
whose `Debug` and `Display` redact, so `tracing`'s `?` and `%` sigils cannot
print it at any level, including `trace`.

Rejected: excluding content by convention and documenting it. That is the shape
ADR-0006 rejected for measurements, for the reason that applies here unchanged —
a security property living in prose has already failed. The difference is that
here the convention would have been the *permissive* one, which is worse: it
fails silently in the direction nobody audits.

Rejected: one mechanism with a content filter. Collapsing telemetry and
diagnostics is what ADR-0006 exists to prevent, and a filter is the retrofit it
names — the day an exporter is attached to the `tracing` subscriber it takes the
content along with everything else.

## Consequences

- The diagnostics log is a sensitive artifact in its own right. It sits in the
  `state` root next to persisted trust decisions, with no transcript beside it
  to inherit sensitivity from, so it carries mode `0600` as a rule local to this
  axis.
- Anything that ships the log inherits that sensitivity in full. A bug-report
  gesture that attaches it is attaching prompts, file contents and provider
  payloads, and owes the user that statement before it sends.
- No exporter may be attached to the `tracing` subscriber. The subscriber is
  constructed in exactly one place in `tp`, which is the same shape as the
  single point where an HTTP client can be constructed: the invariant is a gate
  rather than a warning.
- The credential wrapper is load-bearing outside diagnostics too. Once `Debug`
  redacts, a resolved secret cannot reach a panic message, an error chain, or
  the frame-writer tap either, and none of those had a rule of their own.
- The exclusion is a closed list of one. A second entry is a decision, not a
  patch: every addition narrows the mechanism whose whole value is that it does
  not narrow.

# A query verb's envelope is the process boundary

> ADR numbers collide across the unmerged wayfinder branches: `0015` through
> `0019` are each claimed by more than one branch. This file takes `0020` to
> stay clear of every number currently in flight; renumber on landing if the
> merge order makes a lower one free.

`tp run` streams LDJSON behind an envelope: a `protocol_version` integer, a
`stream_header` line, and a `type` tag on every record. The query verbs — `tp
config get`, `tp config schema`, `tp assets list`, `tp assets which` — carry
none of it. Under `--json` each emits one bare JSON object on stdout, on one
line, with no envelope, no version integer, and no type tag.

The two surfaces differ in what their consumer can see. A headless stream is
read by a process that did not necessarily start `tp`, that may attach to a
stream already in flight, and that cannot ask the producer anything: the
version has to travel in band, on line one, or it does not travel at all. A
query verb is read by the process that just invoked it. That process knows
which binary it ran, can run `tp --version`, and gets an exit code the stream
cannot offer mid-flight. Everything the envelope carries is therefore already
available across the process boundary — identity from the invocation, version
from the binary, outcome from the exit status — so adding an envelope would
have every query verb pay a line of framing for a signal the caller already
holds.

## Considered options

**Mirror `tp run`'s envelope on the query verbs.** Rejected on the above: it
buys the caller nothing it cannot already get, and it would make the smallest
possible answer — one key, one value — the larger part framing.

**Drop the envelope from `tp run` instead, for one product-wide shape.** Not
available. Its consumer genuinely cannot ask, which is the whole reason the
envelope exists there.

## Consequences

- **Renaming or retyping a field in a query verb's output is breaking, with no
  in-band signal.** The tolerance promise runs one way only: a consumer must
  ignore fields it does not know, and we must not remove or retype one outside
  a major version of the binary. There is no line one to refuse at.
- **The exit code is load-bearing, not advisory.** `0` and `1` both put JSON on
  stdout — a negative answer is an answer — and `2` leaves stdout empty. That
  keeps the headless consumer rule, *empty stdout ⇒ read stderr*, true across
  both surfaces instead of needing a second rule for the query verbs.
- **Query verbs and `tp run` do not share an exit-code space.** `2` is a usage
  error to a query verb and `cancelled` to `tp run`. A caller always knows
  which subcommand it invoked, so unifying the two spaces would have meant
  amending a closed decision to serve no consumer. This is deliberate, and
  recorded here so it does not read as an oversight.

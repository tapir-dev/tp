# The removed text never crosses the event stream

Clearing or discarding a delivery lane returns the removed text to the editor as
a transfer inside the process that owns the editor. It is never a field on
`queue_update`, and never an event of its own. On the deferred bidirectional
control surface it is the **response to the `clear queue` command**, not
something on the stream.

## Why not a field on `queue_update`

The event taxonomy splits its variants in two. Lifecycle variants are frozen;
informational variants may be added within a version **only if a reader that
ignores them still reaches the same terminal state and the same durable
transcript**. That is stated as a proof rather than a hope, and every v1
informational variant was checked against it. `queue_update` clears the bar for
one specific reason, written down at the time: it *carries a full snapshot, so a
missed one is replaced by the next*.

The removed text is a single-use payload. It is emitted once, at the moment the
lane is emptied, and no later snapshot reproduces it. A reader that dropped that
one event would lose the text permanently. Putting it on `queue_update` would
therefore convert a variant whose entire safety argument is *"the next one
replaces it"* into the carrier of something nothing replaces — and would do it
silently, since the tolerance rule is about ignoring unknown fields and would
raise no objection.

A new informational variant fails on the same sentence, for the same reason. The
bar does not care which variant carries the unreproducible value.

## Why nothing is lost by keeping it off the stream

Run-scoped lanes are in memory, in the process that owns the editor. Whatever
empties a lane and whatever receives the text are therefore the same process,
and the transfer needs no protocol at all. A headless consumer has no editor to
return text *to*, so the stream never had a recipient for this value.

The brief's wording turns out to be exact rather than loose: *clearing the queue
**returns** the removed text so the UI can restore it into the editor*. "Returns"
is the verb for a command response, which is what the control surface will use
when it ships, and the accept-then-stream contract already keeps command
responses and the event stream as separate channels for separate things.

## Considered options

- **A `removed` field on `queue_update`.** Rejected above.
- **A dedicated informational variant.** Rejected above.
- **A lifecycle variant.** Rejected outright. Adding a lifecycle pair is a new
  taxonomy version, which is an absurd price for a UI convenience, and the value
  is not a terminal state.
- **Emit the text nowhere and let it be lost.** Rejected: it is the failure the
  clear-returns-text rule exists to prevent, and a discard the user did not ask
  for is the case where it matters most.

## Consequences

- **`queue_update` stays purely a snapshot of the three lanes**, and its
  recoverability argument stays true as written.
- **The rule generalises to a test.** Before any value is added to an
  informational variant, ask whether a reader that missed it can recover it from
  a later event of the same variant. If not, the variant is the wrong carrier
  however convenient it looks — and the tolerance rule will not catch the
  mistake, because ignoring an unknown field is exactly what it licenses.
- **The TUI and the control surface deliver this value by different means**, and
  that asymmetry is correct rather than an inconsistency to be smoothed: one has
  an editor in the same process, the other has a caller waiting on a response.

## Note on numbering

ADR numbers collide across the unmerged wayfinder branches. This file takes
`0016` on the same assumption every other branch has made — that numbers are
reconciled when the branches land, not before.

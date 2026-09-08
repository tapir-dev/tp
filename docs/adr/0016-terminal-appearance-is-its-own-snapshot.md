# Terminal appearance is its own snapshot

Whether the terminal is light or dark is held as a snapshot of its own — one
value, `Dark`, `Light` or `Unknown`, carrying provenance — beside the
configuration snapshot, the capability snapshot and the model registry. It is not
a field of the capability snapshot.

## Why it cannot live in the capability snapshot

The capability snapshot is replaced whole and never amended, and it is
re-observed on exactly three triggers: process start, `SIGCONT`, and the live
reload command. Re-observing it means running the start-up handshake again, and
the handshake is the only moment `tp` may ask the terminal anything — after it,
the event reader owns the tty and a second questioner would take the user's
keystrokes for its own answers.

An appearance change arrives as a notification with no question attached. There
is no way to fold that into a snapshot whose only update path is a batch of
questions that may not be asked twice. Putting appearance in the capability
snapshot would force a choice between amending a snapshot that is documented as
never amended in place, and re-asking at a moment the product forbids asking.

The contract points the same way. The capability snapshot holds everything known
about **what the terminal can express**, and the reason a definitionally
unmeasurable field was allowed to stay in it was that the frame writer asks one
question — *what may I emit?* — and that question needs one home. The terminal's
appearance is not something it expresses. It is how the far end looks, which the
theme resolver consults and the frame writer does not. A different question earns
a different home.

## Why a snapshot rather than a plain value

The product already carries more than one snapshot, and the rule that emerged is
one whole per source of knowledge, each replaced entire rather than diffed. The
model registry became a second snapshot on exactly this ground: two values with
two clocks, kept apart so that neither clock could drive the other. Appearance is
a third clock — the terminal's, which ticks when the user changes their colour
scheme and at no other time. Holding it as a snapshot puts it under a rule the
product already has instead of introducing a bare mutable value with no stated
replacement discipline.

It is a very small snapshot, and that is not an argument against it. The cost of
the shape is a type; the cost of not having it is a value that changes underneath
readers with nothing saying when.

## Consequences

- **The capability-override admission test settles where the config keys go.** A
  key belongs to the terminal table only if the capability snapshot has a field of
  that name carrying provenance. Appearance is not such a field, so there is no
  admissible terminal key for it, and the keys that govern it live on the
  appearance axis instead. The placement is forced rather than chosen.
- **Provenance is reused, and no sixth value is minted.** A direct answer or a
  background colour read back is `measured`. A sentinel that fires before either
  arrives, or a budget that expires, is `assumed` — already defined as having
  asked and heard nothing, which is exactly what the sentinel establishes sooner
  than a timeout could.
- **The settings browser shows it.** It already has a read-only section for
  values that were observed rather than configured, showing value and provenance;
  this is one more row, and it is the surface on which "why is my theme light?"
  has an answer.
- **A fourth re-observation trigger exists, and it belongs to this snapshot
  alone.** The capability snapshot's three triggers are untouched. The earlier
  refusal to add a fourth rested on change not being observable from inside the
  pane; a pushed notification is precisely that observation becoming available,
  so the trigger is admitted by that reasoning rather than against it — and it
  replaces this snapshot only.

## Note on numbering

See the numbering note on ADR-0015.

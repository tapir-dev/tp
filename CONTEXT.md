# tp

`tp` is a terminal coding agent whose every user-facing surface — keybindings,
themes, prompts, skills, context, sessions — is data rather than code. This
glossary fixes the vocabulary that data model is described in.

## Language

### Terminal input

**Protocol tier**:
Which keyboard encoding scheme is currently active, as one exclusive value on a
ladder from least to most expressive. A terminal sits on exactly one tier.
_Avoid_: protocol level, keyboard mode, CSI-u (ambiguous: it names three
different things and never a tier)

**Input capability**:
A single thing the keyboard can express, held independently of the tier that
usually implies it — whether a modified `Enter` is distinguishable from a plain
one, whether key releases are reported, whether `super` survives. A tier can be
high while a capability it normally grants is absent.
_Avoid_: feature, terminal feature

**Capability snapshot**:
Everything known about what the terminal can express, as observed at one moment
and taken as a whole, never amended in place — the protocol tier, the input
capabilities, the graphics capability and the cell size together. It is the only
thing binding resolution and image layout consult; a new observation replaces it
entirely.
_Avoid_: capability state, terminal profile, caps

**Provenance**:
How a value in a capability snapshot came to be known — measured, assumed after
no answer arrived, or set by the user. Distinguishes an absent capability from
an unknown one, which matters because the two degrade the same way but are
honest about different things.
_Avoid_: source, origin, confidence

**Binding chain**:
The ordered list of keys bound to one action, read as a preference order rather
than a set of equal alternatives.
_Avoid_: binding list, key list, fallbacks

**Reachable**:
Said of a key that the current capability snapshot can actually deliver. An
action resolves to the first reachable key in its binding chain.
_Avoid_: supported, available

**Orphaned action**:
An action whose binding chain contains no reachable key, so it cannot be invoked
at all in the current terminal. Orphaning is the one condition that earns a
message to the user; a missing capability no binding chain wanted is silence.
_Avoid_: unbound action, broken binding

### Terminal graphics

**Start-up handshake**:
The one batch of questions `tp` asks the terminal about itself, written whole and
answered whole before anything else reads from the terminal. It is the only
moment `tp` may ask; afterwards the terminal is being listened to for the user's
sake, and a second questioner would take the user's answers for its own.
_Avoid_: probe, negotiation, detection pass (each names a part and implies there
could be more than one)

**Sentinel**:
The one question in the handshake that every terminal is known to answer, placed
last so that its reply means the batch is over. It is what turns an unbounded
wait into a bounded one: what has not arrived by then is taken as unanswered.
_Avoid_: terminator, guard, fence

**Cell size**:
The size in pixels of one character cell — the conversion factor between the grid
`tp` composes in and the pixels an image is made of. Without it an image has no
expressible size, so it cannot be drawn at all.
_Avoid_: cell metrics, font size, character size, cell dimensions

**Graphics capability**:
Which image protocol, if any, the terminal can be asked to draw with. Held in the
capability snapshot beside the input capabilities and carrying the same
provenance, because "this terminal draws no images" and "we never heard back" are
different claims here too.
_Avoid_: image support, graphics protocol (names the thing, not the knowledge of
it)

**Placeholder box**:
What stands in for an image that cannot be drawn honestly, naming the file and
its dimensions instead. It is the deliberate alternative to guessing a cell size:
a stated absence rather than a picture at the wrong scale.
_Avoid_: fallback, stub image, broken image

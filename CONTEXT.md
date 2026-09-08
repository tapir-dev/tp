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
The full set of protocol tier and input capabilities as observed at one moment,
taken as a whole and never amended in place. It is the only thing binding
resolution consults; a new observation replaces it entirely.
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

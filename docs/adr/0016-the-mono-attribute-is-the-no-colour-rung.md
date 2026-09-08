# The mono attribute is the no-colour rung of a fallback chain

A theme role may declare a **mono attribute** — one of `none`, `bold`,
`underline`, `reverse`, `bold_underline` — which the frame writer applies
**only** at `ColorDepth::None`. It is mandatory on the three decoration roles
and optional everywhere else.

## Why a colour-only taxonomy does not survive `None`

Colour depth has three values, and `NO_COLOR` forces the bottom one, where the
frame writer emits no colour at all. Every role's fallback chain is required to
stay expressible at `Indexed256` *and* at `None`. Walking a chain of colours to
a root is expressible at `Indexed256`; at `None` it resolves to nothing, for
every role, identically.

For most roles that is the correct outcome — text is text. For the three
decorations it is a defect with a visible symptom: selection, search match and
current search match are ranges the driver paints over the assembled line, and
their whole content is *which* range you are looking at. The precedence between
them — search match, then current search match, then selection — is meaningful
only if the three are distinguishable, and under `NO_COLOR` they were not. The
chain terminated in silence and the invariant was satisfied on a technicality.

An attribute is the only thing left that survives with colour switched off, and
the terminal has had them the whole time.

## Why it is mandatory on decoration roles and optional elsewhere

The rule that catches the bug has to be the rule the build checks. A role
declared as a decoration cannot compile without a mono attribute, so the next
decoration added to the product — a lint underline, a diff marker, anything the
driver paints over a line it did not render — inherits the obligation instead of
rediscovering it. Everywhere else the field is optional, because a mandatory
attribute on all fifty-six roles would be fifty-three authors writing `none`.

The defaults are chosen so the three stay apart under the same precedence they
have in colour: `search_match_background` is `underline`,
`current_search_match_background` is `bold_underline`, `selection_background` is
`reverse`.

## Consequences

- **`mono` is not a second theme.** It is one field on a role, read at one depth,
  and it does not compose with the colour chain: at `None` there is no colour to
  fall back through, so the walk is not performed.
- **A theme author can set it.** The field is part of the theme file like any
  other, which means a theme aimed at a monochrome terminal is expressible
  rather than merely tolerable.
- **The HTML export block has no `mono`.** Export has no colour depth to
  degrade through, so the field would name a rung that cannot be reached.
- **The 16-colour rung remains out of v1.** Resolving it would require reading
  terminfo, a terminal-identity table under another name; a 16-colour terminal
  takes the 256-index approximation or a theme written in indices. `mono` is not
  a substitute for that rung and does not reopen it.

## Note on numbering

See the numbering note on ADR-0015: numbers are reconciled when the wayfinder
branches land.

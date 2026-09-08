# Fork crossterm for input parsing

`tp` depends on a forked `crossterm` 0.29.0, wired in through `[patch.crates-io]`,
carrying two small parser patches. Both are upstreamable and the fork is meant to
be deleted, not maintained.

## Why

`crossterm` 0.29.0 (2025-04-05) is the only published release and has been for
seventeen months. Two defects in its input parser block us, and neither can be
worked around from outside the crate: its reader internals are `pub(crate)`, so
there is no seam to filter bytes before they reach the parser.

1. **Any unrecognised `CSI ?` sequence wedges input permanently.** The parser
   returns "incomplete" rather than "unparseable", so the buffer never clears and
   every later keystroke is appended to it instead of being delivered. Only
   `CSI ? … u` and `CSI ? … c` are handled. The trigger is not something we send:
   recent `tmux` forwards colour-scheme change notifications unsolicited. A
   coding agent that silently and permanently stops accepting input is the worst
   failure mode we could ship.

2. **It cannot read the xterm form of modified keys**, `ESC[27;<mod>;<code>~`.
   It parses only the CSI-u form. Both `tmux` (>= 3.5) and `xterm` emit the xterm
   form *by default*, so this is the common case rather than a legacy corner, and
   it is exactly the encoding our middle protocol tier exists to read.

## Considered options

- **Wait for upstream.** Rejected: the fix for the first defect exists as an
  unmerged, unreviewed pull request, and the issues covering the reader seam have
  no proposed implementation at all. There is no date to wait for.
- **Reconfigure the multiplexer instead.** Rejected: the relevant option is
  server-scoped, so we would be silently rewriting the user's configuration for
  every pane of every session to suit ourselves.
- **Drop the middle protocol tier.** Rejected: `tp` expects to be run under a
  multiplexer, and that is precisely where the middle tier is the only tier
  available. Dropping it means the typical user loses modified `Enter`.
- **Hand-roll the whole input parser.** Rejected: it would buy independence at
  the cost of owning key encoding, mouse, bracketed paste, focus and resize
  parsing forever, to repair two small gaps in code that otherwise fits.

## Consequences

The fork is a liability with an expiry condition, so it needs an owner: both
patches go upstream as pull requests, and the day a release carries them the
`[patch.crates-io]` stanza is deleted. Anyone bumping the dependency must check
that first.

One capability stays closed regardless of the fork: `crossterm` does not
implement the keyboard protocol's associated-text flag, so that is out for v1.

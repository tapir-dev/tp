# The editor keeps the arrow keys in both rendering modes

Unmodified navigation keys drive the **editor** in fullscreen and in scrollback
alike. The transcript is scrolled with `page_up`/`page_down`, `ctrl+up`/`ctrl+down`
and `shift+home`/`shift+end`, and with the wheel in fullscreen.

This contradicts the brief, which asks for the opposite in fullscreen:
*"in fullscreen, unmodified navigation keys drive the transcript while their
modified variants drive the editor; outside fullscreen both drive the editor."*
The line is overturned rather than dropped, and the reason is recorded here.

## Why the brief's line does not close

A key event resolves along a context chain of three layers — focused component,
then owner, then `app` — with **first match winning, innermost to outermost**.
In fullscreen the chain is `editor` → `transcript` → `app`.

`editor` is layer 1. It is innermost. It wins `up` in fullscreen, and there is no
ordering in the model that lets the transcript take a key the editor also claims.

The overlay decision anticipated the objection and answered it with chain
*membership*: the driver knows the mode, so in fullscreen the chain includes
`transcript` and in scrollback it does not. That is true and it is not sufficient.
Membership is not precedence. Adding the transcript to the chain places it
*outside* the editor, which is the wrong side for winning an unmodified key.

Two escapes exist and both were rejected:

- **Mode-conditional default chains** — `editor.cursor_up` defaulting to `["up"]`
  in scrollback and `["alt+up"]` in fullscreen. This is expressible: defaults are
  already a runtime-selected table. But it makes the same action answer to
  different keys depending on a mode the user toggles at will, it turns the
  generated reference page into a six-cell matrix per key, and a user who rebinds
  `cursor_up` silently loses transcript scrolling in fullscreen with no diagnostic.
- **Reordering the chain by modifier** — resolving unmodified keys outermost-first
  and modified keys innermost-first. This is a second, contradictory precedence
  rule for the one thing the brief explicitly asked to have stated once.

## Why the editor is the right winner

The editor is **multi-line**. It has `cursor_up`, `cursor_down` and `newline`, so
`up` has real work to do inside it, in both modes. Giving that key to the
transcript would mean the cursor cannot leave the first line by the obvious
gesture while the caret is visibly blinking in the editor.

The transcript, by contrast, has **no keyboard selection at all**. Its selection
model is entirely mouse-driven — `shift`+press extends, double-click takes a word,
triple-click takes a line — and its remaining ids are `scroll_*`, `copy`,
`plain_text_open` and `search_open`. It is not a keyboard-focusable surface, and
its own id names — `scroll_page_up`, `scroll_top` — read as the PgUp/Home family
rather than the arrow family. In fullscreen the wheel already bubbles to it.

So the brief's routing rule protects a gesture the transcript was never given the
actions to use, at the cost of a gesture the editor genuinely needs.

## Consequences

The editor is the focused component inside the transcript surface at all times,
which makes it permanently innermost in fullscreen. Two invariants follow, both
build assertions:

- Every `transcript` key must be disjoint from every `editor` key, or the
  transcript id is unreachable. This is why `transcript.copy` is `alt+w` rather
  than the obvious `ctrl+shift+c` — which is doubly barred, since under legacy
  encoding that chord is byte-identical to `ctrl+c`.
- `transcript` may never bind a bare printable character. A bare `y` would resolve
  to `transcript.copy` and never reach text insertion, which would break typing in
  fullscreen. This is what makes a faithful Vim transcript preset impossible and
  is recorded there too.

The transcript is not left without keys. It is fullscreen-only, i.e.
alternate-screen-only, and VTE steals `shift+page_up`/`shift+page_down` and
`shift+home`/`shift+end` only on the normal screen — so in the one mode where the
transcript exists, those keys are delivered intact.

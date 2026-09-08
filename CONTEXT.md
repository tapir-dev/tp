# tp

`tp` is a single-binary terminal coding agent in Rust whose every user-facing
surface is data rather than code. This glossary carries the terms the project
has settled; it grows as decisions land.

## Rendering

**Line**:
One unit of rendered content occupying exactly one terminal row. The invariant
is load-bearing: all row arithmetic depends on a Line never wrapping.
_Avoid_: row, string

**Span**:
A run of text inside a Line under a single Style, optionally carrying a
hyperlink target or an image placement.

**Style**:
A theme role plus text attributes. Never a concrete colour — colour is resolved
at the frame writer, so a component cannot bake one in.
_Avoid_: colour, format, attributes

**Theme role**:
The named semantic slot a Style points at, resolved against the active theme.
_Avoid_: colour name, palette entry

**Committed line**:
A Line already written to the terminal and never repainted again. It belongs to
the terminal's scrollback, not to `tp`.
_Avoid_: scrollback line, flushed line, history line

**Live region**:
The block of Lines anchored at the bottom of the terminal that `tp` may still
repaint. Everything above it is committed.
_Avoid_: viewport, inline viewport, dock

**Commit**:
Moving Lines out of the live region into committed lines, giving up the right
to repaint them. Explicit when a transcript block finalises; forced when the
live region would exceed the terminal height.

**Anchor**:
The row at which the live region begins, tracked by counting the lines `tp`
emitted. Never queried from the terminal.
_Avoid_: cursor origin, saved position

**Frame**:
One pass of the render loop: the diff of a new Line vector against the previous
one, written between synchronized-output markers and flushed once.

**Frame writer**:
The single component permitted to write to the terminal. Owns synchronized
output, colour resolution, cursor placement and the debug tap.

**Terminal driver**:
The mode-specific half of rendering. The scrollback driver maintains an anchored
live region and commits; the fullscreen driver owns the whole viewport and never
commits. Components never see which one is active.

**Fingerprint**:
The per-Line hash the differential pass compares to find the first changed line.

**Component**:
A unit that renders to a Line vector for a given width, knowing nothing of the
mode it renders into.

**Cursor marker**:
The invisible Private Use Area codepoint a component emits at its logical cursor
position, so the frame writer can place the hardware cursor there for IME
candidate windows. Zero-width to the text utilities, stripped before output.
_Avoid_: caret, cursor position

**Scrollback mode**:
The default mode: no alternate screen, no mouse capture, native terminal
scrolling and search preserved.

**Fullscreen mode**:
The alternate-screen mode: fixed dock, scrolling transcript region, mouse
capture.

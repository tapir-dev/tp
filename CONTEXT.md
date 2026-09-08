# tp

`tp` is a single-binary terminal coding agent in Rust whose every user-facing
surface is data rather than code. This glossary carries the terms the project
has settled; it grows as decisions land.

## Overlays

**Overlay**:
A component the terminal driver composes over a surface, positioned by a layout
spec the component never sees. It lives entirely inside the live region or the
viewport, never over committed lines.
_Avoid_: popup, modal, floating window, dialog

**Overlay canvas**:
The rectangle an overlay's anchoring resolves against — the viewport in
fullscreen mode, the live region at its natural height in scrollback mode.
_Avoid_: parent, container, bounds

**Available extent**:
The largest rectangle an overlay could ever occupy — the viewport in fullscreen
mode, one row short of it in scrollback mode. Distinct from the overlay canvas,
which may be much smaller.
_Avoid_: max size, screen size, terminal size

**Anchor target**:
The rectangle or point an overlay's layout is resolved against: the overlay
canvas, a dock slot, another open overlay, or the cursor marker.
_Avoid_: parent, origin, reference

**Overlay handle**:
The programmatic grip on an open overlay, carrying focus, hide and close. Goes
inert once closed; every later call is a reported no-op.
_Avoid_: reference, id, token

**Visibility predicate**:
The declarative size constraints an overlay must satisfy against the available
extent to be shown. Evaluated once per frame; failing it hides the overlay
without disposing it.
_Avoid_: responsive rule, breakpoint, media query

**Hide**:
Withholding an overlay from the frame while preserving all of its state and its
place in the ownership stack. The reversible half of the pair with close.

**Close**:
The single teardown path for an overlay, releasing everything it holds in a
fixed order and leaving its handle inert. Irreversible.
_Avoid_: dismiss, destroy, dispose, unmount

## Input ownership

**Input ownership**:
The right to receive key events, held by exactly one surface or overlay at a
time. Distinct from focus, which selects a component _within_ the owner.
_Avoid_: focus, active, modal

**Ownership stack**:
The LIFO stack of entries eligible to own input. Only the topmost entry that is
neither suspended nor hidden owns it.
_Avoid_: focus stack, z-order, layer stack

**Owning overlay**:
An overlay that takes a place in the ownership stack when opened, and blocks
mouse hits on the rows it occupies.
_Avoid_: modal, focusable

**Transient overlay**:
An overlay that is pure paint: it never enters the ownership stack and never
consumes a mouse hit. This is what makes "a focused overlay retains input
ownership across transient UI" structurally true.
_Avoid_: toast, notification, ephemeral

**Suspended**:
The state of an ownership-stack entry that is still painted but no longer
receiving input, because another entry sits above it.
_Avoid_: blurred, inactive, background

**Binding context**:
The namespace of key bindings a focused component or ownership-stack entry
activates. Never a mode and never a component type.
_Avoid_: keymap, mode, scope

**Context chain**:
The ordered list a key event is resolved against — focused component, then
owner, then `app`. First match wins; suspended and hidden entries contribute
nothing.
_Avoid_: keymap stack, precedence list

## Mouse

**Hit target**:
The identity a Span carries so a cell can be resolved to something clickable —
either a hyperlink or an opaque action id. Carried in band, like the cursor
marker, so it survives slicing and reordering.
_Avoid_: click region, hotspot, hit box

**Hit chain**:
The path a mouse event bubbles along, innermost to outermost: hit target, then
the driver's laid-out regions, then unhandled. The same propagation shape the
context chain uses for keys.
_Avoid_: event path, hit stack

**Capture**:
The routing of every subsequent mouse event to one handler regardless of
position. Acquired only from a press and released unconditionally on the
matching release.
_Avoid_: grab, lock, drag mode

**Capture lost**:
The event delivered when a capture ends by something other than its release —
the capturing overlay closing, or a width change — so the handler can undo
partial state.
_Avoid_: cancel, abort

**Scroll view**:
A driver-laid-out region that consumes an otherwise unhandled wheel event, and
that owns the line vector a selection anchors into.
_Avoid_: scroll area, viewport, pane

## Selection and copy

**Anchor**:
A position inside a scroll view, held as block id, line index within that block,
and display column. Never a viewport coordinate, and never a flat index into the
scroll view's whole line vector — both slide under content that moves.
_Avoid_: cursor, offset, point, coordinate

**Block**:
The unit the driver assembles a scroll view's line vector from — one transcript
entry's rendered lines. The anchoring unit, because a block's height changes
independently of its neighbours'.
_Avoid_: chunk, section, item, node

**Selection**:
A range between two anchors, born and dying within one press, surviving scroll
but not a re-wrap and not a change to the block it anchors in.
_Avoid_: highlight, marked text, region

**Chrome**:
A Span that frames content rather than being content — a border, a gutter, a
padding run. Excluded from both copy and search, by one rule rather than two.
_Avoid_: decoration, ornament, styling

**Decoration**:
A range plus a theme role, applied by the driver over the assembled line vector
after the component cache and before the frame writer. Selection and search
matches are decorations; no component learns it is decorated.
_Avoid_: highlight, overlay, marker, annotation

**Kill ring**:
The editor's own bounded history of killed text, fed only by kill actions and
read only by yank. Distinct from the system clipboard in both directions: no
sync, no shared machinery.
_Avoid_: clipboard, buffer, copy history

## The transcript scroll view

**Follow tail**:
Not a mode but a predicate — the slice index sits at its maximum. New content
moves the slice only when the predicate already held, so scrolling away and back
detaches and reattaches without a flag to desynchronise.
_Avoid_: auto-scroll, stick to bottom, tail mode

**Scrollbar policy**:
Whether a scroll view paints its scrollbar: always, never, or only while the
content exceeds the viewport. It governs painting, never layout — the column is
reserved whenever the policy is not `hidden`, so the transcript's width cannot
oscillate.
_Avoid_: scrollbar mode, visibility

**In-transcript search**:
The fullscreen affordance that finds and highlights text in the transcript's
rendered lines. Distinct from session search, which searches stored sessions and
is out of v1 scope.
_Avoid_: search, find, filter

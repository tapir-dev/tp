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

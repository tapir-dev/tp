# tp

`tp` is a terminal coding agent whose every user-facing surface — layout, colors,
keybindings, tools, providers, models, prompts, skills, context, sessions — is
data rather than code.

## Language

### Assets

**Asset**:
A unit of data the product resolves at runtime rather than compiles in: a theme,
a prompt, a doc, a skill.

**Built-in asset**:
An asset that ships as part of the product itself, carried by the binary.
_Avoid_: bundled asset — the brief's term, ambiguous between the content and the
directory it might live in

**Asset root**:
A directory whose files overlay built-in assets of the same name.
_Avoid_: bundled asset directory, asset dir

**Scope ladder**:
The product-wide ordering of the sources an asset may come from, from built-in
at the bottom to a command-line flag at the top. One ladder governs every asset
kind.
_Avoid_: lookup order, precedence chain, search path

### Identity

**Identity**:
The single constant naming the product: the name it uses in paths, the name it
displays, its environment-variable prefix, and its directory name. A rebrand
changes this and nothing else.
_Avoid_: branding, product config, app config

### Trust

**Project trust**:
A per-directory grant deciding whether project-local inputs are loaded at all.
It is a gate on origin, not a sandbox: it does not restrict what tools may do
once granted.
_Avoid_: permission, sandbox, allowlist

### Skills

**Skill**:
A directory containing a `SKILL.md` file, holding instructions the agent loads
on demand.
_Avoid_: plugin, extension (an Extension is a separate mechanism), prompt

**Skill root**:
The directory that *is* a Skill. Every relative path written in a skill body is
interpreted against it.
_Avoid_: skill directory, skill folder

**Skill identity**:
The name a Skill is known and collides by: the name of its Skill root. Distinct
from the `name` frontmatter field, which is only a display label.
_Avoid_: skill name (ambiguous between the two)

**Discovery root**:
A directory `tp` searches to find Skills. Each carries a Scope and is either
tp-specific or an Interop path.
_Avoid_: search path, skills directory

**Scope**:
Whether a resource comes from the user or from the project. Project scope is
trust-gated; user scope is not.
_Avoid_: level, tier, global (say "user scope")

**Interop path**:
A Discovery root shared with other agent tools rather than owned by `tp`, so
that a Skill placed there is usable by all of them.
_Avoid_: shared path, common directory, cross-agent path

**Ancestor walk**:
Searching a Discovery root not only at the current directory but at each
directory above it, up to the repository root. It exists to make Skills held at
a monorepo's root visible from a package inside it.
_Avoid_: upward search, parent traversal

**Shadowing**:
What happens when two Skills share an identity: the one found first in traversal
order wins and the other is not loaded. Always warned about, never silent.
_Avoid_: overriding, collision (a collision is the condition; shadowing is the
resolution)

**Progressive disclosure**:
Admitting only each Skill's name and description into the system prompt as a
compact index, and loading a body only when that Skill is actually invoked. It
is what keeps the prompt budget honest as a library grows.
_Avoid_: lazy loading, on-demand loading

### Rendering

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

### Providers

**Surface**:
One addressable API endpoint shape, the unit the provider layer is keyed on. A
single vendor may present several: a vendor's native API, its managed-cloud
offering, and its legacy offering are three surfaces, and they disagree with
each other.
_Avoid_: provider — a vendor, not an endpoint; keying anything on it is already
wrong

**Dialect**:
Code that translates between the provider-agnostic request/response types and
one wire format. It has two halves: encoding a request into an HTTP body, and
decoding a stream of frames into provider-agnostic events. Several surfaces
share one dialect.
_Avoid_: adapter, driver, client — each implies one per surface

**Transport**:
Code that carries a dialect's body to a surface and splits the reply into
frames: how the request is addressed and signed, and how the response envelope
is framed. Chosen independently of the dialect, so a surface is a dialect paired
with a transport.
_Avoid_: HTTP client, backend

**Quirk row**:
The resolved per-surface, per-model data a dialect consults to encode a request:
field names, permitted enum values, minimums, and capability flags. Every cell
holds a decided value; where documentation does not settle one, the decided
value is the conservative one.
_Avoid_: quirk table — the table is the whole set of rows; a dialect consults one
_Avoid_: capabilities, feature flags

**Passthrough**:
A free-form map of sampling parameters merged verbatim into the request body,
user keys winning. Each dialect declares where in its body the merge lands.
_Avoid_: extra params, raw options

**Degradation**:
Rendering a stored entry into a form a destination surface accepts, when that
surface cannot represent the original. It happens while encoding a request and
never alters what is stored.
_Avoid_: conversion, downgrade — both suggest the stored form changes

### Overlays

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

### Input ownership

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

### Mouse

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

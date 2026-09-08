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

**Model source**:
The three-tier composition that produces a model's resolved entry: a compiled
built-in catalog, a network-refreshed disk cache, and user-authored overrides.
It is what hands the seam an already-resolved row; the seam never learns the
tiers existed. The network tier *discovers* — new ids and lifecycle dates —
far more than it enriches, because no surface publishes prices and one
publishes no context window.
_Avoid_: model registry — the registry is the published result, not the machinery
_Avoid_: catalog — one tier of three

**Estimated window**:
A context window standing in for one the source never supplied, taken as the
smallest window known for that surface. It is marked wherever it is shown,
because it drives the compaction trigger and a wrong one truncates silently.

**Model entry**:
A model's resolved metadata paired with its quirk row, keyed on a model
identity. Metadata and quirk row are separate values with separate authority:
the network tier may write metadata and may never write a quirk cell.
_Avoid_: model definition — a user writes a patch, not a definition

**Model identity**:
The pair of a surface and a model id, written `surface/model`. A bare model id
resolves only when unambiguous; where two surfaces carry the same id it is an
error naming the candidates, never a silent pick.
_Avoid_: model name — display text, not identity

**Patch**:
An entry in a merge stack carrying a glob predicate over the model id and a
partial set of cells. Ordered, last match winning. A user override is a patch
in the same stack, not a separate mechanism.
_Avoid_: override — names one tier's use of the general thing

**Selection list**:
The ordered pattern list naming which models participate in cycling. It is a
config array: globs expand, `!pattern` removes, `+path` and `-path` force. It
is *not* a patch stack, and it carries no per-entry data.
_Avoid_: model list, glob list — both blur it with the patch stack

**Catalog cut date**:
The date the built-in catalog's prices were last checked against a primary
source. Carried per priced model and asserted by the build, so staleness is a
failing test rather than a silent mischarge.

**Value expression**:
The resolved-at-request-time form a credential or header value takes: a
literal, an environment variable reference, or an argv command whose stdout is
used. One type; where it may be *stored* differs, since a header value is a
config key and a credential is not.
_Avoid_: secret, credential — the type also carries non-secret header values

**Availability**:
Whether a value expression is *configured*, and for the environment form
whether the variable is set. It is never a claim that resolution will succeed:
determining that for the command form would require executing it, which is the
one thing availability may not do.
_Avoid_: valid, working, reachable — all overclaim

**Resolution**:
Executing a value expression to produce its value. The only step permitted to
run a command, and the only one that may fail at request time.

**Auth attachment**:
How a resolved credential is placed on the request — a header name, or a query
parameter. It is data on the surface row, read by the transport. Resolving a
credential and attaching it are different jobs in different places.

**Contributor**:
The origin of a usage record: an assistant message, an LLM call made inside
tool execution, or a summarization call. Three variants exist in the type from
the start; v1 emits two.

**Context fill**:
How full the current context window is, derived from the last assistant
response. Distinct from lifetime totals, and explicitly absent — not zero —
between a compaction and the next assistant response.
_Avoid_: usage, tokens used — both collide with lifetime totals

**Rate set**:
A complete set of per-token prices, not a delta. A model carries an ordered
list of rate sets keyed on a minimum input-token count; the highest whose
threshold the request's input meets wins.
_Avoid_: pricing tier — names the threshold, not the thing selected

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
Everything known about what the terminal can express, as observed at one moment
and taken as a whole, never amended in place — the protocol tier, the input
capabilities, the graphics capability and the cell size together. It is the only
thing binding resolution and image layout consult; a new observation replaces it
entirely.
_Avoid_: capability state, terminal profile, caps

**Provenance**:
How a value in a capability snapshot came to be known, as one of five exclusive
claims: **measured** (we asked and read the reply), **declared** (the terminal or
the environment asserted it and we did not verify), **assumed** (we asked and
nothing came back), **default** (there was no way to ask, so a stated policy
applies) and **override** (the user set it). Distinguishes an absent capability
from an unknown one, which matters because the two degrade the same way but are
honest about different things — and keeps a value that was never measured from
claiming it was.
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

### Sessions

**Entry**:
One line of a session's JSONL file, and the unit everything in a session is
addressed by. Identified across the whole product by the pair
`(session_id, entry_id)`.
_Avoid_: Record (means something narrower here), row, event, item

**Envelope**:
The fixed set of keys every entry carries regardless of its type — `id`,
`parent_id`, `timestamp`, `type`, `v`, `body` — readable without interpreting
the body. Frozen for all time, because it is the one part no version field can
describe.
_Avoid_: Header (means the `session` entry here), wrapper, metadata

**Node**:
An entry with a non-null `parent_id`, and therefore part of the conversation
tree. Branch-scoped: a fork taken before a node does not inherit it.
_Avoid_: Tree entry, conversation entry

**Session record**:
An entry with a null `parent_id` and a type other than `session`. Scoped to the
whole session rather than to a branch, and resolved last-wins.
_Avoid_: Annotation, metadata entry, sidecar entry

**Leaf**:
The tip of the active branch: the last node in file order. It is derived, never
stored.
_Avoid_: Head, tip, cursor

**Active branch**:
The chain of nodes from the leaf back to the root, and the only part of a
session that becomes model context.
_Avoid_: Current thread, main line, active path

**Fork**:
A new session whose file begins with a verbatim copy of an earlier span of
another session's entries, ids preserved.
_Avoid_: Copy, split, checkout

**Clone**:
A new session that duplicates the active branch of another as-is, discarding
its other branches.
_Avoid_: Duplicate, snapshot

**Tree navigation**:
Moving the leaf within the same session, without creating a file. The third
branching operation alongside fork and clone, and the only one that leaves no
trace until something is appended.
_Avoid_: Rewind, checkout, time travel

**Branch summary**:
The entry hung at a new leaf after tree navigation, recording a summary of the
span that was abandoned and pointing back at the leaf that was left. A distinct
mechanism from compaction, which cuts context rather than annotating a move.
_Avoid_: Checkpoint, snapshot, summary (ambiguous with compaction's)

**Accumulator**:
The cumulative set of files read and modified, carried on every entry that
summarizes, so that the newest one is always complete. Unions across repeated
summarization and across branches; never resets.
_Avoid_: File list, tracker, manifest

**cwd key**:
The directory name that buckets a working directory's sessions on disk. A
readable slug plus a hash, derived and never parsed back — the authoritative
working directory lives in the session's own header.
_Avoid_: Path hash, mangled path, session key

### Tool execution

**Draft**:
The complete set of tools the model is told about, as one immutable value
derived from configuration, directory trust, and the active skills. It is
rebuilt from scratch whenever any of those changes, and snapshotted per turn, so
a call always settles under the same draft that produced it.
_Avoid_: Registry (implies register/unregister, which do not exist), tool list,
catalogue

**Descriptor**:
The data half of a tool: name, description, argument schema, replay policy, and
whether it mutates files. Carries no behaviour, and is the only part the model
ever sees.
_Avoid_: Definition, spec, manifest

**Disabled**:
Absent from the draft, and therefore absent from the system prompt and not
callable. There is no state in which a tool is described to the model but
refused on call.
_Avoid_: Off, hidden, restricted

**Source truncation**:
Cutting a tool's output where the bytes are produced, keeping a head and a tail
with a marker between them, once it passes 50KB or 2000 lines. Distinct from
compaction elision.
_Avoid_: Truncation (ambiguous: two exist), clipping, trimming

**Compaction elision**:
Shortening an already-recorded tool result when serialising history for a
summarisation request, so that request cannot blow its own budget. Distinct from
source truncation, and applied to a different copy of the same text.
_Avoid_: Truncation (ambiguous: two exist), summarisation

**Spill file**:
The on-disk destination for output past the source-truncation limit, named by
`full_output_path` on the result so the model can read the part it was not
given. Lives with the session, not with the operation, and is bounded in its own
right.
_Avoid_: Overflow file, log, dump

**Mutation queue**:
The per-path serialisation of file-mutating tool calls, keyed on the
canonicalised path and ordered by position in the tool call list. It converts a
silent lost update into a visible failure; it is not a lock, and nothing waits
on it except a mutation.
_Avoid_: File lock, write lock, path mutex

**Publication tick**:
The session-owned interval at which accumulated tool output becomes an update on
the event stream. Owned by the session rather than by the renderer, because
headless has the tick and no renderer.
_Avoid_: Frame (belongs to rendering), poll, refresh

**Replay policy**:
A tool's declaration of what an interrupted call should tell the model — that it
is safe to retry, or that the external outcome is unknown. It does not authorise
the harness to re-run anything.
_Avoid_: Idempotency, retry policy, safety class

### Events

**Event**:
A value published on the event stream: the one vocabulary `tp` versions and
promises to an external consumer. Carries content, which is what separates it
from a span.
_Avoid_: Message (names an entry type here), notification, update, signal

**Event stream**:
The ordered sequence of events for one session. One stream serves both the
in-process renderer and the headless consumer; the headless surface adds an
envelope around it and never a second vocabulary.
_Avoid_: Feed, channel, bus, event log

**Lifecycle variant**:
An event variant that opens or closes something — a run, a turn, a message, a
tool execution, a provider request, a compaction. The frozen set: no lifecycle
variant may be added, removed, or re-meant without a new taxonomy version.
_Avoid_: Boundary event, control event

**Informational variant**:
An event variant a conforming reader may ignore and still reach the same
terminal state and the same durable transcript. The only kind that may be added
within a taxonomy version.
_Avoid_: Optional event, auxiliary event

**Taxonomy version**:
The single integer, declared once in the session header, naming which event
vocabulary a stream speaks. Has no minor: within one version every change is
additive, and additive change is by construction invisible to a conforming
reader.
_Avoid_: Schema version, protocol version, `v` (names the per-entry body
version)

**Entry announcement**:
The rule that exactly one event announces any given entry, carrying that
entry's envelope and body verbatim. A message is announced by `message_end`;
every entry type without a lifecycle of its own by `entry_appended`.
_Avoid_: Entry event, append notification

### Session tree browser

**Session tree browser**:
The overlay through which a session's entry tree is inspected and the active
leaf is moved. It owns the in-memory leaf cursor; nothing it does is durable
until an append happens.
_Avoid_: history picker, transcript browser, tree view

**Spine**:
The active branch, rendered as a linear list of one-line rows. The browser's
primary axis: every other row hangs off it.
_Avoid_: main line, trunk, current path

**Branch point**:
A node with two or more children. The only place the tree fans out, since every
entry has exactly one parent.
_Avoid_: fork point, split, junction

**Stub**:
A single collapsed row hanging under a branch point, standing for one non-active
child and the abandoned span below it. Expanding a stub previews that span
inline and never moves the leaf.
_Avoid_: sibling row, branch entry, alternate

**Segment**:
A maximal run of spine rows between two consecutive branch points, with the root
and the leaf as terminal boundaries. What segment jumping moves between.
_Avoid_: section, chunk, span

**Row role**:
The closed vocabulary a browser row is classified into — `user`, `assistant`,
`tool`, `meta`, `opaque` — derived from the entry envelope plus a single body
field. Both the filter modes and the row previews are defined over it.
_Avoid_: kind, category, entry type

**Filter mode**:
Which row roles the browser shows: `all`, `no-tools`, `user-only`, or
`labeled-only`. A filter hides rows; it never folds them.
_Avoid_: view, display mode, filter level

**Fold**:
A user-created row standing for a hidden run of otherwise visible rows.
Computed over the rows the current filter leaves visible, and never created
automatically.
_Avoid_: collapse, group, summary row

**Label gutter**:
The right-aligned column carrying the label names that annotate a row's entry.
A label is a session record, not a node, so it never occupies a row of its own.
_Avoid_: tag column, badges, annotations

**Confirm flow**:
The whole sequence a confirm starts — leaf move, then the branch summarization
dialog when the abandoned span is non-empty — ending with the browser closing.
The browser closes when the flow completes, not when the confirm is pressed.
_Avoid_: commit, apply, accept

**Confirm precondition**:
One of the conditions a confirm requires: no run in flight, an empty editor when
a user-message prefill would land, and a writable session. Failing any one
reports the reason and leaves the browser open.
_Avoid_: guard, validation, check

**Abandoned span**:
The entries between the deepest common ancestor of the old and new leaf and the
old leaf. Empty exactly when the old leaf is an ancestor of, or equal to, the
new one — which is when branch summarization is skipped entirely.
_Avoid_: orphaned branch, dead branch, old path

### Selection and copy

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

### The transcript scroll view

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

### Messages

**Message**:
The entry type carrying one turn of the conversation, and the only entry type
whose body is a tagged union. Its shape is fixed by its role.
_Avoid_: Turn (a turn is one assistant response plus its tool calls), chat
message, prompt

**Role**:
The discriminant of a message — `user`, `assistant`, `tool_result` or `shell` —
and the single field every rule about a message is checkable against. Distinct
from the role a dialect puts on the wire, which it is mapped to.
_Avoid_: Kind, message type, speaker

**Content block**:
One element of a message's ordered content array: text, thinking, a tool call,
or an image. Only the last block of a message can be incomplete, which is what
makes partiality positional rather than a flag.
_Avoid_: Part, segment, chunk, content item

**Attestation**:
A provider's original content block, kept verbatim and tagged with the dialect
that minted it, so a surface demanding its own bytes back receives them
unchanged rather than re-serialized.
_Avoid_: Signature (that is one provider's name for what an attestation
carries), raw block, provenance

**Blob**:
Binary content addressed by the hash of its bytes and stored inside the session
directory, referenced from a content block rather than embedded in it.
_Avoid_: Attachment, asset (means a bundled product file here), file

**Shell message**:
The transcript record of a command the user ran directly, outside the agent
loop. Carries whether it reaches the model, because the brief requires both a
variant that does and one that does not.
_Avoid_: Bash message, command output, terminal message

### Interruption

**Frame**:
One durable, normalised record of a single content-block delta, written to the
sidecar during streaming. Expressed in `tp`'s own vocabulary, never the
provider's, so its meaning does not depend on the dialect version that wrote it.
_Avoid_: Event, chunk, token, stream record

**Fold**:
Reconstructing an interrupted assistant message from its frames at recovery. A
pure function of the frames alone.
_Avoid_: Replay, recovery, reconstruction

**Frame degradation**:
Losing frames that had already been received, because backpressure stopped the
sidecar append. The third and last thing in this product that content can lose,
alongside source truncation and compaction elision, and deliberately not called
truncation.
_Avoid_: Truncation (means two other things here), frame loss, dropping

### Terminal capability overrides

**Capability override**:
A configuration key that sets, by hand, one field of the capability snapshot.
Admission is the rule, not the topic: a key belongs here only if the snapshot has
a field of that name carrying provenance. A preference about what `tp` chooses to
emit is not a capability override however terminal-flavoured it sounds, because
there is nothing about the terminal it could be wrong about.
_Avoid_: terminal setting, capability flag, terminal option

**Resolution ladder**:
The ordered list of rungs an `auto` default is resolved through, each rung
stamping the provenance it earns, ending in a fallback that is stated rather than
left open. Every `auto` in the product is one of these, including the ones with a
single rung; an explicit override is always the first rung and short-circuits the
rest.
_Avoid_: fallback chain (taken by theme roles), detection order, precedence

**Colour depth**:
How much colour the frame writer may express, as one exclusive value: none,
indexed, or true colour. It is what a theme role is clamped to at resolution
time, so a theme never has to know which terminal it landed on.
_Avoid_: colour mode, colour support, palette size

### Telemetry

**Measurement**:
The unit of telemetry: one timed thing that happened, carrying a closed set of
attributes and an outcome. Seven kinds exist and the set is closed.
_Avoid_: Span (names the rendering type that carries a hyperlink target, an
image placement and a hit target), event (names the taxonomy of #15), metric

**Trace**:
The tree of measurements rooted at a single invocation. It is a shape, not a
stored artifact: nothing durable holds it in v1.
_Avoid_: Span tree, transaction, request tree

**Trace context**:
The ambient value naming the current trace and the measurement a new
measurement should hang under. Carries a trace id and a parent measurement id
and nothing else — deliberately no key/value payload, because that payload is
the one route by which excluded content could later re-enter.
_Avoid_: Baggage, span context, correlation context

**Attribute value**:
The closed enumeration of what a measurement attribute may hold: an id, a name,
a compile-time literal naming one of our own enum cases, a signed integer, a
float, a bool, or a duration. It has no free-string case, which is what makes
content exclusion a property of the type rather than of a rule.
_Avoid_: Tag, label, field, property

**Excluded origin**:
The three sources a string in a measurement may never come from: model output,
filesystem bytes, and provider payload. The content-exclusion invariant is
stated over origin rather than over shape, because a model id and a tool name
are both runtime strings and both legitimate.
_Avoid_: Untrusted input, PII, sensitive data

**Sink**:
Where measurements are handed when something is listening. v1 installs none, so
every measurement is constructed against a null sink and short-circuits.
_Avoid_: Exporter (names the deferred off-machine thing), collector, backend,
subscriber

**Vocabulary version**:
The single integer naming which measurement vocabulary a sink is being offered.
It is bumped only by a rename, a removal, or a change of meaning to an existing
attribute; adding a measurement kind or an attribute is free.
_Avoid_: Taxonomy version (names the event one, and is a different integer),
schema version, telemetry version

### Cancellation and the network

**Cancellation**:
The dropping of the future that owns the work, scoped to an invocation. It is
not a value, not a signal and not a token — which is what keeps it structurally
distinct from the trace context, since one is control flow and the other is
data.
_Avoid_: Abort (names the durable operation state of #12), interrupt, kill,
cancellation token

**Network gate**:
The single place in the product where an HTTP client can be constructed. Every
network capability is obtained from it, so disabling it disables every network
side effect by construction rather than by each caller remembering to ask.
_Avoid_: HTTP factory, client provider, connection pool

**Offline**:
The state in which the network gate hands out nothing. It forces the degraded
path that already has to work — the built-in catalog is a complete tier on its
own — so offline is not an error state and nothing reports a failure for it.
_Avoid_: Air-gapped, disconnected, no-network mode

### Configuration

**Axis**:
One configurable area of the product, owning exactly one reference page. An axis
declares which surface it occupies — a table in the main config file, a file
format of its own, or the environment — and the generator refuses any axis
without a page, any page without an axis, and any top-level table no axis claims.
_Avoid_: section, area, config group

**Config layer**:
One of the two sources the main config is composed from — the user's global
config and the project's config — deep-merged in that order. Composition by
merge is what distinguishes a config layer from an asset.
_Avoid_: config level, override level, config scope

**Snapshot**:
The whole merged configuration as a single immutable value, with every runtime
surface derived from it as a pure function. A reload replaces the snapshot
whole; nothing is ever patched in place.
_Avoid_: current config, live config, config state

**Provenance**:
The record, carried by every value in a snapshot, of where that value came from:
the layer, the file, and the position within it. It is what separates "this is
the default" from "someone wrote this", and it is what a relative path resolves
against.
_Avoid_: origin, source, defined-in

**Pattern list**:
A resource-path array, read as an ordered list of patterns rather than a list of
paths: globs expand, `!pattern` excludes, and `+path` / `-path` force a path in
or out regardless of the patterns around them. The operators order patterns
*within* one list; they never reach across config layers, where an array still
replaces its predecessor whole.
_Avoid_: path list, resource paths, include list

**Pending axis**:
An axis that is in scope but not yet decided, naming the ticket that owns it.
Distinct from a deferred axis, which is settled as out of scope and whose page
documents the seam it will one day attach to. The spec is not complete while any
axis is still pending.
_Avoid_: TODO axis, unspecified axis, stub

**Mirrored env entry**:
A row in the environment registry that sets an existing config key rather than
naming a variable of its own. It is the deliberate exception to "there is no
generic `TP_<KEY>` mapping": the exception is enumerated, one row per key that
earns it, so the registry stays a closed set and provenance stays a fact rather
than a translation table. A mirrored entry outranks the config file and is
outranked by `--set`.
_Avoid_: env override, env alias, TP_ variable

**Duration key**:
A config key whose value is a whole number of milliseconds. The unit lives in
the type and in the doc-comment, never in the identifier — `escape_timeout`,
never `escape_timeout_ms` — for the same reason a row count is spelled `height`.
Where a duration also carries a sentinel, its domain is `"auto"` or an integer,
and an explicit integer short-circuits the resolution ladder.
_Avoid_: timeout value, delay setting, `*_ms` key

# tp

`tp` is a single-binary terminal coding agent in Rust whose every user-facing
surface is data rather than code. This glossary carries the terms the project
has settled; it grows as decisions land.

## Session tree browser

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

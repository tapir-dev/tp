# tp

`tp` is a terminal coding agent whose every user-facing surface — layout, colors,
keybindings, tools, providers, models, prompts, skills, context, sessions — is
data rather than code.

## Language

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

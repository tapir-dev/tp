# tp

`tp` is a terminal coding agent whose every user-facing surface — layout, colors,
keybindings, tools, providers, models, prompts, skills, context, sessions — is
data rather than code.

## Language

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
tiers existed.
_Avoid_: model registry — the registry is the published result, not the machinery
_Avoid_: catalog — one tier of three

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

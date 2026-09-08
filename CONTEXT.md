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

# tp

A single-binary terminal coding agent whose every user-facing surface is data
rather than code.

## Language

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

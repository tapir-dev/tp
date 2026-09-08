# The telemetry vocabulary is native, not OpenTelemetry semantic conventions

`tp` defines a complete measurement vocabulary in v1 and emits nothing
off-machine, so the only consumer of the naming choice is an exporter that does
not exist yet. The obvious move is to adopt OpenTelemetry's GenAI semantic
conventions, so that exporter becomes a pass-through. We measured that option
and rejected it: the vocabulary is native, under a private `tp.*` namespace,
with a mapping table maintained beside it for whoever writes the exporter.

The rule for reuse is stability, not convenience. We adopt an OpenTelemetry
name only where the page defining it is marked `Stable`, which today means
`error.type` and nothing else. Every GenAI attribute is marked `Development`,
whose own definition reads "The component SHOULD NOT be used in production. The
component MAY be removed without prior notice." The conventions also left the
core semantic-conventions repository in v1.42.0 for a repository that has zero
releases and zero git tags, so there is no versioned artifact to pin against.
They have already renamed `gen_ai.system` to `gen_ai.provider.name`, moved
prompts and completions from events to attributes, renamed the token counts
once, and have a further breaking rename of `gen_ai.usage.cache_creation.*`
queued unreleased. Conforming to that today buys a pass-through exporter and
sells our own vocabulary's stability to a moving target.

The Rust ecosystem confirms the same conclusion from the other side: all sixty
`gen_ai.*` constants in `opentelemetry-semantic-conventions` were deprecated in
0.32.1 when upstream split the package, with no replacement crate, and
upstream's own issue on the subject records that there is no actionable path to
follow. Conformance would therefore mean hardcoded string literals and
`#[allow(deprecated)]` — the costs of a native vocabulary without its benefits.

Two consequences worth stating because they are visible in the attribute list.
There is no cost attribute anywhere in the conventions (the proposal is open and
unmerged), so ours is native by necessity rather than by choice. And
`gen_ai.response.finish_reasons` is an array, which our `stop_reason` is not:
arrays cost us nothing to avoid, buy nothing at one reason per response, and are
the attribute shape with the worst support in the Rust tracing ecosystem.

## Considered options

- **Full conformance now.** Rejected on the stability evidence above. The
  strongest argument for it — that a future exporter becomes free — is worth
  less than it looks, because a mapping table makes that exporter cheap rather
  than free, and the mapping table can be written against whatever the
  conventions have stabilised into by then rather than against today's snapshot.
- **Semconv-shaped names in a private namespace** (`tp.gen_ai.usage.input_tokens`
  and so on). Adopted in spirit and this is what the vocabulary looks like: it
  costs nothing to shape our names like theirs where the concept genuinely
  matches, and it makes the mapping table mostly mechanical. What we decline is
  the *commitment*, not the shape.
- **Reusing `session.id` and `db.*`**, both of which exist upstream and would
  collide. Rejected by the same stability rule: `session.*` is `Development`,
  and while `db.*` spans are Stable there is no transaction-level convention at
  all, which is precisely the part we needed.

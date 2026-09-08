# An image tool result splits into two messages on OpenAI Chat Completions

`ChatCompletionRequestToolMessageContentPart` is a `oneOf` with exactly one
member — text — so a tool result carrying an image has **no lossless
serialization** on that surface, and the runtime behaviour of sending one anyway
is undocumented, so it cannot be probed. Because `read` returns an image content
block, the OpenAI dialect emits the `role: "tool"` message with text declaring
the image, then — **after every tool message in the batch** — one `role: "user"`
message carrying each image as an `image_url` data URI in `tool_call_index`
order, each preceded by a text part naming its `tool_use_id`.

Rejected: a text placeholder alone, which turns reading an image into an
invitation to hallucinate; and failing the call, which would make a product
capability depend on the selected model, after the provider seam established
that changing surface is a change of view rather than a loss of content.

## Consequences

- This is the **only** point where the request contains a message the transcript
  does not. Transcript → request stops being one-to-one, and any code assuming
  otherwise is wrong here.
- The divergence is deterministic: the same session always produces the same
  prefix, so the KV-cache tail invariant is untouched.
- It is declared as a quirk-row cell rather than living silently in the encoder,
  so the behaviour is inspectable without reading the dialect.
- Emitting after the whole batch, rather than adjacent to each result, avoids
  OpenAI's tool-message adjacency rules, which no primary document states.

# Provider blocks are stored verbatim as attestations, keyed on dialect

Anthropic returns 400 unless a thinking block is echoed back **complete and
unmodified**, and from Fable 5.1 validates its signature against an unchanged
prefix; Gemini 3+ returns 400 when the first `functionCall` part's
`thoughtSignature` is missing, even at `MINIMAL`. Rebuilding those blocks from
our own types would be a standing bet that our serializer stays byte-exact
against two vendors forever. Instead, a `Thinking` or `ToolUse` block carries an
optional **attestation**: the provider's original JSON block kept verbatim,
tagged with the dialect that minted it. Encoding to that dialect emits the
attestation as-is; encoding anywhere else drops it and degrades to tagged text.
"Complete and unmodified" then holds by construction rather than by discipline.

The key is the **dialect**, not the surface: Anthropic signatures are portable
across the Claude API, Bedrock and Vertex, which share a dialect and differ only
in transport.

## Consequences

- `redacted_thinking` is not a separate block type. Anthropic's
  `display: "omitted"` — the default on most current models — returns empty
  `thinking` with a populated `signature`, structurally identical to it. One
  `Thinking { text, attestation }` covers both, and the distinction survives
  inside the attestation, where only the minting dialect reads it.
- `ToolUse` needs the slot as well, because Gemini hangs its signature on
  `functionCall` parts rather than on thinking.
- Thinking text is stored twice, typed and raw. Under the default the typed half
  is empty; where it is not, the duplication is accepted because transcripts are
  human-scale.
- Absence of an attestation means "cannot be echoed back", **not** "incomplete".
  Gemini does not strictly validate signatures outside `functionCall` parts, so
  a complete block can legitimately have none. Partiality is carried by position
  instead.

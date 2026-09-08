# Context fill is a reported base plus an estimated delta

The compaction trigger compares context fill against the model's window. That
figure is composed, never measured in one place: it is the **reported base** —
the provider's own token count for the last assistant response — plus a **delta
estimate** covering only the entries appended since.

`tp` embeds no tokenizer and calls no token-counting endpoint.

## Why not estimate the whole thing

A character-based estimate is not merely imprecise, it is **systematically low
by terms no scan of message text can see**. Tool schemas are one. Worse is the
tool-use preamble a vendor injects on its own: Anthropic publishes it per model
at 286 to 804 tokens, and it is non-monotonic across versions — Opus 4.7 costs
675 where Opus 4.8 costs 290 — so it cannot even be extrapolated from a
neighbouring release. Anthropic's own example makes the magnitude plain: an
identical user message counts 14 tokens with no tools and 403 with a single
trivial one. Images add hundreds to thousands each. Adaptive thinking varies per
request and is unpredictable in principle.

Every one of those terms is already inside the reported base. Composing confines
estimation to the delta, which is the entries appended since the last assistant
response — tool results and a user message, almost entirely text, which is the
one thing estimation is decent at.

## Why not count exactly, when two vendors will do it for free

Anthropic's `count_tokens` and Gemini's `countTokens` are free, accept the full
request shape, and have their own rate-limit buckets. They were still refused.

They cover two surfaces of four. OpenAI's counting endpoint exists only on the
Responses API, which is not the surface v1 speaks, and a generic
OpenAI-compatible base URL guarantees nothing at all. So the estimating path has
to exist regardless, and adding an exact path alongside it buys precision on
half the surfaces at the cost of maintaining both.

The cost is not only code. The trigger is checked after every tool batch, so an
exact count puts a network round trip on the hot path — with latency documented
nowhere, and Google's own guidance warning that counting is "fairly
memory-intensive" for large prompts and recommending a local tokenizer instead.
Paying that per tool batch to sharpen a number that is only ever compared
against a 16384-token reserve does not pay.

Bundling a tokenizer was refused on the same arithmetic. `tiktoken-rs` would
serve one surface of four at roughly 3.6 MB of vocabulary in the binary.
Anthropic has published no usable vocabulary since Claude 2.x — it removed the
file from its Python SDK in 0.39.0 and archived the TypeScript repository, and
its own README says the algorithm stopped being accurate at Claude 3. Gemini is
reachable only through Gemma vocabularies mapped to models in SDK source that no
prose documents, marked experimental and text-only. A tokenizer would not help
the backward walk either, which needs proportion rather than exactness.

## The normalisation the base requires

The reported base is not a field, it is a computation, because the surfaces
disagree about what their own number means. Anthropic's `input_tokens` counts
only what follows the last cache breakpoint: its documentation gives the example
of a 200K cached document reporting `input_tokens: 50`. OpenAI and Gemini
include cached tokens in theirs. Reading the field naively understates context
fill on Anthropic by the entire cached prefix — precisely on the long
conversations where compaction exists to help.

The rule lives as a **quirk row cell**, not a branch in code. It is a per-surface
divergence about wire semantics, which is what the quirk table is for.

## Two consumers, two requirements

The composition also settles something the brief conflates. The **trigger**
needs absolute accuracy, because it is compared against the window. The
**backward walk** needs only proportion, because it decides how much tail to
keep, and being wrong by a fifth means keeping slightly more or less — absorbed
by the reserve. Only the trigger earns the reported base; the walk uses the
heuristic alone.

## Why overflow is a net, not a trigger

Building compaction on catching the context-limit error was considered and
rejected on the evidence: Anthropic's error shape has no `code` field at all,
Gemini returns a catch-all `INVALID_ARGUMENT`, and OpenAI's
`context_length_exceeded` does not appear in its published error-code list. Two
of the three are reachable only by matching human-readable message text.

So `overflow` stays a last-resort net. Its discriminator is a quirk row cell
marked as undocumented, and a discriminator that stops matching degrades to an
ordinary turn error rather than to a loop. Anthropic's
`stop_reason: "model_context_window_exceeded"` — the one clean, documented,
programmatic overflow signal anywhere across the four surfaces — is mapped as a
`stop_reason` variant, which is already an open versioned enum for exactly this
kind of arrival.

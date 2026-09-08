# Model catalogue and pricing — what the four v1 provider surfaces actually expose

Companion to [`provider-quirks.md`](./provider-quirks.md), which covers auth and request/response
quirks and explicitly does *not* cover model listing or pricing. This document covers only the
listing and pricing axes.

**Scope.** The four v1 surfaces:

| # | Surface | Base |
|---|---|---|
| 1 | Anthropic (native) | `api.anthropic.com` |
| 2 | OpenAI Chat Completions | `api.openai.com` |
| 3 | Gemini API | `generativelanguage.googleapis.com` |
| 4 | Generic OpenAI-compatible | the portable subset a client may assume |

**Method.** Official primary vendor documentation only. **No API calls were made and no credentials
were used.** Every claim carries a provenance marker:

- **[verified]** — a primary vendor doc states this outright; the URL is given.
- **[inferred]** — reasoned from what the docs say, not stated by them.
- **[not documented]** — the docs were searched for this and are silent. Stronger than "unknown".

**Doc access date: 2026-09-08.** Model rosters and prices churn monthly. Re-verify before relying
on any number here.

---

## TL;DR — the two questions a decision is waiting on

**No listing endpoint on any of the four surfaces returns pricing.** Not one. **[verified]** for
Anthropic, OpenAI and Gemini against their published schemas; **[inferred]** for the generic
OpenAI-compatible subset, since the subset is defined by OpenAI's own schema, which has no price
field. Any price table in this codebase has to be hand-maintained or scraped. There is no first-party
JSON/CSV rate card from Anthropic or OpenAI either. Google is the sole partial exception, and only
via the Cloud Billing Catalog API, which is a Google Cloud SKU catalogue rather than a Gemini API
endpoint.

**Two of the three vendors do have a per-request input-token pricing threshold, and they disagree on
the threshold.** OpenAI: **272K input tokens**, ~2x input / ~1.5x output, on `gpt-6-astra`,
`gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`, `gpt-5.5-pro`, `gpt-5.4`, `gpt-5.4-pro`.
Google: **200K prompt tokens**, ~2x input / ~1.5x output, on Gemini 3.1 Pro Preview and Gemini 2.5
Pro. Anthropic: **no threshold on current models** — 1M context is billed at flat standard rates.
All observed thresholds are evaluated **per-request**, on the *input* side, and when crossed they
reprice the *whole* request, not just the excess. Details and quotes in §6.

---

## 1. Model-listing endpoint

| Surface | Exists? | Method + path | Auth | Paginated? |
|---|---|---|---|---|
| Anthropic (native) | Yes **[verified]** | `GET https://api.anthropic.com/v1/models` **[verified]** | Same credential as inference: `x-api-key` plus the mandatory `anthropic-version` header **[verified]** | Yes — cursor, `before_id`/`after_id`/`limit`, `limit` default 20 max 1000 **[verified]** |
| OpenAI Chat Completions | Yes **[verified]** | `GET https://api.openai.com/v1/models` (`operationId: listModels`) **[verified]** | Same credential as inference: `ApiKeyAuth`, i.e. `Authorization: Bearer $OPENAI_API_KEY` **[verified]** | **No** — `ListModelsResponse` has only `object` and `data`; no `has_more`, no cursor, and the path declares no query parameters **[verified]** |
| Gemini API | Yes **[verified]** | `GET https://generativelanguage.googleapis.com/v1beta/models` (`models.list`); single-model `GET /v1beta/{name=models/*}` (`models.get`) **[verified]** | Same credential as inference: the Gemini API key, passed as `x-goog-api-key` **[verified]** | Yes — `pageSize` (default 50, max 1000) and `pageToken`, response carries `nextPageToken` **[verified]** |
| Generic OpenAI-compatible | Yes, in practice **[verified]** for the servers checked | `GET {base_url}/v1/models` | Whatever the server uses for inference, typically a bearer token; local servers often accept any value **[inferred]** | **No** — the OpenAI shape it copies is unpaginated **[inferred]** |

Sources: <https://platform.claude.com/docs/en/api/models-list>,
<https://platform.claude.com/docs/en/api/versioning>,
<https://github.com/openai/openai-openapi> (`openapi.yaml`, `paths./models`,
`components.schemas.ListModelsResponse`), <https://ai.google.dev/api/models>,
<https://ai.google.dev/gemini-api/docs/api-key>.

Notes:

- Anthropic orders results newest-first: *"More recently released models are listed first."*
  **[verified]** No such ordering guarantee is documented for OpenAI or Gemini **[not documented]**.
- Gemini's listing is documented on the `v1beta` path. Whether an identical `v1` path is supported
  is **[not documented]** on the models reference page.
- For the generic subset, `/v1/models` is documented as implemented by Ollama (`/v1/models` and
  `/v1/models/{model}`, <https://docs.ollama.com/openai>) **[verified]**, vLLM (listed among the
  server's endpoints, <https://docs.vllm.ai/en/latest/serving/online_serving/>) **[verified]**, and
  llama.cpp's server (<https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md>)
  **[verified]**. It is nevertheless not safe to *require* it: nothing in the OpenAI-compatible
  contract obliges a server to implement it **[inferred]**.

---

## 2. Response shape — what the model object carries

Legend: **Y** = present, **n** = absent, with provenance.

| Field group | Anthropic | OpenAI | Gemini | Generic OAI-compatible |
|---|---|---|---|---|
| Identifier | `id` **[verified]** | `id` **[verified]** | `name` (`models/{model}`), plus `baseModelId`, `version` **[verified]** | `id` **[verified]** |
| Display name | `display_name` **Y [verified]** | **n [verified]** | `displayName` (≤128 UTF-8 chars) **Y [verified]** | **n [inferred]** |
| Description | **n [verified]** | **n [verified]** | `description` **Y [verified]** | **n [inferred]** |
| Context window / input limit | `max_input_tokens` **Y [verified]** | **n [verified]** | `inputTokenLimit` **Y [verified]** | **n [verified]** for Ollama; llama.cpp exposes `meta.n_ctx_train` as a **non-standard extension** **[verified]** |
| Max output tokens | `max_tokens` **Y [verified]** | **n [verified]** | `outputTokenLimit` **Y [verified]** | **n [inferred]** |
| Modality support | Indirect: `capabilities.image_input`, `capabilities.pdf_input` **[verified]** | **n [verified]** | Indirect: `supportedGenerationMethods[]` lists *methods*, not modalities **[verified]** | **n [inferred]** |
| Tool-use flag | **n** as such; nearest is `capabilities.structured_outputs` and `capabilities.code_execution` **[verified]** | **n [verified]** | **n [verified]** | **n [inferred]** |
| Vision flag | `capabilities.image_input` **Y [verified]** | **n [verified]** | **n [verified]** | **n [inferred]** |
| Caching flag | **n** as a boolean; `capabilities.context_management` covers context editing, not prompt caching **[verified]** | **n [verified]** | **n [verified]** | **n [inferred]** |
| Reasoning / thinking flag | `capabilities.thinking.supported` plus `types.adaptive` / `types.enabled`, and `capabilities.effort` with per-level `low`/`medium`/`high`/`max`/`xhigh` **Y [verified]** | **n [verified]** | `thinking` (boolean) **Y [verified]** | **n [inferred]** |
| Batch support | `capabilities.batch` **Y [verified]** | **n [verified]** | **n [verified]** | **n [inferred]** |
| Citations | `capabilities.citations` **Y [verified]** | **n [verified]** | **n [verified]** | **n [inferred]** |
| Creation / release date | `created_at`, RFC 3339, *"the time at which the model was released. May be set to an epoch value if the release date is unknown."* **Y [verified]** | `created`, Unix seconds, *"when the model was created"* **Y [verified]** | **n [verified]** | `created` **Y [verified]** (Ollama documents it as *"when the model was last modified"*, i.e. **different semantics**) |
| Deprecation / retirement date | **n [verified]** | `shutdown_date`, `string(date)` or `null`, *"The date when the model will shut down, or null if not announced."* **Y [verified]** | **n [verified]** | **n [inferred]** |
| Owner | **n [verified]** | `owned_by` **Y [verified]** | **n [verified]** | `owned_by` **Y [verified]** |
| Sampling defaults | **n [verified]** | **n [verified]** | `temperature`, `maxTemperature`, `topP`, `topK` **Y [verified]** | **n [inferred]** |
| **Pricing** | **n [verified]** | **n [verified]** | **n [verified]** | **n [inferred]** |

Anthropic's list envelope also carries `first_id`, `last_id`, `has_more` **[verified]**; each entry
has `type: "model"` **[verified]**. OpenAI's envelope carries `object: "list"` and `data` only
**[verified]**.

**Reading of the table.** Anthropic's `/v1/models` is by a wide margin the richest of the three: it
is the only one that returns a structured capability tree, and the only one that returns both an
input limit and an output limit alongside per-capability booleans. OpenAI's is the poorest — four
required fields (`id`, `object`, `created`, `owned_by`) plus optional `shutdown_date`. Gemini sits in
between: good static limits and a display name, no capability tree beyond `thinking`, no
deprecation date.

**The asymmetry that matters for a registry design.** Deprecation dates and context limits are
*disjoint* across vendors: OpenAI gives you `shutdown_date` but no context window; Anthropic and
Gemini give you the context window but no shutdown date. **[verified]** So no single surface lets a
client answer both "how big is it" and "when does it die" from the listing endpoint alone
**[inferred]**. Anthropic publishes retirement dates on a separate prose page
(<https://platform.claude.com/docs/en/about-claude/model-deprecations>) **[verified]**, which is not
machine-readable **[inferred]**.

llama.cpp's `meta` object (`vocab_type`, `n_vocab`, `n_ctx_train`, `n_embd`, `n_params`, `size`)
**[verified]** is a good example of why the *generic* row must stay minimal: local servers do add
useful fields, but each adds a different set, so nothing beyond `id` is portable **[inferred]**.

---

## 3. Does any listing endpoint expose PRICING?

Plainly, per surface:

| Surface | Pricing in the listing response? |
|---|---|
| Anthropic (native) | **No.** **[verified]** The `ModelInfo` schema is `id`, `capabilities`, `created_at`, `display_name`, `max_input_tokens`, `max_tokens`, `type`. There is no price field of any kind. |
| OpenAI Chat Completions | **No.** **[verified]** The `Model` schema is `id`, `created`, `object`, `owned_by`, `shutdown_date`. There is no price field of any kind. |
| Gemini API | **No.** **[verified]** The `Model` resource is `name`, `baseModelId`, `version`, `displayName`, `description`, `inputTokenLimit`, `outputTokenLimit`, `supportedGenerationMethods[]`, `thinking`, `temperature`, `maxTemperature`, `topP`, `topK`. There is no price field of any kind. |
| Generic OpenAI-compatible | **No.** **[inferred]** The portable subset is OpenAI's `Model` schema, which has no price field, so a client may not assume one. Individual OpenAI-compatible aggregators do add pricing as a vendor extension — OpenRouter's `/api/v1/models` is the well-known case — but that is outside the generic subset and must not be relied on **[inferred]**. |

**Consequence.** A price table cannot be populated from the inference APIs. It has to come from
elsewhere — hand-maintained constants, a scrape, or (for Google only) the Cloud Billing Catalog.
**[inferred]**

**Adjacent but not a substitute: realized-cost endpoints.** Both Anthropic and OpenAI expose
*spend already incurred*, not a rate card:

- Anthropic `GET https://api.anthropic.com/v1/organizations/cost_report` **[verified]**. Requires an
  admin credential (`Authorization: Bearer $ANTHROPIC_AUTH_TOKEN`), **not** the inference API key
  **[verified]**. Returns time buckets with `amount` (decimal string, *"in lowest currency units
  (e.g. cents)"*), `currency` (*"Currently always `USD`"*), `model`, `token_type`, `service_tier`,
  `inference_geo`, and `context_window`.
- OpenAI `GET https://api.openai.com/v1/organization/costs` **[verified]**, `security:
  AdminApiKeyAuth`, i.e. `Authorization: Bearer $OPENAI_ADMIN_KEY`, again a different credential from
  inference **[verified]**.

These let you reconcile a bill. They do **not** let you predict one, because they report money spent
rather than $/MTok **[inferred]**.

**One artefact worth flagging from that Anthropic schema.** The cost report's `context_window` field
is an enum with exactly two values, `"0-200k"` and `"200k-1M"` **[verified]**. So Anthropic's billing
system still *buckets* usage by a 200K input boundary even though the current pricing page says
long-context requests are billed at standard rates (see §6). Read this as a residue of the older
Sonnet 4/4.5 1M-context beta rather than as evidence of a live surcharge **[inferred]** — the
pricing page is the authoritative statement on rates, and it says flat.

---

## 4. Rate limits on the listing endpoint

| Surface | Documented limit for the listing endpoint? |
|---|---|
| Anthropic | **[not documented]**. The rate-limits page enumerates limits for the Messages API (RPM/ITPM/OTPM per model class), the Message Batches API, Managed Agents endpoints, the Files API and fast mode. `/v1/models` is not named anywhere on it. **[verified]** that it is absent. **[inferred]**: the Models API is either unlimited or governed by an undocumented shared limit; do not build a poll loop assuming either. |
| OpenAI | **[not documented]**. The rate-limits guide describes RPM/TPM/RPD/TPD tiers and states limits *"vary by the model being used"*, which does not map onto a model-agnostic listing call. `/v1/models` is not mentioned. **[verified]** that it is absent. |
| Gemini | **[not documented]**. The rate-limits page covers RPM/TPM/RPD for generation, and does not state which endpoints the limits attach to. `models.list` is not mentioned. **[verified]** that it is absent. |
| Generic OpenAI-compatible | **[not documented]**, and unknowable in general — it is per-deployment. |

Sources: <https://platform.claude.com/docs/en/api/rate-limits>,
<https://developers.openai.com/api/docs/guides/rate-limits>,
<https://ai.google.dev/gemini-api/docs/rate-limits>.

Anthropic does document rate-limit *response headers* that apply to API responses generally —
`anthropic-ratelimit-requests-limit`, `-remaining`, `-reset`, and token-scoped variants, plus
`retry-after` on 429 **[verified]**. Whether `/v1/models` responses carry them is **[not
documented]**.

Related and worth knowing even though it is not a *listing* limit: OpenAI publishes **separate
rate-limit tiers for long-context traffic**, gated on the same 272K boundary as its long-context
pricing. The `gpt-5.5` model page has a "Long Context" table headed *"> 272K input tokens"* with its
own RPM/TPM/batch-queue numbers per tier — e.g. Tier 1 drops from 500 RPM / 500,000 TPM to 200 RPM /
400,000 TPM **[verified]**, <https://developers.openai.com/api/docs/models/gpt-5.5>. So crossing 272K
costs you throughput as well as money **[verified]**.

---

## 5. Machine-readable pricing published officially?

| Vendor | Machine-readable rate card? | Detail |
|---|---|---|
| Anthropic | **No** JSON/CSV. **[verified]** as absent | The rate card exists only as documentation prose at <https://platform.claude.com/docs/en/about-claude/pricing>. There is a **Markdown mirror** at <https://platform.claude.com/docs/en/about-claude/pricing.md>, served as `text/markdown` **[verified]**, containing the price tables as GFM tables. That is parseable, but it is a docs mirror with no schema and no stability guarantee, not an API **[inferred]**. |
| OpenAI | **No** JSON/CSV. **[verified]** as absent | Same situation: <https://developers.openai.com/api/docs/pricing> renders HTML tables, and <https://developers.openai.com/api/docs/pricing.md> serves the Markdown source. The docs state the convention outright: *"Markdown versions of documentation pages are available by appending `.md` to the page URL."* **[verified]**. Again a docs mirror, not an API **[inferred]**. |
| Google | **Partially yes**, but not from the Gemini API | The Gemini pricing page publishes no JSON/CSV and no endpoint **[verified]**; appending `.md` returns HTML, so Google does *not* offer the Markdown-mirror trick **[verified]**. However Google Cloud publishes the **Cloud Billing Catalog API**: `GET https://cloudbilling.googleapis.com/v1/{parent=services/*}/skus` **[verified]**, which *"lists all publicly available SKUs for a given cloud service"* and returns `pricingInfo[]` → `pricingExpression` → `tieredRates[]` with `startUsageAmount` and `unitPrice`, plus `usageUnit` **[verified]**. It is paginated (`pageSize` default 5000, `pageToken`), and requires **OAuth** (`cloud-platform`, `cloud-billing`, or `cloud-billing.readonly`) — API-key auth is **[not documented]** **[verified]**. Whether SKUs for `generativelanguage.googleapis.com` specifically (as opposed to Vertex AI) appear in that catalogue is **[not documented]**. |

Source for the Billing Catalog:
<https://docs.cloud.google.com/billing/docs/reference/rest/v1/services.skus/list>.

**Design read.** There is no vendor-neutral machine-readable pricing feed and no realistic prospect
of one from these three **[inferred]**. The honest options are (a) hand-maintained constants with a
recorded access date and a staleness warning, or (b) scraping the Markdown mirrors for Anthropic and
OpenAI plus HTML for Google. Option (b) buys freshness at the cost of a scraper that breaks silently
whenever a docs page is restructured **[inferred]**. Note also that the two Markdown mirrors are not
in a common schema, so (b) is really two scrapers, not one **[inferred]**.

---

## 6. Tiered / long-context pricing — the threshold question

**Two of three vendors: yes. Anthropic: no, not any more.** All observed thresholds are on **input**
tokens, evaluated **per request**, and reprice the **entire** request rather than only the excess.

### OpenAI — threshold 272K input tokens

**[verified]**, quoted verbatim from the per-model docs:

> Prompts with more than 272K input tokens are priced at 2x input and cache rates and 1.5x output for the full request.

— <https://developers.openai.com/api/docs/models/gpt-6-astra>

> Prompts with >272K input tokens are priced at 2x input and 1.5x output for the full request.

— <https://developers.openai.com/api/docs/models/gpt-5.6-sol>, and identically on
<https://developers.openai.com/api/docs/models/gpt-5.6-terra> and
<https://developers.openai.com/api/docs/models/gpt-5.6-luna>

> For GPT-5.5, prompts with >272K input tokens are priced at 2x input and 1.5x output for the full session for standard, batch, and flex.

— <https://developers.openai.com/api/docs/models/gpt-5.5>

> For models with a 1.05M context window (GPT-5.4 and GPT-5.4 Pro), prompts with >272K input tokens are priced at 2x input and 1.5x output for the full session for standard, batch, and flex.

— <https://developers.openai.com/api/docs/models/gpt-5.4> and
<https://developers.openai.com/api/docs/models/gpt-5.4-pro>

**Per-request or cumulative?** **Per-request.** **[verified]** for `gpt-6-astra`, `gpt-5.6-sol`,
`gpt-5.6-terra`, `gpt-5.6-luna`, all of which say *"for the full request"*. The `gpt-5.5` and
`gpt-5.4` pages instead say *"for the full session"*, which is the only wording in the corpus that
could be read as cumulative. Treat that as loose phrasing for the same per-request rule
**[inferred]** — the trigger in every variant is *"prompts with >272K input tokens"*, a property of a
single prompt, and the newer model pages replaced "session" with "request" while leaving the
multipliers identical, which reads as a wording fix rather than a policy change **[inferred]**.
Whether "session" is load-bearing on `gpt-5.5`/`gpt-5.4` is **[not documented]**.

**Which models.** The pricing page renders this as paired column groups — *"Short context input /
Short context cached input / Short context cache writes / Short context output"* and the same four
under *"Long context"* **[verified]**. Rows with both groups populated, at standard tier:

| Model | Short in | Short cached in | Short cache write | Short out | Long in | Long cached in | Long cache write | Long out |
|---|---|---|---|---|---|---|---|---|
| `gpt-6-astra` | $10.00 | $1.00 | $12.50 | $50.00 | $20.00 | $2.00 | $25.00 | $75.00 |
| `gpt-5.6-sol` | $4.00 | $0.40 | $5.00 | $20.00 | $8.00 | $0.80 | $10.00 | $30.00 |
| `gpt-5.6-terra` | $2.00 | $0.20 | $2.50 | $12.00 | $4.00 | $0.40 | $5.00 | $18.00 |
| `gpt-5.6-luna` | $0.20 | $0.02 | $0.25 | $1.20 | $0.40 | $0.04 | $0.50 | $1.80 |
| `gpt-5.5` | $5.00 | $0.50 | – | $30.00 | $10.00 | $1.00 | – | $45.00 |
| `gpt-5.5-pro` | $30.00 | – | – | $180.00 | $60.00 | – | – | $270.00 |
| `gpt-5.4` | $2.50 | $0.25 | – | $15.00 | $5.00 | $0.50 | – | $22.50 |
| `gpt-5.4-pro` | $30.00 | – | – | $180.00 | $60.00 | – | – | $270.00 |

USD per 1M tokens, <https://developers.openai.com/api/docs/pricing> **[verified]**. Every ratio is
exactly 2x on input and cached input and cache writes, and exactly 1.5x on output **[verified]**, so
the multiplier is uniform and the doubling applies to cache reads too — worth noting, since cache
reads are the tokens most likely to push a long agent loop over the line **[inferred]**.

Models with only the short-context group populated (`gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.2`,
`gpt-5.2-pro`, `gpt-5.1`, `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5-pro`, `gpt-4.1` and its mini
and nano) have **no long-context tier** **[verified]**. The same short/long split repeats in the
batch and flex tables at halved rates **[verified]**.

Note the labelling quirk: the pricing table names some rows `gpt-5.5 (<272K context length)`
**[verified]**, which reads as if it were a separate model. It is not — it is the short-context price
row for `gpt-5.5` **[inferred]**.

### Google Gemini — threshold 200K prompt tokens

**[verified]**, verbatim column labels from <https://ai.google.dev/gemini-api/docs/pricing>:

> `$2.00, prompts <= 200k tokens` … `$4.00, prompts > 200k tokens`

| Model | Tier | Input ≤200k | Input >200k | Output ≤200k | Output >200k |
|---|---|---|---|---|---|
| Gemini 3.1 Pro Preview | Standard | $2.00 | $4.00 | $12.00 | $18.00 |
| Gemini 3.1 Pro Preview | Batch | $1.00 | $2.00 | $6.00 | $9.00 |
| Gemini 2.5 Pro | Standard | $1.25 | $2.50 | $10.00 | $15.00 |
| Gemini 2.5 Pro | Batch | $0.625 | $1.25 | $5.00 | $7.50 |

USD per 1M tokens **[verified]**. Ratios are 2x input and 1.5x output — numerically identical to
OpenAI's multipliers, at a different threshold **[verified]**. Gemini 2.5 Flash and the other Flash
and Lite models are flat-rate **[verified]**.

**Per-request or cumulative?** The docs say *"prompts"*, a per-prompt property, so **per-request**
**[inferred]**. Google does **not** state "per request" in those words, and does not say whether
cached tokens count toward the 200k **[not documented]**.

### Anthropic — no threshold on current models

This is the surprise, and it is a *change* from the older Sonnet 4 / 4.5 1M-context beta behaviour.
Verbatim, from <https://platform.claude.com/docs/en/about-claude/pricing> under the heading "Long
context pricing":

> Claude 4.6 and later models and Claude Mythos Preview include the full 1M token context window at standard pricing. (A 900k-token request is billed at the same per-token rate as a 9k-token request.) Prompt caching and batch processing discounts apply at standard rates across the full context window.

**[verified]**. Corroborated on <https://platform.claude.com/docs/en/build-with-claude/context-windows>:

> For every model with a 1M-token context window, 1M is the default: you don't need a beta header, and long-context requests are billed at standard pricing.

**[verified]**. The per-model price table on the pricing page has a single input column ("Base input
tokens") with no threshold split **[verified]**.

Two residues of the old scheme survive and should not be mistaken for a live surcharge:

1. The fast-mode section says fast-mode pricing *"applies across the full context window, including
   requests over 200k input tokens"* **[verified]** — phrasing that only makes sense as reassurance
   against a threshold that no longer applies **[inferred]**.
2. The Admin cost report's `context_window` enum, `"0-200k"` / `"200k-1M"` **[verified]** (see §3).

Models below Claude 4.6 that never had a 1M window (Claude Sonnet 4.5 and earlier, all Haiku) have a
200k context window and so cannot cross a 200k input threshold at all **[verified]** for the window
size, **[inferred]** for the conclusion.

### Summary table

| Vendor | Threshold | Side | Multiplier | Scope | Per-request or cumulative |
|---|---|---|---|---|---|
| OpenAI | 272,000 input tokens | input | 2x input, 2x cached input, 2x cache writes, 1.5x output | whole request | **per-request** **[verified]** ("for the full request"); `gpt-5.5`/`gpt-5.4` say "full session" **[verified]**, read as the same rule **[inferred]** |
| Google | 200,000 prompt tokens | input | 2x input, 1.5x output | whole request **[inferred]** | **per-request** **[inferred]** |
| Anthropic | none on current models | — | — | — | n/a **[verified]** |

**What this settles.** A cost estimator cannot use one global threshold constant. The threshold is
per-vendor *and* per-model — `gpt-5.6-luna` has one, `gpt-5.4-mini` does not; Gemini 2.5 Pro has one,
Gemini 2.5 Flash does not; no current Claude model has one. It therefore belongs on the per-model
record as an optional `(threshold_tokens, input_multiplier, output_multiplier)` triple, absent by
default, and the evaluation is a single comparison against that request's input-token count with the
result applied to the whole request **[inferred]**. Cache-read tokens must be counted toward the
comparison and repriced along with everything else, at least for OpenAI, where the doubling of cached
input is explicit **[verified]**.

---

## Cross-cutting notes

**Same-credential is the rule, admin-credential is the exception.** All three listing endpoints take
the same credential as inference **[verified]**. Both realized-cost endpoints take a *different*,
admin-scoped credential **[verified]**. Google's Billing Catalog needs OAuth rather than an API key
**[verified]**. So a client that only holds an inference key can enumerate models everywhere and
price nothing anywhere **[inferred]**.

**Pagination is not uniform and one surface has none.** Anthropic uses opaque bidirectional ID
cursors with `has_more`; Gemini uses `pageToken`/`nextPageToken`; OpenAI returns a bare list with no
paging affordance at all **[verified]**. Any abstraction over "list models" has to tolerate a
provider that simply returns everything at once **[inferred]**.

**Folklore corrections.** Two things that are widely assumed and are wrong as of the access date:

1. **Anthropic does not charge a long-context premium.** The 200K/2x rule people remember was the
   Sonnet 4/4.5 `context-1m-2025-08-07` beta. On Claude 4.6 and later it is gone, stated explicitly
   and with a worked example ("a 900k-token request is billed at the same per-token rate as a 9k-token
   request") **[verified]**. Carrying the old rule forward would over-estimate Claude costs on long
   prompts.
2. **The long-context threshold is not 200K everywhere.** OpenAI's is 272K, not 200K **[verified]**.
   A shared 200K constant would mis-bill OpenAI requests in the 200K–272K band in the expensive
   direction.

**Where the docs are silent.** Recorded so it is not re-derived later: whether the listing endpoints
have their own rate limits (all three) **[not documented]**; whether Gemini's 200k threshold counts
cached tokens **[not documented]**; whether Gemini's `models.list` exists on a stable `v1` path
**[not documented]**; whether Google's Billing Catalog carries `generativelanguage.googleapis.com`
SKUs **[not documented]**; whether `/v1/models` responses carry Anthropic's rate-limit headers
**[not documented]**.

---

## Sources

Anthropic:

- <https://platform.claude.com/docs/en/api/models-list>
- <https://platform.claude.com/docs/en/api/versioning>
- <https://platform.claude.com/docs/en/api/rate-limits>
- <https://platform.claude.com/docs/en/about-claude/pricing> (and `.md` mirror)
- <https://platform.claude.com/docs/en/build-with-claude/context-windows>
- <https://platform.claude.com/docs/en/about-claude/model-deprecations>
- <https://platform.claude.com/docs/en/api/admin-api/usage-cost/get-cost-report>

OpenAI:

- <https://github.com/openai/openai-openapi> — `openapi.yaml`: `paths./models`,
  `components.schemas.Model`, `components.schemas.ListModelsResponse`, `paths./organization/costs`
- <https://developers.openai.com/api/docs/pricing> (and `.md` mirror)
- <https://developers.openai.com/api/docs/models/gpt-6-astra>
- <https://developers.openai.com/api/docs/models/gpt-5.6-sol>
- <https://developers.openai.com/api/docs/models/gpt-5.6-terra>
- <https://developers.openai.com/api/docs/models/gpt-5.6-luna>
- <https://developers.openai.com/api/docs/models/gpt-5.5>
- <https://developers.openai.com/api/docs/models/gpt-5.4>
- <https://developers.openai.com/api/docs/models/gpt-5.4-pro>
- <https://developers.openai.com/api/docs/guides/rate-limits>

Google:

- <https://ai.google.dev/api/models>
- <https://ai.google.dev/gemini-api/docs/pricing>
- <https://ai.google.dev/gemini-api/docs/rate-limits>
- <https://ai.google.dev/gemini-api/docs/api-key>
- <https://docs.cloud.google.com/billing/docs/reference/rest/v1/services.skus/list>

Generic OpenAI-compatible:

- <https://docs.ollama.com/openai>
- <https://docs.vllm.ai/en/latest/serving/online_serving/>
- <https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md>

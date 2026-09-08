# Per-provider API quirks — raw catalogue

Research output for [tapir-dev/tp#10](https://github.com/tapir-dev/tp/issues/10).

**Scope.** The quirk axes named in the ticket, for the major hosted providers plus the
generic OpenAI-compatible endpoint shape. This is the *raw catalogue only*. How the
table is represented in code is a separate ticket (#16) and is deliberately not
designed here.

**Method.** Official primary provider documentation only. No API calls were made and
no credentials were used. Every non-obvious claim is traceable to a URL in the
per-provider sections below.

**Doc access date: 2026-09-07.** These APIs drift; treat every cell as stale after a
few months and re-verify against the linked source before relying on it.

**Reading the tables.**

- `unknown` means *not confirmable from primary docs* — not "no" and not "probably".
  A blank/unknown cell is correct; a wrong quirk flag is worse.
- `none documented` means the docs were searched for the feature and it is absent,
  which is a stronger claim than `unknown`.
- Model-gated behaviour is called out inline, because several axes are per-model
  rather than per-provider. The brief's "per-provider/per-model quirk table" is
  literal: at least reasoning-effort values, thinking mode, cache minimums, and
  prefill support vary *within* a single provider.

**Row set.** Provider rows are the same in every table, in this order:

| # | Row | Surface |
|---|---|---|
| 1 | Anthropic (native) | `POST api.anthropic.com/v1/messages` |
| 2 | Anthropic on Bedrock (new) | `POST bedrock-mantle.{region}.api.aws/anthropic/v1/messages` |
| 3 | Anthropic on Bedrock (legacy) | `InvokeModel` / `InvokeModelWithResponseStream` on `bedrock-runtime` |
| 4 | Anthropic on Vertex | `:rawPredict` / `:streamRawPredict` |
| 5 | OpenAI Chat Completions | `POST api.openai.com/v1/chat/completions` |
| 6 | OpenAI Responses | `POST api.openai.com/v1/responses` |
| 7 | Azure OpenAI | classic deployment path, or `openai/v1/` |
| 8 | Gemini API | `generativelanguage.googleapis.com` `generateContent` |
| 9 | Vertex Gemini | `aiplatform.googleapis.com` `generateContent` |
| 10 | Bedrock Converse | `Converse` / `ConverseStream` on `bedrock-runtime` |
| 11 | xAI (Grok) | `api.x.ai/v1/chat/completions` + `/v1/responses` |
| 12 | Mistral | `api.mistral.ai/v1/chat/completions` |
| 13 | DeepSeek | `api.deepseek.com` (+ `/beta`) |
| 14 | Groq | `api.groq.com/openai/v1` |
| 15 | OpenRouter | `openrouter.ai/api/v1` |
| 16 | Ollama | `/v1/chat/completions` compat endpoint |
| 17 | vLLM | OpenAI-compatible server |
| 18 | llama.cpp server | `/v1/chat/completions` |
| 19 | LM Studio | `/v1/chat/completions` |
| 20 | **Generic OpenAI-compatible** | the portable subset a client may assume |

---

## Table A — Role support and message ordering

| Provider | Role values | System placement | Message-ordering requirements |
|---|---|---|---|
| Anthropic (native) | `user`, `assistant`, `system` | top-level `system` param (string or text blocks); **mid-conversation `role:"system"` messages** on Fable 5.1, Mythos 5.1, Fable 5, Mythos 5, Opus 4.8, Opus 5 — **not** Sonnet 5; no beta header | Alternation **not enforced** — consecutive same-role turns are merged into one. A `system` message may not be first (exception: empty-content effort-only), must follow a user/assistant turn, must precede an assistant turn or end the array, and must not sit between a `tool_use` and its `tool_result`. Assistant-last = prefill, but **400 on Claude 4.6+ and Mythos Preview**. Later system messages beat earlier ones and beat top-level `system`. |
| Anthropic on Bedrock (new) | same as native | same as native | same as native |
| Anthropic on Bedrock (legacy) | same as native | same as native | same as native; Converse-API path instead uses Converse's own top-level `system` |
| Anthropic on Vertex | same as native | same as native | same as native |
| OpenAI Chat Completions | `developer`, `system`, `user`, `assistant`, `tool`, `function` (deprecated) | `system` or `developer` as ordinary messages; `developer` replaces `system` from o1 onward | **unknown** — no alternation rule, no "tool message must follow tool_calls" rule, and no error text appear in OpenAI primary docs. The commonly-cited 400 string is community-sourced only. |
| OpenAI Responses | `user`, `assistant`, `system`, `developer` (strict `InputMessage`: `user`/`system`/`developer` only). **No `tool` role** | message items | **unknown**; the migration guide only warns against dropping reasoning / function_call / function_call_output items when carrying context manually |
| Azure OpenAI | as per surface | `developer` ≡ `system`; **do not send both in one request**; on o4-mini/o3/o3-mini/o1 a system message is treated as a developer message | **unknown** (inherits the surface) |
| Gemini API | `contents[].role` = `user` \| `model`, and the field is **optional** | **no system role** — separate top-level `systemInstruction` (text only) | **none documented** — no alternation rule, no first-must-be-user, no last-message rule, no error code. Docs self-contradict on tool results: the `Tool` reference text says role `"function"`, every worked example uses `"user"`. |
| Vertex Gemini | same | same; **`systemInstruction.role` is ignored** | same as Gemini API |
| Bedrock Converse | `messages[].role` valid values are `user` \| `assistant` \| **`system`** per the API reference | top-level `system` array; `messages` is `Required: No` (a Prompt ARN can supply it) | **none documented**. Structural constraints that *are* documented: ≤20 images, ≤5 documents; a `document` block requires a sibling `text` block; images and documents **only** when `role: "user"`. |
| xAI | `system`, `user`, `assistant`, `tool` — **`developer` never mentioned** | system message | none documented |
| Mistral | `system`, `user`, `assistant`, `tool`; no `developer` | system message | **none documented for the chat API.** `AssistantMessage.prefix: true` conditions a prefill on the normal base URL. See the folklore correction below — the "last message must be user" rule is a *fine-tuning dataset* rule, not an API rule. |
| DeepSeek | `system`, `user`, `assistant`, `tool`; no `developer`; **`name` is absent from the tool-message schema** | system message | **none documented.** Prefix completion requires `base_url=https://api.deepseek.com/beta`, `prefix: true`, and the last message being the assistant one. |
| Groq | `system`, `user`, `assistant`, `tool`, `function` (deprecated); no `developer`; all message schemas are `additionalProperties: false` | system message | none documented; assistant **prefilling is explicitly supported** |
| OpenRouter | `system`, **`developer`**, `user`, `assistant`, `tool` — the only provider here that documents `developer` | system/developer message | none documented; prefill supported |
| Ollama | `system`, `user`, `assistant`, `tool` | system message | none documented |
| vLLM | `role` is an unconstrained string; validation is delegated to the model's Jinja chat template | template-dependent | template-dependent |
| llama.cpp | ChatML default; only `system`/`user`/`assistant` documented | system message | none documented |
| LM Studio | `system`, `user`, `assistant`, `tool` | system message | none documented |
| **Generic** | assume **only** `system`/`user`/`assistant`/`tool` | top-level `system` message | assume nothing; do not rely on alternation being enforced *or* on it being permitted |

---

## Table B — Reasoning effort and thinking serialization

| Provider | Effort/budget field | Values | Thinking wire format | Echo-back requirement |
|---|---|---|---|---|
| Anthropic (native) | **two** controls: `thinking` (mode) and `output_config.effort` | `thinking`: `{type:"enabled", budget_tokens, display}` \| `{type:"disabled"}` \| `{type:"adaptive", display}`. `effort`: `low\|medium\|high\|xhigh\|max`, default `high`. `enabled`+`budget_tokens` is **deprecated on 4.6 and 400s on 4.7+**; `adaptive` 400s on Sonnet 4.5/Opus 4.5/Haiku 4.5 and earlier | `{"type":"thinking","thinking":"…","signature":"…"}` and `{"type":"redacted_thinking","data":"…"}`. `display:"omitted"` (the default on Fable 5.1/Mythos 5.1/Fable 5/Mythos 5/Opus 5/Sonnet 5/Opus 4.8/4.7) returns **empty `thinking` with a populated `signature`**. Stream deltas: `thinking_delta`, `signature_delta` | **Mandatory with tool use** — blocks must return complete and unmodified, `redacted_thinking` included, or 400. From Fable 5.1 the signature is validated against the unchanged prefix (system + tools + preceding messages); any prefix edit invalidates that block and all later ones |
| Anthropic on Bedrock (new) | same | same; top-level effort available | same; **signatures are portable across Claude API / Bedrock / Vertex** | same |
| Anthropic on Bedrock (legacy) | same | same | same | same |
| Anthropic on Vertex | same | same | same | same |
| OpenAI Chat Completions | `reasoning_effort` (top level). **No `reasoning` object on this surface** | `none\|minimal\|low\|medium\|high\|xhigh\|max`, default `medium`; not all models accept every value; `max` is **Responses-only**; `minimal` is original-GPT-5-only; `gpt-5.1` defaults to `none`; GPT-6 Astra 400s on `none` | **No reasoning content is serialized at all** — only the token count (`completion_tokens_details.reasoning_tokens`) | n/a (nothing to echo) |
| OpenAI Responses | `reasoning: {effort, summary, context}` | same enum. `summary`: `auto\|concise\|detailed`. `context`: `auto\|current_turn\|all_turns` (gpt-5.6 family defaults `all_turns`, earlier `current_turn`) | reasoning items with a `summary` array; encrypted state via `include: ["reasoning.encrypted_content"]`. Stream events `response.reasoning_text.delta/.done`, `response.reasoning_summary_text.delta/.done`, `response.reasoning_summary_part.added/.done` | Carried by `previous_response_id`, or manually via encrypted items when `store:false`/ZDR. **Streaming trap:** take `encrypted_content` from `response.output_item.done`; the copy on `.added` may be incomplete |
| Azure OpenAI | as per surface | full per-model matrix published by Azure (see notes). Azure-only hard edge: on `gpt-5.6-sol` + Chat Completions, sending `tools` at all fails unless `reasoning_effort: "none"` — and it fails even if you omit the field, because the default is `medium` | as per surface | as per surface |
| Gemini API | `generationConfig.thinkingConfig.{thinkingLevel, thinkingBudget, includeThoughts}` | `thinkingLevel`: `MINIMAL\|LOW\|MEDIUM\|HIGH` (Gemini 3+; **errors on earlier models**). `thinkingBudget`: per-model ranges; `-1` = dynamic; `0` disables (not possible on 2.5 Pro, 3 Pro, 3.1 Pro). **Sending both on a Gemini 3 model is an error** | `Part.thought: true` plus `Part.thoughtSignature` (base64). There is no dedicated thought block — the signature is metadata attachable to any part, including `functionCall` parts | **400 on Gemini 3+ if omitted**, even at `MINIMAL`. Only the **first** parallel `functionCall` part carries a signature; each sequential step's does. Interleaving `FC1,FR1,FC2,FR2` instead of `FC1,FC2,FR1,FR2` is a 400. A turn starts at the most recent non-`functionResponse` user message. Escape hatch `skip_thought_signature_validator` (degrades quality). Non-functionCall signatures are not strictly validated |
| Vertex Gemini | same | same | same | same |
| Bedrock Converse | **no first-class field** — passed via `additionalModelRequestFields` | `{"thinking":{"type":"adaptive"}, "output_config":{"effort":"low"}}`; effort `max\|xhigh\|high\|medium\|low`. **`effort` inside `thinking` is a `ValidationException`** — it must be its own `output_config` object. Omitting `thinking` on Sonnet 5 / Opus 5 does **not** disable thinking (adaptive is the default) | `ContentBlock.reasoningContent`, a union of `reasoningText{text,signature}` and `redactedContent`. In the stream `ReasoningContentBlockDelta` is a union of `text` \| `signature` \| `redactedContent` | Required: submit the returned `signature` plus all previous messages unmodified, or the response errors |
| xAI | `reasoning_effort` (chat completions); `reasoning:{effort}` (responses) | `none\|low\|medium\|high\|xhigh`. Models that don't support the parameter **reject the request**; `xhigh` on e.g. `grok-4.5` is **silently downgraded to `high`**. Reasoning cannot be disabled on grok-4.5/4.6. `presence_penalty`/`frequency_penalty`/`stop` **error** on reasoning models | `choices[].message.reasoning_content` (chat completions); `include:["reasoning.encrypted_content"]` (responses) | encrypted-content echo-back on the Responses surface |
| Mistral | `reasoning_effort`; also `prompt_mode: "reasoning"` | `none\|minimal\|low\|medium\|high\|xhigh` | **typed content chunk**: `ThinkChunk = {type:"thinking", thinking:[TextChunk…], signature, closed}`. Magistral `-2506` used inline `<think>` string tags; `-2507` switched to typed chunks and **requires a migration** | `signature` exists "to replay some reasoning blocks across turns"; enforcement **unknown** |
| DeepSeek | `thinking:{type:"enabled"\|"disabled"}` (default **enabled**) + `reasoning_effort`, both via `extra_body` | `low\|high\|max`; `medium` and `xhigh` are **mapped to `high`** | **`reasoning_content`**, a sibling of `content` (also in the streaming `delta`) | **Conditional and load-bearing:** with `tools` present, all prior turns' `reasoning_content` must be passed back or the API returns **400**. Without `tools` it is silently ignored. Thinking mode also silently ignores `temperature`, `top_p`, and both penalties |
| Groq | `reasoning_format` **or** `include_reasoning` (mutually exclusive), plus `reasoning_effort` | `reasoning_format`: `raw` (inline `<think>` tags in `content`) \| `parsed` (`message.reasoning`) \| `hidden`. GPT-OSS models don't support `reasoning_format` at all. `reasoning_effort`: `none, default, minimal, low, medium, high, xhigh, max`, model-dependent; **values outside a model's set are 400s** | see above | **400** if `reasoning_format: "raw"` is combined with JSON mode or tool use (the format silently defaults to `raw` or `parsed` when those are on) |
| OpenRouter | unified `reasoning: {effort, max_tokens, exclude, enabled, summary}` | `max\|xhigh\|high\|medium\|low\|minimal\|none`, documented as approximate budget fractions (max≈95%, high≈80%, medium≈50%, low≈20%, minimal≈10%). Legacy `include_reasoning: true/false` | `reasoning` string plus typed **`reasoning_details`** blocks: `reasoning.summary`, `reasoning.encrypted`, `reasoning.text` (with optional `signature`), each carrying `id`/`format`/`index`/`type` | Mandatory for Anthropic upstreams: the entire sequence of consecutive reasoning blocks must match what the model produced |
| Ollama | compat endpoint accepts **both** `reasoning_effort` and `reasoning:{effort}` | `high\|medium\|low\|max\|none` | compat endpoint: OpenAI-shaped. Native `/api/chat` uses request `think` and response **`message.thinking`** | unknown |
| vLLM | requires `--reasoning-parser`; `include_reasoning: false` via `extra_body` suppresses | server/model dependent | **`reasoning`** — renamed from `reasoning_content`; migration is a direct field rename | unknown |
| llama.cpp | `--reasoning-format`, `--reasoning-budget N`, `--reasoning-preserve`; request-level `reasoning_effort`, `reasoning_format`, `reasoning_control`; `chat_template_kwargs` (e.g. `{"enable_thinking": false}`) | `--reasoning-format`: `none` (thoughts left in `content`) \| `deepseek` (→ `reasoning_content`) \| `deepseek-legacy` (keeps `<think>` tags **and** fills `reasoning_content`) | see left | unknown |
| LM Studio | model-family dependent | — | **`reasoning_content`** for DeepSeek-R1-class (v0.3.9, experimental, opt-in in Developer settings) vs **`message.reasoning` / `delta.reasoning`** for gpt-oss (v0.3.23) | unknown |
| **Generic** | probe | — | **four incompatible encodings in the wild**: `reasoning_content`, `reasoning`, inline `<think>` tags, and typed blocks. See the generic-row section | **opposite-signed across vendors** — never round-trip reasoning blindly |

---

## Table C — Usage during streaming, finish reason, max-tokens naming

| Provider | Usage during streaming | Finish-reason field and values | Max-tokens field |
|---|---|---|---|
| Anthropic (native) | **Yes, at both ends.** `message_start` carries partial usage (`input_tokens`, cache read/creation, initial `output_tokens`); `message_delta` carries **cumulative** usage plus `stop_reason`. `output_tokens_details.thinking_tokens` only on the final `message_delta` | **`stop_reason`**: `end_turn`, `max_tokens`, `stop_sequence`, `tool_use`, `pause_turn`, `refusal`, `model_context_window_exceeded`. Companions: `stop_sequence`, `stop_details` (refusals only) | **`max_tokens`, required on every request.** Ceiling covers thinking tokens too |
| Anthropic on Bedrock (new) | same (SSE) | same | same |
| Anthropic on Bedrock (legacy) | same, but AWS event-stream encoding rather than SSE | same | same |
| Anthropic on Vertex | same | same | same |
| OpenAI Chat Completions | **Opt-in only** via `stream_options.include_usage` (default null). Then one extra chunk before `[DONE]` with `choices: []`; all other chunks carry `usage: null`. **Interrupted stream may lose it.** `include_obfuscation` also lives here | **`finish_reason`**: `stop`, `length`, `tool_calls`, `content_filter`, `function_call` (deprecated). Nullable in stream chunks | `max_tokens` **deprecated** and incompatible with o-series → `max_completion_tokens` |
| OpenAI Responses | **Always.** `usage` is null on `response.created` / `.in_progress` and populated on `response.completed` | **No `finish_reason`.** `status`: `completed\|failed\|in_progress\|cancelled\|queued\|incomplete`; `incomplete_details.reason`: `max_output_tokens\|max_messages\|content_filter\|steered`. Per-item `status`: `in_progress\|completed\|incomplete` | `max_output_tokens`, **`minimum: 16`** |
| Azure OpenAI | as per surface | as per surface; `content_filter` is a routine terminal state (prompt-level violations are HTTP 400 with `code: "content_filter"` instead) | `max_completion_tokens` on Chat, `max_output_tokens` on Responses; `max_tokens` is listed among **unsupported** parameters for reasoning models |
| Gemini API | Yes — `usageMetadata` rides streamed `GenerateContentResponse` chunks. **Cadence unknown** (docs do not say whether every chunk carries it) | **`candidates[].finishReason`**: `FINISH_REASON_UNSPECIFIED, STOP, MAX_TOKENS, SAFETY, RECITATION, LANGUAGE, OTHER, BLOCKLIST, PROHIBITED_CONTENT, SPII, MALFORMED_FUNCTION_CALL, IMAGE_SAFETY, IMAGE_PROHIBITED_CONTENT, IMAGE_OTHER, NO_IMAGE, IMAGE_RECITATION, UNEXPECTED_TOOL_CALL, TOO_MANY_TOOL_CALLS, MISSING_THOUGHT_SIGNATURE, MALFORMED_RESPONSE, ESCALATION`. Separate `finishMessage` string | `generationConfig.maxOutputTokens` |
| Vertex Gemini | same | same | same |
| Bedrock Converse | **Only in the terminal `metadata` event**, once. Order: `messageStart` → per-block `contentBlockStart`/`Delta`/`Stop` → `messageStop` (carries `stopReason`) → `metadata` (carries `usage` + `metrics`). No incremental usage | **`stopReason`**: `end_turn, tool_use, max_tokens, stop_sequence, guardrail_intervened, content_filtered, malformed_model_output, malformed_tool_use, model_context_window_exceeded` | `inferenceConfig.maxTokens` |
| xAI | `stream_options.include_usage` → **separate usage-only chunk** before `[DONE]`; other chunks have `usage: null` | `finish_reason` documented enum is `stop`, `length`, **`end_turn`**, or null in streaming. **`tool_calls` and `content_filter` are absent from the documented enum** | `max_completion_tokens` (defaults to 128,000 when unset); `max_tokens` marked deprecated but accepted |
| Mistral | **`stream_options` does not exist** — zero occurrences in the published OpenAPI spec. `CompletionChunk.usage` is optional; the chunk it lands on is **unknown** | `finish_reason` non-streaming: `stop, length, `**`model_length`**`, `**`error`**`, tool_calls`. Streaming: `stop, length, error, tool_calls, null` — **`model_length` is absent from the streaming enum** | **`max_tokens` only** |
| DeepSeek | `stream_options.include_usage` supported, but **no separate usage chunk** — usage rides the last content chunk, whose single `choices` element carries no new content and a non-null `finish_reason`. Opposite of xAI/Groq | `stop, length, content_filter, tool_calls, `**`insufficient_system_resource`** | **`max_tokens` only** |
| Groq | `stream_options.include_usage` → separate chunk with **`choices: []`**. Groq-only `stream_options.include_obfuscation` (default **true**). `usage` also carries non-OpenAI `queue_time`, `prompt_time`, `completion_time`, `total_time` | exactly `stop, length, tool_calls, function_call` — **`content_filter` is absent** | `max_completion_tokens`; `max_tokens` deprecated but accepted |
| OpenRouter | **Both toggles are dead** — `usage:{include:true}` and `stream_options:{include_usage:true}` are deprecated no-ops; usage is always included, on an extra chunk just before `[DONE]`. Extra fields: `cost`, `cost_details.upstream_inference_cost`, `cached_tokens`, `cache_write_tokens` | `stop, length, tool_calls, content_filter, function_call`, plus **`error`** for a mid-stream upstream failure at HTTP 200. Also emits **`native_finish_reason`** (upstream's raw value) | both; `max_tokens` deprecated in favour of `max_completion_tokens`; "some providers enforce a minimum of 16" |
| Ollama | **`stream_options.include_usage` IS supported** on `/v1/chat/completions` and `/v1/completions` | **unknown** — never enumerated | **`max_tokens` only** |
| vLLM | not called out in prose — **unknown** | `finish_reason` is an unconstrained string; vLLM adds a non-OpenAI **`stop_reason`** field | both; `max_tokens` carries a deprecation marker in favour of `max_completion_tokens` |
| llama.cpp | standard `usage` including `prompt_tokens_details.cached_tokens`, plus a non-OpenAI **`timings`** object. `include_usage` not separately documented — **unknown** | not enumerated; the function-calling doc shows **`"finish_reason": "tool"`** (non-OpenAI spelling) | `max_tokens` on `/v1/chat/completions`; native `/completion` uses `n_predict`. No `max_completion_tokens` |
| LM Studio | `stream_options.include_usage` supported since v0.3.18 | only `tool_calls` documented (v0.3.15) | `max_tokens`; **`max_completion_tokens` absent** from the supported-payload list |
| **Generic** | **Do not assume a trailing empty-choices chunk exists.** Three behaviours in the wild: opt-in separate chunk, always-on final chunk, and usage riding the last content chunk | **No two vendors share an enum.** Map unknown values to a default; never `match` exhaustively | **`max_tokens` is the portable field**; `max_completion_tokens` is absent at Mistral, DeepSeek, Ollama, llama.cpp, LM Studio |

---

## Table D — Tool results, strict/grammar modes, eager tool-input streaming

| Provider | Tool-result shape and placement | Strict / grammar modes | Eager tool-input streaming |
|---|---|---|---|
| Anthropic (native) | `{"type":"tool_result","tool_use_id":…,"content":…,"is_error":…}` inside a **`user`** message. `content` is *optional*. Must **immediately follow** the tool-use message, and `tool_result` blocks must come **first** in the content array — text before them is a 400. Batching multiple results in one message is the documented parallel pattern. `content` may be `text`, `image`, `document`, or `search_result` blocks (computer/browser toolsets narrow this and require the matching `toolset_name`) | **Real grammar-constrained sampling.** Per-tool `"strict": true`; structured outputs via **`output_config.format`** (not `response_format`, not `output_format`). Unsupported schema keywords: recursive schemas, complex types in `enum`, external `$ref`, `minimum`/`maximum`/`multipleOf`, `minLength`/`maxLength`, array constraints beyond `minItems` 0/1, `additionalProperties` other than `false`. `tool_choice`: `auto\|any\|tool\|none` + `disable_parallel_tool_use`. **`any`/`tool` 400 under manual extended thinking and on Fable 5.1 / Mythos 5.1** | **Yes.** `input_json_delta` with `partial_json` fragments; `content_block_start` carries `input: {}` as a placeholder. Enabled per-tool via **`eager_input_streaming: true`**, or legacy header `fine-grained-tool-streaming-2025-05-14`. No server-side validation — accumulated JSON may be invalid or truncated by `max_tokens` |
| Anthropic on Bedrock (new) | same | **structured outputs not supported** on this endpoint | same |
| Anthropic on Bedrock (legacy) | same | structured outputs **are** supported here | same |
| Anthropic on Vertex | same | structured outputs supported | same |
| OpenAI Chat Completions | `{role:"tool", tool_call_id, content}`, all three required; content parts are **text-only** | `strict: true` on functions (default false); Structured Outputs via `response_format: {type:"json_schema", json_schema:{…}}` (**nested**). Under `strict`, every property must be in `required` and `additionalProperties` must be `false`; optionality is expressed as `"type":["string","null"]`. Custom tools with **`grammar` (`lark` \| `regex`)**. `tool_choice`: `none\|auto\|required` \| allowed-tools \| named. `parallel_tool_calls` default true | **Yes.** `choices[].delta.tool_calls[].function.arguments` fragments; correlation is by **`index`**, not `id` |
| OpenAI Responses | `{type:"function_call_output", call_id, output}` item; only `type` and `output` are required. **`output` may be a string *or* an array of content items** — unlike Chat. Note the item has both `id` and `call_id`; echo `call_id` | same feature set but **flat** nesting: `text: {format: {type:"json_schema", name, schema, strict}}`. This shape difference is a real porting hazard. `tool_choice` union also covers MCP and custom tools | **Yes**, via named events: `response.function_call_arguments.delta/.done`, `response.custom_tool_call_input.delta/.done`, `response.mcp_call_arguments.delta/.done`. Correlation by `item_id`/`output_index` |
| Azure OpenAI | as per surface | as per surface | as per surface |
| Gemini API | `functionResponse` part: `name` **required**, `response` **required and must be a JSON object** (not a bare string), optional `id`, optional `parts[]` for multimodal. Placed in a **`user`**-role `Content` per every worked example. All parallel responses must be returned together | `responseMimeType` (`text/plain`, `application/json`, `text/x.enum`); `responseSchema` and `_responseJsonSchema` are **marked deprecated**, superseded by `generationConfig.responseFormat.text.{mimeType, schema}`. `toolConfig.functionCallingConfig.mode`: `AUTO\|ANY\|NONE\|`**`VALIDATED`** (validated = constrained decoding), with `allowedFunctionNames` only valid under `ANY`/`VALIDATED`. Schemas are an OpenAPI subset; `FunctionDeclaration` takes `parameters` **xor** `parametersJsonSchema` | **No partial-args mechanism is documented.** `Part.functionCall` is `{name, args}`, a whole object; there is no delta representation in the schema. Caveat: a thought signature may arrive in a part with empty text, so parse all parts until `finishReason` |
| Vertex Gemini | same | same | same |
| Bedrock Converse | `toolResult`: `toolUseId` **required** (1–64 chars, `[a-zA-Z0-9_.:-]+`), `content` **required** (array; `json` or `text` blocks), `status` `success\|error` (**Nova and Claude 3/4 only**). Sent in a **`user`** message immediately after the assistant turn. Whether multiple results must be batched into one message is **unknown** | **Both** supported and combinable: `outputConfig.textFormat` with `{"type":"json_schema","structure":{"jsonSchema":{"schema":"<schema as a JSON string>"}}}`, and per-tool `"strict": true`. Draft 2020-12 subset; unsupported features are a **400 at request time**. Grammar compilation can take minutes on first use, then cached 24h. **Incompatible with citations on Anthropic models (400).** `toolChoice`: `any\|auto\|tool` (`tool` = Claude 3 and Nova only) | **Yes.** `ContentBlockStart.toolUse` opens the block, then `ContentBlockDelta.toolUse.input` carries partial JSON as a **string**; concatenate across a `contentBlockIndex` and parse at `contentBlockStop` |
| xAI | standard `{role:"tool", tool_call_id, content}`; no `name` requirement | **No `strict` flag — it is implicitly always true**: "xAI models will always generate tool call arguments that strictly conform to the tool's input JSON Schema". `response_format`: `text\|json_object\|json_schema`. Hard schema limits: `maxLength` ≤2048, `maxItems` ≤256, `maxProperties` ≤64; `not`, `if/then/else` and multi-subschema `allOf` are best-effort only; `additionalProperties` defaults to `false`. No grammars | **Explicitly NO** — "the function call is returned in whole in a single chunk, not streamed across chunks" |
| Mistral | `ToolMessage = {role, content, tool_call_id?, name?}`. `content` **required** (string or content-chunk array); `tool_call_id` **optional and nullable**; `name` **is allowed**. See the folklore correction — there is **no** 9-character `tool_call_id` constraint in the chat API spec | `Function.strict: boolean` (default false); `response_format`: `text\|json_object\|json_schema` (with `JsonSchema.strict`). `tool_choice`: `none\|auto\|`**`any`**`\|required\|`named. No grammars | **unknown** |
| DeepSeek | `{role:"tool", content, tool_call_id}`; `content` typed **string-only, no array**; **no `name` field in the schema** | `tools[].function.strict` exists but is **beta-gated** — requires `base_url=…/beta`; the server validates the schema and errors on unsupported types. `tool_choice`: `none\|auto\|required\|`named. `response_format`: **`text` \| `json_object` only — no `json_schema`** | **unknown** |
| Groq | Docs contradict themselves: the OpenAPI schema allows string *or* array `content` and defines `name` as "DO NOT USE"; the compat page says any `messages[].name` is a **400**; the tool-use guide shows `"tool_calls_id"` (apparent typo) plus `name`. **Safest: `{role, tool_call_id, content}` with no `name`** | `response_format`: `json_object \| json_schema` (supported models only); per-tool `"strict": true` appears in official examples. `tool_choice`: `none\|auto\|required\|`named. Groq-only `disable_tool_validation`. `parallel_tool_calls` default true but **No** for gpt-oss-20b/120b. No grammars | **unknown** |
| OpenRouter | `{role, content, tool_call_id}`; `name` not required. Content-part-array support is ambiguous across doc surfaces → probe | `response_format: {type:"json_schema", json_schema:{strict:true}}` with the honest caveat that enforcement varies per upstream provider (guaranteed / translated / treated as a hint). Also exposes **real grammars**: `type: "grammar"` with a GBNF-style string, and `type: "python"`. `tool_choice` includes `required` in the schema. Per-tool `strict`: unconfirmed | **unknown** |
| Ollama | compat endpoint takes OpenAI tool messages. **Native `/api/chat` uses `tool_name` instead of `tool_call_id`** — do not cross the wires | `response_format` works for structured outputs; native `format` takes `"json"` or a schema. **`tool_choice` is explicitly unsupported.** No `strict` | **not definitively documented.** The tool-calling doc tells callers to gather every chunk of `thinking`/`content`/`tool_calls` and return them together, which is consistent with buffering but is guidance, not a server guarantee |
| vLLM | not documented; template-dependent | `guided_json`/`guided_regex`/`guided_choice`/`guided_grammar` were **deprecated and removed in v0.12.0**, superseded by a unified `{"structured_outputs": {...}}`. `tool_choice`: `auto\|required\|none\|`named; per-tool `strict: true` with global `VLLM_ENFORCE_STRICT_TOOL_CALLING` (default true) | **Yes, eager by design** — the parser plugin contract is `extract_tool_calls_streaming(previous_text, current_text, delta_text, …)` |
| llama.cpp | **not documented** — no `tool_call_id` example anywhere | **Real grammars**: `grammar` (GBNF) and `json_schema` on `/completion`, honoured on `/v1/chat/completions` too. `response_format` accepts `{"type":"json_object","schema":{…}}` **and** `{"type":"json_schema","schema":{…}}` — note the non-standard nesting (`schema` at top level, not under a named wrapper). `tool_choice` is documented **only** for the Anthropic `/v1/messages` endpoint. Tools need `--jinja` | **unknown** |
| LM Studio | standard `{role:"tool", content, tool_call_id}`, with a worked example | `response_format: {type:"json_schema", json_schema:{name, strict:true, schema}}`; GGUF backend uses llama.cpp GBNF, MLX backend uses Outlines. **`tool_choice` is not mentioned at all** | **Yes** — v0.3.17: "Tool-call argument tokens are streamed as they are generated" |
| **Generic** | assume `{role:"tool", tool_call_id, content}` with **string** content; treat `name` as forbidden and array content as optional | assume nothing beyond `response_format: {type:"json_object"}`; probe for `json_schema`, `strict`, and `tool_choice: required` | **must handle both**: a single complete `tool_calls` delta and a stream of `arguments` fragments |

---

## Table E — Cache control, session affinity, auth

| Provider | Cache-control format | Cache accounting | Session-affinity header | Auth modes | Subscription login with separate billing pool |
|---|---|---|---|---|---|
| Anthropic (native) | `cache_control: {"type":"ephemeral","ttl":"5m"\|"1h"}`, **max 4 breakpoints** (automatic caching consumes one). Placeable on system blocks, message content blocks, the last `tools` entry, `tool_use`/`tool_result` blocks — **not** on thinking blocks, citation sub-blocks, or empty text. Prefix order `tools → system → messages`. Minimum cacheable tokens vary 512/1024/2048/4096 **by model** | `usage.cache_creation_input_tokens`, `cache_read_input_tokens`, and `cache_creation.{ephemeral_5m_input_tokens, ephemeral_1h_input_tokens}`. `input_tokens` counts only tokens after the last breakpoint | **none documented.** The closest construct, `diagnostics.previous_message_id` (beta `cache-diagnosis-2026-04-07`), is explicitly diagnostic and does **not** affect routing. `anthropic-workspace-id` is scoping, not affinity | `Authorization: Bearer` (or legacy `x-api-key`), `anthropic-version` **required**; Workload Identity Federation OAuth via `POST /v1/oauth/token`; Apple App Attest (Messages API only, 1h tokens) | **Confirmed separate, but NOT an API auth mode.** Claude Pro/Max login exists only at the Claude Code / Agent SDK layer; "a paid Claude subscription… doesn't include access to the Claude API or Console". Precedence trap: if `ANTHROPIC_API_KEY` is set, Claude Code bills the API key, not the subscription. The OAuth mechanics of subscription login are **undocumented** |
| Anthropic on Bedrock (new) | same | same | none documented | SigV4 (`aws:amz:{region}:bedrock-mantle`), Bedrock service role, IAM assumed roles, or bearer token in `x-api-key` (12h max) | none |
| Anthropic on Bedrock (legacy) | same, except **automatic caching (top-level `cache_control`) is not supported** | same | none documented | SigV4 via the AWS credential chain, or `AWS_BEARER_TOKEN_BEDROCK` | none |
| Anthropic on Vertex | same | same | none documented | Google OAuth bearer / ADC / service account | none |
| OpenAI Chat Completions | **Automatic by default**, plus an explicit layer for gpt-5.6+: `prompt_cache_options.{ttl:"30m", mode:"implicit"\|"explicit"}` and `prompt_cache_breakpoint: {mode:"explicit"}` on content blocks. ≤4 cache writes/request; matching considers up to the latest **80** breakpoints (**Azure says 50**). Minimum 1,024 tokens on GPT-5.6+, 2,048 below. Legacy `prompt_cache_retention` (`in_memory\|24h`) deprecated | `usage.prompt_tokens_details.{cached_tokens, cache_write_tokens}` | **No sticky header.** `prompt_cache_key` (body) "influence[s] routing; [it does] not pin requests to a machine or guarantee a cache read hit". It replaces the deprecated `user` field. `X-Client-Request-Id` is idempotency/correlation, not routing | `Authorization: Bearer`, `OpenAI-Organization`, `OpenAI-Project` | **Documented, but Codex-scoped only.** "Sign in with ChatGPT for subscription access" vs "Sign in with an API key for usage-based access"; the pools are explicitly separate. **No** primary doc says ChatGPT credentials work against `api.openai.com` generally |
| OpenAI Responses | same | `usage.input_tokens_details.{cached_tokens, cache_write_tokens}` | same | same | same |
| Azure OpenAI | same fields; models before GPT-5.6 **return 400** if you send `prompt_cache_options` or `prompt_cache_breakpoint`. PTU-M deployments support neither breakpoints nor `cache_write_tokens`. On GPT-5.5 and earlier, hits occur in **128-token increments** past the first 1,024 | same | none. Azure adds a throughput ceiling: **>~15 req/min per prefix+`prompt_cache_key` combination starts missing the cache**; distribute across keys with a stable mapping | **`api-key` custom header** (not `Authorization`), or Entra ID bearer with scope `https://ai.azure.com/.default`. Classic URL embeds the deployment name and requires `api-version`; the v1 API drops both | none |
| Gemini API | **Two mechanisms.** Explicit: `cachedContents` resource (`model` required and immutable; `ttl` as a seconds string like `"300s"` **xor** `expireTime`), referenced via `cachedContent: "cachedContents/{id}"`. Implicit: on by default for Gemini 2.5+, nothing to enable. **There is no inline per-block cache marker.** Explicit-cache minimum token count is **unknown** | `usageMetadata.cachedContentTokenCount` and `cacheTokensDetails[]`. **`promptTokenCount` includes cached tokens.** Implicit-cache minimums: 4,096 (Gemini 3.x Flash, 3.1 Pro Preview), 2,048 (2.5 Flash/Pro) | **none documented** | API key via `x-goog-api-key` header **or** `?key=` query param; env `GEMINI_API_KEY` / `GOOGLE_API_KEY` (the latter wins); OAuth is documented as the stricter-access exception | **Explicitly not offered for the API.** Google AI Pro/Ultra benefits are "AI Studio UI only"; direct Gemini API use is "billed and managed separately". Gemini Code Assist as an API auth mode is **undocumented** |
| Vertex Gemini | same; `cachedContent` name is fully qualified (`projects/…/locations/…/cachedContents/{id}`) | same | Not affinity, but the documented routing header is `X-Vertex-AI-LLM-Request-Type: dedicated\|shared` (Provisioned Throughput vs pay-as-you-go; over-quota on PT returns **429**). A companion `X-Vertex-AI-LLM-Shared-Request-Type` (`flex`/`priority`) is lower-confidence | OAuth2 bearer / ADC / service account | none |
| Bedrock Converse | `{"cachePoint": {"type": "default"}}` (optional `"ttl": "5m"\|"1h"`) as a content block in `system`, `messages`, or `tools`. **Max 4** for Claude. **Ordering matters:** processed `tools → system → messages`, the minimum is evaluated against the *cumulative* total, and changing an earlier section invalidates later ones. Longer TTLs must appear before shorter ones. Auto-checks previous block boundaries ~20 blocks back. Not available with batch inference | `usage.cacheReadInputTokens`, `cacheWriteInputTokens`, `cacheDetails[]`. **Accounting trap:** `inputTokens` excludes cached tokens — total = `inputTokens + cacheRead + cacheWrite`. Minimums 512 / 1,024 / 4,096 by model | **none documented for `bedrock-runtime`.** `X-Amzn-Bedrock-Request-Metadata` is logging. A real session header exists only in **AgentCore** (`X-Amzn-Bedrock-AgentCore-Runtime-Session-Id`) — a different service; do not conflate | SigV4 + IAM (`bedrock:InvokeModel` / `…WithResponseStream`); **bearer-token API keys** are first-class: short-term (≤12h, inherits IAM principal) or long-term (creates an IAM user), via `AWS_BEARER_TOKEN_BEDROCK` or `Authorization: Bearer` | **none** — everything resolves to an IAM principal |
| xAI | automatic prefix caching | `usage.prompt_tokens_details.cached_tokens` on the JSON surface (`cached_prompt_text_tokens` is the **gRPC SDK attribute name only**); `usage.input_tokens_details.cached_tokens` on Responses. Non-OpenAI extras `cost_in_usd_ticks`, `num_sources_used` | **Yes — the strongest in this set.** Header **`x-grok-conv-id`** routes same-ID requests to the same server to maximise cache hits; body `prompt_cache_key` is plumbed to it | `Authorization: Bearer`, with per-key ACLs and separate `management-api.x.ai` keys | **No API auth mode.** The Grok CLI's OAuth targets `auth.x.ai` → `cli-chat-proxy.grok.com`, a different host/product, not `api.x.ai` |
| Mistral | `prompt_cache_key` exists in the request spec **with no description**, and there is **no prompt-caching guide at all** | **none** — `UsageInfo` has no cached-token fields | none documented; do not assume `prompt_cache_key` implies stickiness | `Authorization: Bearer` only | none documented (no Le Chat API credential) |
| DeepSeek | automatic, always on, prefix-exact, best-effort, no opt-out and no code change | **`prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`** (their sum is `prompt_tokens`) — a shape unique to DeepSeek. Plus `completion_tokens_details.reasoning_tokens` | body **`user_id`** (not OpenAI's `user`; `[a-zA-Z0-9\-_]+`, ≤512) for KVCache and scheduling **isolation**, with per-`user_id` concurrency limits. Isolation, not stickiness | `Authorization: Bearer`. Three base URLs: `/` (OpenAI shape), `/anthropic` (Anthropic Messages shape), `/beta` (prefix + strict tools) | none documented |
| Groq | automatic, no code change, **no additional fee**, 50% input discount, **2-hour idle expiry**, minimum 128–1024 tokens by model, and **only** on `openai/gpt-oss-20b`, `-120b`, `-safeguard-20b`. "No Manual Control" | `usage.prompt_tokens_details.cached_tokens` | none documented | `Authorization: Bearer` only | none |
| OpenRouter | `cache_control: {"type":"ephemeral"}` on a **content part**; Anthropic accepts `"ttl":"1h"` (default 5m). **Auto-cached (no breakpoints):** OpenAI, DeepSeek, Grok, Moonshot, Groq, Z.AI, Gemini 2.5+ implicit. **Explicit breakpoints required:** Anthropic Claude, Alibaba Qwen, Gemini explicit | `prompt_tokens_details.cached_tokens`, `cache_write_tokens`, `cache_discount` | **Richest.** Body `session_id` (≤256) or header **`x-session-id`** used directly as the sticky routing key; implicit stickiness after a cached request. Plus `provider: {order, only, ignore, sort, allow_fallbacks, …}` routing — note that setting `sort` or `order` **disables load balancing**. Attribution headers `HTTP-Referer` and `X-OpenRouter-Title` (legacy `X-Title`) | `Authorization: Bearer`, plus **OAuth PKCE** for provisioning user keys. BYOK is a billing/routing feature, not a separate auth scheme | none |
| Ollama | none documented | none documented | none | local server needs no key (the OpenAI SDK's required key is ignored); `OLLAMA_API_KEY` is for ollama.com cloud only | n/a |
| vLLM | automatic prefix caching (`enable_prefix_caching=True`) | `prompt_tokens_details.cached_tokens`, `completion_tokens_details.reasoning_tokens` | none | `--api-key` / `VLLM_API_KEY`, but it **only guards `/v1`, `/v2`, `/inference` prefixes** — other endpoints on the same server, notably `/invocations`, are unauthenticated | n/a |
| llama.cpp | `cache_prompt` (default `true`), `--cache-reuse N`, `--cache-idle-slots` | `prompt_tokens_details.cached_tokens`, plus the `timings` object (`cache_n`, …) | **Yes — real slot affinity**: request param `id_slot`, `--slot-prompt-similarity`, and `POST /slots/{id_slot}?action=save\|restore\|erase` | `--api-key` / `--api-key-file`, **none by default** | n/a |
| LM Studio | none documented | none documented | none on the OpenAI-compat surface | none by default; optional toggle + `Authorization: Bearer` | n/a |
| **Generic** | assume **no** cache control | assume **no** cached-token fields; four incompatible shapes exist | assume none | `Authorization: Bearer`, or none locally | assume none |

---

## Cross-cutting notes

### Folklore corrections

Three widely-repeated "quirks" did not survive contact with primary docs. Recording
them explicitly so they don't get re-imported later:

1. **Mistral `tool_call_id` is *not* constrained to 9 alphanumeric characters** in the
   chat API. The 9-character rule appears only in the fine-tuning data-format doc
   (where both `id` and `tool_call_id` are described as randomly generated 9-character
   strings). Mistral's published OpenAPI spec puts **no pattern or length constraint**
   on `tool_call_id`, and the field is optional and nullable.
2. **Mistral has no "last message must be user or assistant-with-prefix" API rule.**
   That constraint is fine-tuning *dataset validation*.
3. **Ollama does support `stream_options.include_usage`** on both
   `/v1/chat/completions` and `/v1/completions`; its compatibility matrix marks it
   supported. Relatedly, "Ollama buffers tool arguments" is *not* documented as a
   server guarantee — the docs give caller-side guidance that is merely consistent
   with buffering.

Two more corrections of smaller blast radius: xAI's `cached_prompt_text_tokens` is a
gRPC SDK attribute name, not a JSON field (the JSON surface uses
`prompt_tokens_details.cached_tokens`); and Groq's documented `x_groq` object is
non-streaming metadata containing `{id}` — `x_groq.usage` is not documented.

### The generic OpenAI-compatible row, expanded

**Safe to assume present** (documented by every provider and runtime surveyed):
`POST {base}/v1/chat/completions`; `Authorization: Bearer` (or no auth locally);
`messages[]` with `system`/`user`/`assistant`/`tool`; string `content`; `model`;
`stream: true` as SSE terminated by `data: [DONE]`; `choices[].message.content` and
`choices[].delta.content`; `usage.{prompt_tokens, completion_tokens, total_tokens}` on
the non-streaming response; `tools[]` as `{type:"function", function:{name,
description, parameters}}`; assistant `tool_calls[].{id, function.{name, arguments}}`
with `arguments` as a JSON **string**; `max_tokens`; `temperature`; `stop`;
`GET /v1/models`.

**Must be probed for or treated as optional:** the `developer` role;
`max_completion_tokens`; `stream_options.include_usage`; any specific `finish_reason`
value; every reasoning-serialization field; `tool_choice` (and `required` in
particular); `strict` tools; eager tool-argument streaming; cached-token accounting;
session affinity; content-part arrays in tool results.

**Non-JSON lines in the stream.** DeepSeek emits `: keep-alive` SSE comments *and*
blank lines on non-streaming responses while waiting for inference (closing the
connection after 10 minutes if inference hasn't started); OpenRouter emits
`: OPENROUTER PROCESSING`. A parser must skip comment lines and empty bodies rather
than treating them as malformed frames.

**Unknown-field handling is genuinely unknown as a behavioural claim.** The only hard
evidence is that Mistral's and Groq's published schemas declare
`additionalProperties: false` (implying rejection), and Groq's compat page names four
fields that 400 (`logprobs`, `logit_bias`, `top_logprobs`, `messages[].name`).
Conversely several providers **silently ignore**: xAI (`logprobs` on grok-4.20+,
`web_search_options` filters), DeepSeek (sampling params in thinking mode), vLLM
(`user`). Assume neither behaviour; send the minimal field set. This matters directly
for the brief's free-form sampling-parameter passthrough — verbatim merge into the
request body is safe at some providers and a hard 400 at others.

### Provider-specific stream hazards worth flagging separately

- **Azure's first streamed chunk has an empty `choices` array** (it carries
  `prompt_filter_results`). Any client that indexes `choices[0]` unconditionally
  breaks on Azure and nowhere else.
- **Azure interleaves content-filter annotation chunks** with `"id":""`, `"model":""`,
  an always-empty text field, and `content_filter_offsets` whose `check_offset` never
  decreases. Two filter modes exist (Default buffered vs Asynchronous Filter
  token-by-token, the latter needing api-version ≥ `2024-02-01`).
- **Azure's Responses API reports filtering differently from Chat Completions** — a
  top-level `content_filters` array rather than `prompt_filter_results` /
  `content_filter_results`.
- **Gemini thought signatures can arrive in a part with empty text content**, so a
  streaming client must keep parsing parts until `finishReason` appears rather than
  stopping at the last text-bearing part.

---

## Sources

All accessed 2026-09-07.

**Anthropic** — `platform.claude.com` (note `docs.anthropic.com` / `docs.claude.com`
now redirect there): [`/docs/en/api/messages`](https://platform.claude.com/docs/en/api/messages),
[`/build-with-claude/thinking`](https://platform.claude.com/docs/en/build-with-claude/thinking),
[`/build-with-claude/extended-thinking`](https://platform.claude.com/docs/en/build-with-claude/extended-thinking),
[`/build-with-claude/effort`](https://platform.claude.com/docs/en/build-with-claude/effort),
[`/build-with-claude/mid-conversation-system-messages`](https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages),
[`/build-with-claude/working-with-messages`](https://platform.claude.com/docs/en/build-with-claude/working-with-messages),
[`/build-with-claude/streaming`](https://platform.claude.com/docs/en/build-with-claude/streaming),
[`/build-with-claude/handling-stop-reasons`](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons),
[`/build-with-claude/prompt-caching`](https://platform.claude.com/docs/en/build-with-claude/prompt-caching),
[`/build-with-claude/cache-diagnostics`](https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics),
[`/build-with-claude/structured-outputs`](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
[`/agents-and-tools/tool-use/handle-tool-calls`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls),
[`/tool-use/define-tools`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools),
[`/tool-use/strict-tool-use`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use),
[`/tool-use/fine-grained-tool-streaming`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/fine-grained-tool-streaming),
[`/tool-use/parallel-tool-use`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use),
[`/api/overview`](https://platform.claude.com/docs/en/api/overview),
[`/api/beta-headers`](https://platform.claude.com/docs/en/api/beta-headers),
[`/manage-claude/authentication`](https://platform.claude.com/docs/en/manage-claude/authentication),
[`/build-with-claude/claude-in-amazon-bedrock`](https://platform.claude.com/docs/en/build-with-claude/claude-in-amazon-bedrock),
[`/build-with-claude/claude-on-amazon-bedrock-legacy`](https://platform.claude.com/docs/en/build-with-claude/claude-on-amazon-bedrock-legacy),
[`/build-with-claude/claude-on-vertex-ai`](https://platform.claude.com/docs/en/build-with-claude/claude-on-vertex-ai).
Subscription/billing separation: [support.claude.com 9876003](https://support.claude.com/en/articles/9876003-i-have-a-paid-claude-subscription-pro-max-team-or-enterprise-plans-why-do-i-have-to-pay-separately-to-use-the-claude-api-and-console),
[11145838](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan),
[12304248](https://support.claude.com/en/articles/12304248-manage-api-key-environment-variables-in-claude-code).

**OpenAI** — `platform.openai.com/docs/*` 403s automated fetch and redirects to
[`developers.openai.com/api/docs`](https://developers.openai.com/api/docs); the
normative schema evidence is OpenAI's published spec
[`openai/openai-openapi` `openapi.yaml`](https://github.com/openai/openai-openapi/blob/master/openapi.yaml)
(`info.version: 2.3.0`). Guides used:
[reasoning](https://developers.openai.com/api/docs/guides/reasoning),
[function-calling](https://developers.openai.com/api/docs/guides/function-calling),
[structured-outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[prompt-caching](https://developers.openai.com/api/docs/guides/prompt-caching),
[migrate-to-responses](https://developers.openai.com/api/docs/guides/migrate-to-responses),
[authentication](https://developers.openai.com/api/docs/api-reference/authentication).
Codex subscription auth: [learn.chatgpt.com/docs/auth](https://learn.chatgpt.com/docs/auth),
[help.openai.com 11369540](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan).

**Azure OpenAI** — [reasoning](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/reasoning),
[prompt-caching](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/prompt-caching),
[responses](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses),
[content-streaming](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/content-streaming),
[content-filter](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/content-filter),
[reference](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/reference),
[api-version-lifecycle](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/api-version-lifecycle).

**Google Gemini / Vertex** — [ai.google.dev/api/generate-content](https://ai.google.dev/api/generate-content),
[ai.google.dev/api/caching](https://ai.google.dev/api/caching),
[gemini-api/docs/thinking](https://ai.google.dev/gemini-api/docs/thinking),
[gemini-api/docs/caching](https://ai.google.dev/gemini-api/docs/caching),
[gemini-api/docs/function-calling](https://ai.google.dev/gemini-api/docs/function-calling),
[gemini-api/docs/api-key](https://ai.google.dev/gemini-api/docs/api-key),
[gemini-api/docs/oauth](https://ai.google.dev/gemini-api/docs/oauth),
[gemini-api/docs/google-ai-plans](https://ai.google.dev/gemini-api/docs/google-ai-plans),
[gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits),
[vertex-ai thinking](https://cloud.google.com/vertex-ai/generative-ai/docs/thinking),
[thought-signatures](https://cloud.google.com/vertex-ai/generative-ai/docs/thought-signatures),
[model-reference/inference](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference),
[multimodal/function-calling](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/function-calling),
[provisioned-throughput](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/provisioned-throughput/use-provisioned-throughput).
Sourcing caveat: the ai.google.dev *guides* have been rewritten around the newer
Interactions API and no longer describe `generateContent` semantics; the REST
reference plus the Vertex docs are the authoritative `generateContent` surface.

**AWS Bedrock** — [Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html),
[ConverseStream](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseStream.html),
[Message](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Message.html),
[ToolResultBlock](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ToolResultBlock.html),
[ToolChoice](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ToolChoice.html),
[ToolUseBlockDelta](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ToolUseBlockDelta.html),
[ReasoningContentBlock](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ReasoningContentBlock.html),
[ReasoningContentBlockDelta](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ReasoningContentBlockDelta.html),
[CachePointBlock](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_CachePointBlock.html),
[conversation-inference](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html),
[prompt-caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html),
[structured-output](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html),
[tool-use-client-side](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-client-side.html),
[claude-messages-adaptive-thinking](https://docs.aws.amazon.com/bedrock/latest/userguide/claude-messages-adaptive-thinking.html),
[api-keys](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html),
[troubleshooting-api-error-codes](https://docs.aws.amazon.com/bedrock/latest/userguide/troubleshooting-api-error-codes.html).
AgentCore session stickiness (different service): [runtime-sessions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html).

**xAI** — [chat-completions reference](https://docs.x.ai/developers/rest-api-reference/inference/chat-completions),
[reasoning](https://docs.x.ai/developers/model-capabilities/text/reasoning),
[structured-outputs](https://docs.x.ai/developers/model-capabilities/text/structured-outputs),
[function-calling](https://docs.x.ai/developers/tools/function-calling),
[prompt-caching](https://docs.x.ai/developers/advanced-api-usage/prompt-caching),
[caching usage and pricing](https://docs.x.ai/developers/advanced-api-usage/prompt-caching/usage-and-pricing),
[maximizing cache hits](https://docs.x.ai/developers/advanced-api-usage/prompt-caching/maximizing-cache-hits),
[management API](https://docs.x.ai/developers/management-api-guide),
[gRPC reference](https://docs.x.ai/developers/grpc-api-reference).

**Mistral** — published OpenAPI 3.1 spec [docs.mistral.ai/openapi.yaml](https://docs.mistral.ai/openapi.yaml)
and [docs.mistral.ai/api](https://docs.mistral.ai/api/);
[reasoning](https://docs.mistral.ai/docs/capabilities/reasoning),
[prefix guide](https://docs.mistral.ai/docs/guides/prefix),
[fine-tuning data format](https://docs.mistral.ai/docs/capabilities/finetuning/text-vision-finetuning),
[fine-tuning e2e](https://docs.mistral.ai/docs/guides/finetuning_sections/_03_e2e_examples).

**DeepSeek** — [create-chat-completion](https://api-docs.deepseek.com/api/create-chat-completion),
[thinking_mode](https://api-docs.deepseek.com/guides/thinking_mode),
[chat_prefix_completion](https://api-docs.deepseek.com/guides/chat_prefix_completion),
[multi_round_chat](https://api-docs.deepseek.com/guides/multi_round_chat),
[tool_calls](https://api-docs.deepseek.com/guides/tool_calls),
[kv_cache](https://api-docs.deepseek.com/guides/kv_cache),
[rate_limit](https://api-docs.deepseek.com/quick_start/rate_limit),
[error_codes](https://api-docs.deepseek.com/quick_start/error_codes).

**Groq** — [OpenAI compatibility](https://console.groq.com/docs/openai),
[API reference](https://console.groq.com/docs/api-reference),
[reasoning](https://console.groq.com/docs/reasoning),
[prefilling](https://console.groq.com/docs/prefilling),
[tool use](https://console.groq.com/docs/tool-use/overview),
[prompt caching](https://console.groq.com/docs/prompt-caching),
[errors](https://console.groq.com/docs/errors).
Note the prose reasoning page is staler than the API reference; prefer the latter.

**OpenRouter** — [chat completion reference](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion),
[reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens),
[usage accounting](https://openrouter.ai/docs/guides/administration/usage-accounting),
[streaming](https://openrouter.ai/docs/api-reference/streaming),
[errors and debugging](https://openrouter.ai/docs/api_reference/errors-and-debugging),
[tool calling](https://openrouter.ai/docs/guides/features/tool-calling),
[prompt caching](https://openrouter.ai/docs/features/prompt-caching),
[provider routing](https://openrouter.ai/docs/features/provider-routing),
[app attribution](https://openrouter.ai/docs/app-attribution),
[OAuth PKCE](https://openrouter.ai/docs/api-reference/o-auth).

**Local runtimes** — Ollama:
[openai-compatibility](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx)
(note `docs/openai.md` is now a 404),
[thinking](https://github.com/ollama/ollama/blob/main/docs/capabilities/thinking.mdx),
[tool-calling](https://github.com/ollama/ollama/blob/main/docs/capabilities/tool-calling.mdx),
[authentication](https://github.com/ollama/ollama/blob/main/docs/api/authentication.mdx).
vLLM: [online serving](https://docs.vllm.ai/en/latest/serving/online_serving/),
[reasoning outputs](https://docs.vllm.ai/en/latest/features/reasoning_outputs/),
[structured outputs](https://docs.vllm.ai/en/latest/features/structured_outputs/),
[tool calling](https://docs.vllm.ai/en/latest/features/tool_calling/).
llama.cpp: [server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
LM Studio: [chat completions](https://lmstudio.ai/docs/developer/openai-compat/chat-completions),
[tools](https://lmstudio.ai/docs/developer/openai-compat/tools),
[API changelog](https://lmstudio.ai/docs/developer/api-changelog),
[authentication](https://lmstudio.ai/docs/developer/core/authentication).

---

## Consolidated unknowns

Cells left deliberately blank, with the reason. Each is a candidate for a follow-up
probe against a live endpoint — which this ticket explicitly did not do.

| Provider | Axis | Why unknown |
|---|---|---|
| OpenAI (both surfaces) | message ordering | No alternation rule, tool-message adjacency rule, or error text in any OpenAI primary doc. The familiar 400 string is community-sourced. |
| OpenAI | strict JSON-Schema keyword exclusions | The guide states exclusions exist but the retrieved content does not enumerate them. |
| OpenAI Responses | attachment point for `ResponseFormatTextGrammar` / `ResponseFormatTextPython` | Present in the spec but not members of the `TextResponseFormatConfiguration` union; the custom-grammars guide was not retrieved. |
| Azure | whether `include: ["reasoning.encrypted_content"]` works on all api-versions | Changelog confirms arrival in v1 preview; no per-version matrix located. |
| Gemini | alternation / first-message / last-message rules | Not stated in the REST reference or the Vertex reference; no error code documented. |
| Gemini | required role for `functionResponse` | Reference text says `"function"`, every example says `"user"` — the docs contradict themselves. |
| Gemini | `usageMetadata` cadence in streaming | Reference says only "a stream of `GenerateContentResponse` instances". |
| Gemini | error on `functionResponse.name` mismatch | Not documented. |
| Gemini | whether the wire ever splits a `functionCall` | No partial-args representation exists in the schema; cadence unstated. |
| Gemini | explicit `cachedContents` minimum token count | The current caching guide covers implicit caching only; the reference states no minimum. |
| Gemini | Gemini Code Assist as an API auth mode | Not documented; Google AI Pro/Ultra is explicitly AI-Studio-UI-only. |
| Vertex Gemini | "no free tier" as a quotable claim | Not asserted on any primary page read (the Gemini API free tier *is* documented). |
| Bedrock Converse | alternation enforcement and its error | Neither the Converse guide nor the troubleshooting page states a role-ordering rule. |
| Bedrock Converse | whether multiple `toolResult` blocks must batch into one user message | AWS's own example appends one message per result; no rule stated. |
| Mistral | which chunk carries `usage` in a stream | `stream_options` does not exist in the spec; `CompletionChunk.usage` is optional with no cadence stated. |
| Mistral | eager tool-input streaming | Not stated anywhere. |
| Mistral | `prompt_cache_key` semantics | Field exists in the request spec with no description and no caching guide. |
| DeepSeek | eager tool-input streaming | Not stated. |
| Groq | eager tool-input streaming | Not stated. |
| Groq | tool-message `name` handling | Schema, compat page, and tool-use guide give three mutually inconsistent answers. |
| OpenRouter | eager tool-input streaming; per-tool `strict`; content-part arrays in tool results | Not stated / ambiguous across doc surfaces. |
| Ollama | `finish_reason` value set | Never enumerated. |
| Ollama | whether tool arguments are ever streamed partially | Caller-side guidance only, not a server guarantee. |
| vLLM | `include_usage` support | Not called out in prose. |
| llama.cpp | tool-result shape; `finish_reason` set; eager streaming | No `tool_call_id` example anywhere; the one observed value is the non-OpenAI `"tool"`. |
| LM Studio | `finish_reason` set beyond `tool_calls` | Not enumerated. |
| All | unknown-request-field handling (reject vs ignore) | No provider documents it as a behavioural contract; the only evidence is schema-level `additionalProperties: false` at Mistral and Groq, and four named 400 fields at Groq. |
| Anthropic | complete `anthropic-beta` value list | No master enumeration is published; the values recorded here are only those appearing inline across feature pages. |
| Anthropic | subscription-login OAuth mechanics | Documented as a product behaviour in support articles, never as an API surface. |
| Anthropic on Vertex | body-level `anthropic_beta` array | Not documented on the primary Vertex page; do not assume. |

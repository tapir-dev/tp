# Per-provider image and binary-attachment encoding — raw catalogue

Research output for [tapir-dev/tp#34](https://github.com/tapir-dev/tp/issues/34).

**Scope.** How an image, and how a non-image binary attachment, is encoded on the wire
for the four v1 provider surfaces — in an ordinary user message, and inside a tool
result. This axis was **not** among the five catalogued in
[#10](https://github.com/tapir-dev/tp/issues/10)
(`docs/research/provider-quirks.md`), so it is a gap-fill, not a revision: nothing here
supersedes that document, and the two are meant to be read together. This is the *raw
catalogue only*. How the content-block vocabulary is represented in `tp` is #34's own
decision and is deliberately not designed here.

**Method.** Official primary provider documentation and published machine-readable
schemas only. No API calls were made and no credentials were used. Every non-obvious
claim is traceable to a URL in the Sources section. Three of the four surfaces publish
a machine-readable artefact, and where one exists it was treated as more normative than
prose:

| Surface | Normative artefact used |
|---|---|
| OpenAI Chat Completions | [`openai/openai-openapi` `openapi.yaml`](https://github.com/openai/openai-openapi/blob/master/openapi.yaml), `info.version: 2.3.0`, `openapi: 3.1.0` |
| Gemini `generateContent` | the API discovery document, `GET https://generativelanguage.googleapis.com/$discovery/rest?version=v1beta` |
| Anthropic Messages | **no published spec file** — the rendered API reference is the only schema surface |
| Generic OpenAI-compatible | each runtime's own repo docs; Ollama publishes `docs/openapi.yaml` but it covers only the *native* API |

**Doc access date: 2026-09-08.** These APIs drift; treat every cell as stale after a
few months and re-verify against the linked source before relying on it.

**Reading the tables.** Same marker vocabulary as `provider-quirks.md`:

- `unknown` means *not confirmable from primary docs* — not "no" and not "probably".
- `none documented` means the docs were searched for the feature and it is absent,
  which is a stronger claim than `unknown`.
- Where two primary pages from the same vendor disagree, the cell says so rather than
  picking a winner. Three such conflicts exist and are called out under
  **Primary-source conflicts**.
- Model-gated behaviour is called out inline. Unlike the reasoning axis, image
  behaviour is *mostly* per-provider; the per-model variation that does exist is
  concentrated in limits and token accounting, not in wire format.

**Row set.** Provider rows are the same in every table, in this order:

| # | Row | Surface |
|---|---|---|
| 1 | Anthropic (native) | `POST api.anthropic.com/v1/messages` |
| 2 | OpenAI Chat Completions | `POST api.openai.com/v1/chat/completions` |
| 3 | Gemini API | `POST generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` |
| 4 | **Generic OpenAI-compatible** | the portable subset a client may assume across Ollama / vLLM / llama.cpp / LM Studio |

---

## Table A — Image encoding in an ordinary user message

| Provider | Block/part shape | Source variants | Data-URI accepted? | Fidelity knob |
|---|---|---|---|---|
| Anthropic (native) | `{"type":"image","source":{…}}` as an element of `messages[].content[]`. Optional siblings on the block: `cache_control`, `transformations` | **three**: `{"type":"base64","media_type":…,"data":…}` (all three required); `{"type":"url","url":…}` (**no `media_type` field**); `{"type":"file","file_id":…}`. **On Bedrock and Google Cloud only `base64` is available** | n/a — base64 is its own source type, not a URI scheme | `transformations: {"oversized_image": "downsize" \| "error"}`. `downsize` is the behaviour when the field is omitted; `error` turns a would-be-resize into a 400 |
| OpenAI Chat Completions | `{"type":"image_url","image_url":{"url":…,"detail":…}}` as an element of `messages[].content[]`. Optional sibling on the part: `prompt_cache_breakpoint`. **`image_url` is an object**; only `url` is required | **one**: the `url` string, documented as *"Either a URL of the image or the base64 encoded image data."* **No `file_id` field on the image part** | **yes** — `data:image/jpeg;base64,…`. Verified in the vision guide's data-URL construction; **no Chat-Completions-specific worked example uses it** (the guide's base64 examples are Responses-shaped), so the pairing is inferred | `image_url.detail`, schema enum **`auto` \| `low` \| `high`**, `default: auto`. The vision guide additionally names **`original`**, which is *not* in the Chat Completions enum — see conflicts |
| Gemini API | a `Part` inside `contents[].parts[]`. Two relevant union members: `{"inlineData":{"mimeType":…,"data":…,"displayName":…}}` and `{"fileData":{"fileUri":…,"mimeType":…,"displayName":…}}`. `fileUri` is **Required**; `fileData.mimeType` is **Optional** | **two**: inline base64 (`Blob`), or a Files-API URI (`FileData`). There is no third form; an ordinary public http URL is not a documented `fileData.fileUri` value | n/a — `inlineData.data` is a bare base64 string, no `data:` prefix | `generationConfig.mediaResolution` (bare enum string) **and**, on Gemini 3 only, per-part `Part.mediaResolution` (an **object** `{"level": …}`). Per-part wins where both are set |
| **Generic** | assume `content` may be **a string**; assume nothing about arrays. Where parts exist, `{"type":"image_url", …}` is the only shape any runtime documents | assume **base64 only**. `http(s)` URL fetch is verified at vLLM and llama.cpp and **explicitly unsupported at Ollama** | **the only portable form**, and even then only at 3 of 4 runtimes | **do not send `detail`** — vLLM documents it as not supported and the other three never mention it |

`Part` is a tagged union by presence, not by a discriminator string. Its full member
set from the discovery document, `Part.data`: `text`, `inlineData`, `fileData`,
`functionCall`, `functionResponse`, `executableCode`, `codeExecutionResult`,
`toolCall`, `toolResponse`. Non-union sibling fields on the same object: `thought`,
`thoughtSignature`, `partMetadata`, `mediaResolution`, `mediaProcessing`,
`audioTranscription`, `videoMetadata` (the last now marked deprecated in favour of
`GenerateContentRequest.processing_options`).

### Where each part type is legal, by role — OpenAI Chat Completions

Verified from spec 2.3.0. This table is the sharpest single constraint on the whole axis.

| Part | `user` | `assistant` | `tool` | `system` | `developer` |
|---|---|---|---|---|---|
| `text` | yes | yes | yes | yes | yes |
| `image_url` | **yes** | no | **no** | no | no |
| `input_audio` | **yes** | no | no | no | no |
| `file` | **yes** | no | no | no | no |
| `refusal` | no | yes (exactly one) | no | no | no |

The union aliases are explicit: `ChatCompletionRequestToolMessageContentPart` and
`ChatCompletionRequestSystemMessageContentPart` are each a `oneOf` with **exactly one
member**, `ChatCompletionRequestMessageContentPartText`; the developer message inlines
the text part directly. The prose is equally explicit — *"For tool messages, only type
`text` is supported."*

Anthropic has no role-based restriction of this kind, because it has no `tool` role:
`image` blocks are legal anywhere in `messages[].content[]`, including inside
`tool_result.content`. Gemini likewise has no `tool` role — but see Table D; its
restriction is expressed structurally instead.

---

## Table B — Accepted MIME types

| Provider | Images | Documents / other | Behaviour on an unsupported type |
|---|---|---|---|
| Anthropic (native) | **`image/jpeg`, `image/png`, `image/gif`, `image/webp`** — a closed enum on `Base64ImageSource.media_type`. *"Animations are unsupported, and only the first frame is used."* | `document` blocks: **`application/pdf`** and **`text/plain`** only. *"Binary formats such as .xlsx or .docx are not supported in document blocks and must be converted to text or PDF first."* | **none documented** for an image MIME violation. The nearest documented case is Files-API-specific: *"Invalid file type (400): The file type doesn't match the content block type (for example, using an image file in a document block)."* A 400 on enum violation is inferred, not stated |
| OpenAI Chat Completions | **PNG (`.png`), JPEG (`.jpeg`/`.jpg`), WEBP (`.webp`), non-animated GIF (`.gif`)** | `file` part: PDF; text/code (`.txt`, `.md`, `.json`, `.html`, `.xml`, code); `.doc`/`.docx`/`.rtf`/`.odt`; `.ppt`/`.pptx`; `.csv`/`.xls`/`.xlsx`. PDFs on vision-capable models have **both text and page images** extracted; non-PDF files are **text-extraction only**. `input_audio`: **`wav`, `mp3`** only | **none documented** for MIME. The only documented rejection is dimensional: *"Images that exceed the 30,000-patch limit after processing are rejected, not automatically resized to meet it."* |
| Gemini API | Two primary pages disagree. Guide: `image/png`, `image/jpeg`, `image/webp`, `image/heic`, `image/heif`. Schema (`Blob.mimeType` description in the discovery doc): the same plus **`image/jpg`, `image/gif`, `image/avif`** | Same `Blob`/`FileData` mechanism carries everything. Schema-listed: audio `audio/*`, `video/audio/s16le`, `video/audio/wav`; video `video/*`; text `text/plain`, `text/html`, `text/css`, `text/javascript`, `text/x-typescript`, `text/csv`, `text/markdown`, `text/x-python`, `text/xml`, `text/rtf`, `video/text/timestamp`; applications `application/x-javascript`, `application/x-typescript`, `application/x-python-code`, `application/json`, `application/x-ipynb+json`, `application/rtf`, **`application/pdf`** | For `FunctionResponseBlob` specifically, verbatim: *"If an unsupported MIME type is provided, an error will be returned."* For an ordinary `Blob`: **none documented** |
| **Generic** | **the safe intersection is PNG + JPEG.** llama.cpp: whatever `stb_image` accepts (*"jpeg, png, tga, bmp, gif, …"*). LM Studio: *"JPEG, PNG, and WebP"* (stated on the SDK pages, scoped to "the LM Studio server"). Ollama and vLLM: **none documented** | **PDF: none documented by any of the four runtimes.** There is no PDF path over any of these OpenAI-compatible endpoints. Audio/video parts exist at vLLM and llama.cpp only | **none documented** anywhere |

---

## Table C — Documented size, dimension and count limits

| Provider | Per-image bytes | Pixels / dimensions | Count per request | Whole-request cap | base64-vs-URL asymmetry |
|---|---|---|---|---|---|
| Anthropic (native) | **10 MB (base64-encoded)** on the Claude API; **5 MB (base64-encoded)** on Bedrock and Google Cloud; 10 MB on claude.ai. **No URL-sourced byte limit is documented** — every published figure is qualified "(base64-encoded)" | **8000×8000 px** maximum. Above 20 image blocks in a request, *"a stricter per-image dimension limit applies to every image in that request"* — the numeric value is **not published**; the doc says the 400 message reports it, and offers **2000 px** only as safe guidance. Resolution tiers: high-res (Claude 4.7+) long edge **2576 px** / **4784** visual tokens; standard **1568 px** / **1568** visual tokens | **100 per request** for 200k-context models, **600 per request** for all others; 20 per message on claude.ai. All `image` blocks count, including resent earlier turns **and images nested in `tool_result.content`** | **32 MB** (Messages API). Batch 256 MB, Files 500 MB. Over → 413 `request_too_large` | asymmetric in the *limit's scope*, not its value: the byte cap is stated only for base64 |
| OpenAI Chat Completions | **none documented.** The historically-cited 20 MB figure is absent from current docs. For `file` parts: *"each file must be under 50 MB. The combined limit across all files in the request is 50 MB."* | **30,000 patches per image after resizing**, applied *"to each image separately, not to the combined patch count of the request"*; over-limit → rejected, **not** resized. Per-model+`detail` sizing table: `low` fits 512×512; `high` 2048 px max dim + 2,500 patches; `original` up to 10,000 patches / 6000 px, or preserved dims capped at 65,535 px depending on family | **1,500 images per request** | **512 MB total payload per request** | **none documented.** Only the single 512 MB payload cap exists, which base64 inflates by roughly a third — that consequence is not stated by OpenAI |
| Gemini API | **conflicting.** Image guide: *"Inline image data limits your total request size (text prompts, system instructions, and inline bytes) to 20MB. For larger requests, upload image files using the File API."* Files guide: *"Always use the Files API when the total request size … is larger than 100 MB. For PDF files, the limit is 50 MB."* Vertex reference: inline `data` *"Size limit: 7 MB for images"* | **no image resize or max-dimension rule is documented.** Vertex states *"There is no limit on image resolution."* Resizing **is** documented for PDF pages: scaled down to a max of **3072×3072** preserving aspect ratio, small pages scaled up to **768×768** | **3,600 image files per request** | governed by the Files-API threshold above, not by a separate stated cap | this **is** the asymmetry: inline bytes are capped by a request-total threshold, `fileData` is not. Files API: **2 GB per file**, **20 GB per project**, **files deleted after 48 hours**, free of charge |
| **Generic** | **none documented by any runtime.** No byte cap is advertised anywhere | none documented as pixels. Orthogonal knobs exist: llama.cpp `--image-min-tokens` / `--image-max-tokens` / `--mtmd-batch-max-tokens` (default 1024) | vLLM `--limit-mm-per-prompt.image N` is an item **count** cap set by the operator. Multi-image support is documented only at vLLM | none documented. vLLM documents fetch **timeouts** instead: `VLLM_IMAGE_FETCH_TIMEOUT` default **5 s**, `VLLM_AUDIO_FETCH_TIMEOUT` default **10 s** | n/a — assume no limit is advertised and handle 4xx/5xx |

**Token accounting**, since it is the practical limit more often than bytes are:

| Provider | Rule |
|---|---|
| Anthropic | patch-based: *"Each patch is a 28×28-pixel block … An image, therefore, costs `⌈width / 28⌉ × ⌈height / 28⌉` visual tokens."* Downsizing picks the largest aspect-preserving size satisfying both the tier's edge limit and its visual-token budget, then pads to the next multiple of 28 on the bottom and right. PDF pages additionally cost **1,500–3,000 text tokens per page** |
| OpenAI | **two schemes coexist.** Tile-based on the `gpt-4o` / `gpt-4.1` / `gpt-5` / `gpt-5.1` / `o1` / `o3` families: base + tile tokens over 512 px squares, after fitting to 2048×2048 and shrinking the short side to 768 px. Base/tile pairs 85/170 (`gpt-4o`, `gpt-4.1`), 70/140 (`gpt-5`, `gpt-5.1`), 2833/5667 (`gpt-4o-mini`), 75/150 (`o1`, `o1-pro`, `o3`). Patch-based on newer families: 32×32 px patches, `patch_count = ceil(width/32) × ceil(height/32)`, then `shrink_factor = sqrt((32^2 * patch_budget) / (width * height))`. On the patch scheme, *"`low` does not always use fewer tokens than `high`"* |
| Gemini | pre-Gemini-3: **258 tokens** if both dimensions ≤ 384 px, else tiled into **768×768** tiles at 258 tokens each. Gemini 3: flat per-item budgets driven by `mediaResolution` — image 280 / 560 / 1120 / 2240 for low / medium / high / ultra_high, default 1120; PDF 280 / 560 / 1120 plus untaxed native text; video 70 / 70 / 280. PDF-page tokens report under the **`IMAGE`** modality in `usageMetadata` on Gemini 3, not a separate document modality |
| **Generic** | none documented |

---

## Table D — Images inside a tool result

This is the axis on which the four surfaces are least alike, and the one #34 has to
absorb.

| Provider | Carrier | Can it hold an image? | Exact nesting |
|---|---|---|---|
| Anthropic (native) | `{"type":"tool_result","tool_use_id":…,"content":…}` inside a **`user`** message | **Yes.** *"These content blocks can use the `text`, `image`, `document`, or `search_result` types."* The rendered schema for the `content` array additionally admits `ToolReferenceBlockParam` and `BrowserStateBlockParam` | `content` is a string, or an array of blocks; an image is the ordinary `image` block verbatim, nested one level deeper |
| OpenAI Chat Completions | `{"role":"tool","tool_call_id":…,"content":…}` | **No.** `content` is `string \| array<ChatCompletionRequestToolMessageContentPart>`, and that union has exactly one member — the text part. Schema prose: *"For tool messages, only type `text` is supported."* | n/a |
| Gemini API | a `functionResponse` `Part`, in a `Content` whose `role` is **`"user"`** | **Yes, but only through a dedicated sub-type.** `FunctionResponse.parts[]` is an array of `FunctionResponsePart`, and `FunctionResponsePart` is a union with **exactly one member: `inlineData`**, of type `FunctionResponseBlob` (`mimeType`, `data`). **No `text`, no `fileData`** | image bytes go in `functionResponse.parts[].inlineData`; the structured `response` object references them by `{"$ref": "<displayName>"}` |
| **Generic** | `{"role":"tool", …}` | **none documented** at any of the four runtimes — every relevant page was searched. Assume text-only | n/a |

Verbatim Anthropic example:

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_01A09q90qw90lq917835lq9",
      "content": [
        { "type": "text", "text": "15 degrees" },
        {
          "type": "image",
          "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": "/9j/4AAQSkZJRg..."
          }
        }
      ]
    }
  ]
}
```

Verbatim Gemini example (documented as **Gemini 3 series only**):

```json
{
  "role": "user",
  "parts": [{
    "functionResponse": {
      "name": "get_image",
      "id": "UNIQUE_CALL_ID_HERE",
      "response": { "image_ref": { "$ref": "instrument.jpg" } },
      "parts": [{
        "inlineData": {
          "displayName": "instrument.jpg",
          "mimeType": "image/jpeg",
          "data": "<base64>"
        }
      }]
    }
  }]
}
```

Rules attached to that form, verbatim: *"Each multimodal part must contain
`inlineData`. If you reference a multimodal part from within the structured `response`
field, it must contain a unique `displayName`."* … *"Each `displayName` can only be
referenced once in the structured `response` field."* The `$ref` is optional — `parts[]`
may be sent with no reference from `response`. The MIME allowlist for this path is
**narrower** than for an ordinary `Blob`: images `image/png`, `image/jpeg`,
`image/webp`; documents `application/pdf`, `text/plain`.

**On the existing doc's "text-only" claim for OpenAI tool messages.** It is correct, and
now has a schema citation rather than folklore behind it. Two refinements: the
constraint is *schema-declared*, and OpenAI does **not** document the runtime behaviour
of sending an `image_url` part in a tool message — whether the endpoint 400s, silently
drops the part, or coerces it is **unknown**. Do not record a guessed error string.

**On Anthropic's ordering constraints for tool results** — unchanged from
`provider-quirks.md` Table D, restated because they interact with image placement:
`tool_result` blocks must immediately follow their `tool_use` message, must come first
in the content array (text before them is a 400), and if the assistant turn also called
an unresolved server tool the user message must contain **only** `tool_result` blocks.

**Sizing exception for Anthropic tool-result images** — the one place the API rejects
instead of downscaling: *"the API rejects a `tool_result` image that exceeds the model's
limits with a validation error instead of downscaling it, so resize those images in your
application before returning them."* This is scoped to screenshots and zoom images
returned to the computer-use and browser-use toolsets. Those toolsets also narrow
`tool_result.content` to `text` and `image` only (plus one `browser_state` block for
browser use), and require the result to echo the `tool_use` block's `toolset_name`
(`"computer"` or `"browser"`) or be rejected.

**Sibling-part escape hatch on Gemini: `none documented`.** Whether a plain
`{"inlineData": …}` part may sit as a sibling of `{"functionResponse": …}` in the same
`user` `Content` is neither permitted nor forbidden anywhere primary. It is structurally
expressible — `Content.parts[]` is an unconstrained repeated `Part` and *"Parts may have
different MIME types"* — but no primary statement supports it, and only the nested route
ties the image to the call via `id` / `$ref`.

---

## Table E — Non-image binary and documents

| Provider | Dedicated block? | Shape | Limits |
|---|---|---|---|
| Anthropic (native) | **Yes** — `document`, a first-class content block | `{"type":"document","source":{…},"title":…,"context":…,"citations":{"enabled":true},"cache_control":…}`. **Five** `source.type` variants: `base64` (+`media_type:"application/pdf"`, `data`), `text` (+`media_type:"text/plain"`, `data`), `content` (`content`: string or array of blocks), `url` (`url`), `file` (`file_id`). `title` is `minLength 1, maxLength 500`; `context` is `minLength 1`; both are passed to the model but are **not citable** | **32 MB** request; **600 pages per request, 100 when the request's context window is under 1M tokens**; *"Standard PDF (no passwords/encryption)"*. **All active models support PDF processing**; no beta header. `document` blocks accept `cache_control` |
| OpenAI Chat Completions | **Yes** — a `file` content part, legal in `user` messages | `{"type":"file","file":{"filename":…,"file_data":…,"file_id":…}}`. `file_data` is a **data URL**, e.g. `"data:application/pdf;base64,…"`, sent alongside `filename`. **No property inside `file` is marked required** and there is no `oneOf` enforcing `file_id` XOR (`filename` + `file_data`) — that pairing is documented only by example. **No `file_url` field on this surface** (that form exists only on Responses `input_file`) | 50 MB per file, 50 MB combined. **Page-count limit: none documented** — the historically-cited 100-page figure is absent. Files API `purpose` for model inputs is `user_data`; the enum is `assistants \| batch \| fine-tune \| vision \| user_data \| evals`. **`detail` is explicitly not supported on Chat Completions file inputs**, verbatim: *"Chat Completions file inputs don't support `detail`."* |
| Gemini API | **No.** A PDF is an ordinary `inlineData` or `fileData` part with `mimeType: "application/pdf"` | `{"inlineData":{"mimeType":"application/pdf","data":"<b64>"}}` | *"Gemini supports PDF files up to 50MB or 1000 pages. This limit applies to both inline data and Files API uploads. Each document page is equivalent to 258 tokens."* Non-PDF document types are accepted but *"document vision only meaningfully understands PDFs. Other types will be extracted as pure text."* |
| **Generic** | **none documented.** No `{"type":"file"}` part at any of the four runtimes, and **no PDF path over any OpenAI-compatible endpoint** | vLLM and llama.cpp document non-image *media* parts instead: vLLM `{"type":"input_audio","input_audio":{"data":…,"format":"wav"}}`, `{"type":"audio_url","audio_url":{"url":…}}`, `{"type":"video_url",…}`, `{"type":"image_embeds","image_embeds":<b64 tensor>}`; llama.cpp `{"type":"input_audio"}` (miniaudio: mp3, wav, flac; `input_audio.format` is **ignored**) and `{"type":"input_video"}` (ffmpeg formats) | none documented |

Anthropic's `document` block also carries the citation machinery, which is why its
`source` union is five-wide rather than three: citation granularity is a function of
the source type.

| `source.type` | Chunking | Citation block `type` | Index fields |
|---|---|---|---|
| `text` | sentence | `char_location` | `start_char_index`/`end_char_index`, 0-indexed, exclusive end |
| `base64` / `url` / `file` (PDF) | sentence | `page_location` | `start_page_number`/`end_page_number`, 1-indexed, exclusive end |
| `content` | none | `content_block_location` | `start_block_index`/`end_block_index`, 0-indexed, exclusive end |

Two constraints worth carrying: *"citations must be enabled on all or none of the
documents within a request"*, and *"Only text citations are currently supported. Image
citations are not yet possible."*

The adjacent `search_result` block is explicitly **not** an image carrier: *"Search
results hold text only. Images and other media are not supported inside the `content`
array."* It is usable both as top-level user content and inside `tool_result`.

---

## Table F — Per-model variation within a surface

| Provider | Which models accept images | What varies per model |
|---|---|---|
| Anthropic (native) | *"All current models support text and image input, text output, multilingual capabilities, vision, and tool use."* Files page: *"Images are supported on all current Claude models."* | **Resolution tier** — Claude 4.7 and later get 2576 px / 4784 visual tokens; everything else 1568 px / 1568. **Max images per request** — 100 for 200k-context models, 600 otherwise. **Max PDF pages** — 600, or 100 under a 1M context window. **Cache minimum tokens** varies (512 / 1,024 / 2,048 / 4,096 by model). `search_result` is supported on all active models except Claude Haiku 3. **Per-model differences in supported `source` types: none documented** — the only split is by *platform* (Bedrock and Google Cloud are base64-only; Microsoft Foundry Azure-hosted deployments have no Files API) |
| OpenAI Chat Completions | *"All latest OpenAI models support text and image input, text output, multilingual capabilities, and vision."* — a blanket statement, **not an enumerated matrix**. A definitive per-model "accepts images: yes/no" list is **none documented** | **Supported `detail` values and the sizing scheme.** `gpt-5.6-*`, `gpt-5.5`, `gpt-5.4`/`-mini`/`-nano` support `low, high, original, auto`; `gpt-5.2` and `gpt-4.1-mini` support `low, high, auto` (*"`original` is not supported"*); `gpt-5.1`, `gpt-4.1`, `gpt-4o`, `gpt-4o-mini` support `low, high, auto` and use tile-based sizing. Caveat verbatim: *"Other models and specialized variants can use different limits."* Base/tile token pairs also differ per family |
| Gemini API | *"All Gemini model versions are multimodal."* **No per-model image-limit table exists on ai.google.dev.** Vertex defers: *"For limits on the inputs, such as … the number of images, see the model specifications on the Google models page"* | **Token accounting changes generation-over-generation** — the 258-per-768×768-tile model is pre-Gemini-3; Gemini 3 uses flat `mediaResolution` budgets, and *"The token count for [unspecified] varies significantly between Gemini 3 and earlier Gemini models."* **Per-part `Part.mediaResolution` is Gemini 3 only**, marked experimental, `v1beta` only. **`MEDIA_RESOLUTION_ULTRA_HIGH` exists per-part only.** **Multimodal `functionResponse.parts[]` is documented as Gemini 3 series only.** `Part.mediaProcessing: AGENTIC` requires Gemini 3.5+; unsupported models fall back to `STATIC` |
| **Generic** | model must be a VLM at all four runtimes. The **capability probe differs per runtime**: Ollama `GET /api/show` → `capabilities: ["completion","vision"]`; llama.cpp `GET /props` → `modalities.vision` plus `media_marker`, or `GET /models` → `architecture.input_modalities`; LM Studio `GET /api/v1/models` → `capabilities.vision`; vLLM has a supported-models list rather than a runtime probe | llama.cpp additionally needs an **mmproj** (multimodal projector) loaded: `-mm/--mmproj FILE`, `-mmu/--mmproj-url URL`, `--mmproj-auto`/`--no-mmproj` (auto-downloaded with `-hf`), `--mmproj-offload`, `-mmdev/--mmproj-device`. vLLM needs a chat template (*"A chat template is **required** to use Chat Completions API"*) |

---

## Cross-cutting notes

### Where the four surfaces are structurally irreconcilable

Seven, in rough order of how much each costs a single internal representation.

1. **A tool result cannot carry an image on OpenAI Chat Completions, at all.** Anthropic
   nests image blocks inside `tool_result.content`; Gemini nests `FunctionResponseBlob`s
   inside `functionResponse.parts[]`; OpenAI's tool-message content-part union has one
   member and it is text. Any internal `tool_result` that admits an image block has no
   lossless OpenAI Chat Completions serialisation — the image must be dropped, described
   in text, or relocated into a following `user` message, and each of those is a
   different visible behaviour.
2. **The nesting depth of an image inside a tool result differs by one level and by
   kind.** Anthropic reuses its *ordinary* image block verbatim inside
   `tool_result.content`. Gemini uses a **different type** — `FunctionResponsePart` and
   `FunctionResponseBlob` are distinct schemas from `Part` and `Blob`, with a narrower
   MIME allowlist and no `fileData` member. An internal representation that models
   "image block" once and reuses it in both positions matches Anthropic's shape and not
   Gemini's.
3. **Reference-by-id has three incompatible spellings, and one surface has none.**
   Anthropic `{"type":"file","file_id":…}` (Files API); Gemini
   `{"fileData":{"fileUri":…}}` (Files API); OpenAI Chat Completions **has no image
   `file_id` path at all** — its `file_id` lives on the `file` part, and whether that
   accepts an image is **unknown**. Any "attachment handle" abstraction must degrade to
   inline bytes on at least one surface.
4. **`image_url` is an object on OpenAI and a bare string at Ollama.** OpenAI:
   `{"type":"image_url","image_url":{"url":…}}`. Ollama's only documented form:
   `{"type":"image_url","image_url":"data:image/png;base64,…"}`. Both call themselves
   OpenAI-compatible. A serialiser cannot emit one shape for both without a per-target
   flag.
5. **Fidelity control is a per-part enum, a per-part object, a global config field, and
   nothing — depending on surface.** OpenAI `image_url.detail: auto|low|high`; Anthropic
   `transformations.oversized_image: downsize|error` (a *rejection policy*, not a
   fidelity level); Gemini `generationConfig.mediaResolution` as a bare enum plus a
   per-part `{"level": …}` object carrying a fifth value the global form lacks. None of
   these four vocabularies maps onto another.
6. **Media type is required, optional, absent, or inferred — per surface and per source
   variant.** Anthropic `base64` requires `media_type` but `url` and `file` have no such
   field; Gemini `Blob.mimeType` is effectively required while `FileData.mimeType` is
   explicitly Optional; OpenAI carries no MIME field at all on the image part and infers
   it from the data URL or the fetched response. A representation that stores a MIME type
   unconditionally will be emitting a field two surfaces do not have; one that stores it
   optionally will have nothing to emit for Anthropic base64.
7. **Documents are a distinct block on one surface, a content part on another, and the
   same part as images on a third.** Anthropic `document` with five source variants and
   citation metadata; OpenAI a `file` part with no page limit documented; Gemini a plain
   `inlineData` with `mimeType: "application/pdf"`. Anthropic's `title` / `context` /
   `citations` have no counterpart anywhere else, and its `source.type: "content"` — a
   document made of content blocks — has no counterpart at all.

Two things that are, encouragingly, *not* irreconcilable: base64 image bytes in a user
message are expressible on all four surfaces; and every surface accepts multiple images
interleaved with text in a single user turn.

### The generic OpenAI-compatible row, expanded

Same standard as `provider-quirks.md`: what a client may assume without probing versus
what must be probed. Population is Ollama, vLLM, llama.cpp server, LM Studio.

**Safe to assume present** (documented by every runtime surveyed): `POST
{base}/v1/chat/completions` with `messages[]` carrying `role` + `content`; `content` as
a plain **string**; and the constraint that vision requires an explicitly
vision-capable model, discoverable through *some* runtime-specific capability field.

That is the whole list. **Nothing image-specific is documented by all four**, because
LM Studio documents no wire shape for image parts on `/v1/chat/completions` at all — the
string `image_url` does not appear anywhere in its docs corpus, and the chat-completions
page defers to *"See platform.openai.com/docs/api-reference/chat/create for parameter
semantics."* Its supported-payload list names `messages` without ever giving the content
schema. The only positive signal is prose: *"Send requests to Responses, Chat Completions
(**text and images**), Completions, and Embeddings endpoints."*

Drop LM Studio and the 3-of-4 safe set becomes: array-of-parts `content`,
`{"type":"text","text":…}`, `{"type":"image_url", …}`, and a base64 image payload.

**Must be probed for or treated as optional**, roughly by how likely each is to bite:

| # | Thing | State of the world |
|---|---|---|
| 1 | `image_url` **value type** | object `{"url": …}` at vLLM and llama.cpp; **bare string** is Ollama's only documented form. No runtime documents accepting both |
| 2 | `data:` base64 URI | verified at Ollama (its *only* accepted image source) and llama.cpp (which also accepts raw base64 with no prefix); inferred for vLLM's online endpoint; undocumented at LM Studio |
| 3 | `http(s)://` image URL | verified at vLLM and llama.cpp; **explicitly unsupported at Ollama** — its compatibility checklist marks `Image URL` unchecked while `Base64 encoded image` is checked; undocumented at LM Studio |
| 4 | local path | vLLM `file://` behind `--allowed-local-media-path`; llama.cpp `file://` behind `--media-path`. **Off by default in both** |
| 5 | `detail` | vLLM documents it verbatim as *"not supported"*; the other three never mention it. Do not send it |
| 6 | `{"type":"input_image"}` / `{"type":"file"}` | **none documented** by any of the four. Treat as absent |
| 7 | `input_audio` / `audio_url` / `video_url` / `image_embeds` | vLLM and llama.cpp only, per-model. **PDF nowhere** |
| 8 | MIME set | divergent and only partly stated; ship PNG + JPEG |
| 9 | size limits | no runtime advertises a byte cap; what exists is token budgets (llama.cpp) and item counts (vLLM) |
| 10 | multiple images per message | explicit only at vLLM |
| 11 | `role:"tool"` with non-text parts | **none documented** across all four |
| 12 | array-of-parts `content` at all | **none documented** at LM Studio |

**Native escape hatches**, for when the OpenAI-compatible path is not enough. Each is a
different shape again:

- **Ollama** `POST /api/chat` — `images` is an array of **raw base64 strings** (no
  `data:` prefix) and sits on the **message object as a sibling of the string
  `content`**, not inside it. `POST /api/generate` has a top-level `images` array.
  Verbatim: *"Provide an `images` array. SDKs accept file paths, URLs or raw bytes while
  the REST API expects base64-encoded image data."*
- **llama.cpp** `POST /completions` — `prompt` may be
  `{"prompt_string": "…<__media__>…", "multimodal_data": ["<b64>"]}`, with one MTMD media
  marker in the string per element, substituted in order. The marker is reported by
  `GET /props` as `media_marker`. The same mechanism works on the non-OAI `/embeddings`.
  *"A client must not specify this field unless the server has the multimodal
  capability."*
- **LM Studio** `POST /api/v1/chat` — a flat `input` array of typed items, not nested
  under a message: `{"type":"image","data_url":"data:image/png;base64,…"}`.
- **vLLM** — **none.** Online serving goes exclusively through `/v1/chat/completions`;
  the `multi_modal_data` path is offline-only Python.

### Primary-source conflicts

Three places where two pages from the same vendor disagree. Recorded rather than
resolved, because picking a winner would be a guess.

1. **OpenAI `detail: "original"`.** The vision guide says *"Supported values depend on
   the model: `low`, `high`, `original`, or `auto`"* and states the default is `auto`
   *"in both the Responses API and the Chat Completions API"*. But `original` is **not in
   the Chat Completions enum** in spec 2.3.0 or in the chat API reference. Whether
   `/v1/chat/completions` accepts it is **unknown**.
2. **Gemini's inline-bytes threshold.** 20 MB (image guide: *"Inline image data limits
   your total request size … to 20MB"*), 100 MB (files guide: *"Always use the Files API
   when the total request size … is larger than 100 MB. For PDF files, the limit is
   50 MB."*), and 7 MB (Vertex inference reference: inline `data` *"Size limit: 7 MB for
   images"*). No page reconciles these. 20 MB is the conservative bound for the Gemini
   API surface.
3. **Gemini's image MIME list.** The guide names five types; the `Blob.mimeType` schema
   description names eight, adding `image/jpg`, `image/gif`, `image/avif`. The schema is
   the lower-level source but the guide is what a user reads.

A fourth, smaller: `FunctionResponseBlob`'s field table lists only `mimeType` and
`data`, yet `FunctionResponse.response` describes referencing *"the
`inline_data.display_name` of a FunctionResponsePart"*, and both the worked example and
the Python SDK use `displayName`. The field is real; the reference table is incomplete.

### Folklore corrections

Four widely-repeated figures did not survive contact with primary docs. Recording them
explicitly so they don't get re-imported later.

1. **OpenAI does not document a 20 MB per-image limit.** The current documented figures
   are 512 MB total request payload and 1,500 images per request. No per-image byte cap
   appears in the vision guide, the file-inputs guide, the chat API reference, or spec
   2.3.0.
2. **OpenAI does not document a 100-page PDF limit.** The current figures are 50 MB per
   file and 50 MB combined across all files in a request. No page count is stated.
3. **Anthropic's "1568 px / ~1.15 megapixel" figure is no longer the general rule.**
   1568 px is now the *standard*-tier long-edge limit; Claude 4.7 and later use 2576 px.
   The megapixel formulation survives only on the computer-use page, scoped to pre-4.7
   models. The general limit is expressed as a visual-token budget instead.
4. **Anthropic's per-image byte limit is not "5 MB".** 5 MB is the Bedrock and Google
   Cloud figure; the Claude API's own limit is 10 MB base64.

Two corrections of smaller blast radius: Gemini's `Part` union has **nine** members, not
seven — `toolCall` and `toolResponse` are newer server-side-tool members absent from most
write-ups; and Gemini's `role` for a tool result is **`"user"`**, not `"function"`. The
normative `Content.role` field says *"Must be either 'user' or 'model'"*, and the
`"function"` mention that survives in the `FunctionDeclaration` prose is a documentation
remnant contradicted by it. That resolves the contradiction `provider-quirks.md` left
open under "required role for `functionResponse`".

### Hazards worth flagging separately

- **Anthropic's >20-image threshold counts blocks you did not send this turn.** Resent
  images from earlier conversation turns and images nested inside `tool_result.content`
  all count. On Bedrock and Google Cloud, `document` blocks count too. Whether they count
  on the direct Claude API is **unstated** — that sentence is scoped to those two
  platforms.
- **Anthropic's token-counting endpoint does not validate size.** *"The Token counting
  endpoint estimates an image's token cost from its dimensions without fully processing
  it, so a successful count doesn't mean the image is within the Messages API's request
  limits."*
- **OpenAI's patch ceiling rejects rather than resizes.** *"Images that exceed the
  30,000-patch limit after processing are rejected, not automatically resized to meet
  it."* That is the opposite of the behaviour everywhere else on that surface.
- **Gemini Files API storage expires.** Uploaded files are deleted after **48 hours**. A
  session that stores a `fileUri` and replays the conversation two days later will send a
  dead reference.
- **Neither Anthropic nor Gemini permits images in the system prompt.** Anthropic's
  `system` accepts `string` or an array of `TextBlockParam` only. Gemini's
  `systemInstruction` is typed as `Content` — so an image part is structurally
  expressible — but the field doc says *"Currently, text only."*, and Vertex adds *"Only
  text should be used in parts"*. OpenAI's system and developer content-part unions are
  text-only by schema.
- **`prompt_cache_breakpoint` sits on OpenAI content parts**, including the image, audio
  and file parts — a cache control at *part* granularity, unlike Anthropic's block-level
  `cache_control` with its 4-breakpoint request cap.

---

## Sources

All accessed 2026-09-08.

**Anthropic** — `platform.claude.com` (note `docs.anthropic.com` / `docs.claude.com`
redirect there): [`/build-with-claude/vision`](https://platform.claude.com/docs/en/build-with-claude/vision),
[`/build-with-claude/vision-coordinates`](https://platform.claude.com/docs/en/build-with-claude/vision-coordinates),
[`/build-with-claude/pdf-support`](https://platform.claude.com/docs/en/build-with-claude/pdf-support),
[`/build-with-claude/citations`](https://platform.claude.com/docs/en/build-with-claude/citations),
[`/build-with-claude/files`](https://platform.claude.com/docs/en/build-with-claude/files),
[`/build-with-claude/search-results`](https://platform.claude.com/docs/en/build-with-claude/search-results),
[`/build-with-claude/prompt-caching`](https://platform.claude.com/docs/en/build-with-claude/prompt-caching),
[`/agents-and-tools/tool-use/handle-tool-calls`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls),
[`/agents-and-tools/tool-use/define-tools`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools),
[`/agents-and-tools/tool-use/computer-use-tool`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool),
[`/api/messages/create`](https://platform.claude.com/docs/en/api/messages/create),
[`/api/errors`](https://platform.claude.com/docs/en/api/errors),
[`/models/overview`](https://platform.claude.com/docs/en/models/overview).
Sourcing caveat: Anthropic publishes **no downloadable API spec file**; the rendered
reference pages are the only schema surface, and a few union aliases — notably
`ContentBlockSourceContent` — are named without being expanded.

**OpenAI** — the normative source is the published spec
[`openai/openai-openapi` `openapi.yaml`](https://github.com/openai/openai-openapi/blob/master/openapi.yaml)
(`info.version: 2.3.0`, `openapi: 3.1.0`), fetched raw from `raw.githubusercontent.com`.
Schemas read: `ChatCompletionRequestUserMessage`,
`ChatCompletionRequestUserMessageContentPart`,
`ChatCompletionRequestMessageContentPartImage`,
`ChatCompletionRequestMessageContentPartFile`,
`ChatCompletionRequestMessageContentPartAudio`,
`ChatCompletionRequestMessageContentPartText`,
`ChatCompletionRequestMessageContentPartRefusal`, `ChatCompletionRequestToolMessage`,
`ChatCompletionRequestToolMessageContentPart`,
`ChatCompletionRequestSystemMessageContentPart`,
`ChatCompletionRequestAssistantMessageContentPart`,
`ChatCompletionRequestDeveloperMessage`, `CreateFileRequest`.
Prose: `platform.openai.com/docs/*` 403s automated fetch and redirects to
`developers.openai.com`; appending `.md` to a `developers.openai.com` doc URL returns
clean markdown. Guides used:
[images-vision](https://developers.openai.com/api/docs/guides/images-vision),
[file-inputs](https://developers.openai.com/api/docs/guides/file-inputs),
[audio](https://developers.openai.com/api/docs/guides/audio),
[text](https://developers.openai.com/api/docs/guides/text),
[chat resource reference](https://developers.openai.com/api/reference/resources/chat),
[models](https://developers.openai.com/api/docs/models).
Note `developers.openai.com/api/docs/guides/pdf-files` is a 404; PDF content lives in
`file-inputs`.

**Google Gemini** — the normative source is the **API discovery document**,
`GET https://generativelanguage.googleapis.com/$discovery/rest?version=v1beta`, which is
where `Content`, `Part`, `Blob`, `FileData`, `FunctionResponse`, `FunctionResponsePart`,
`FunctionResponseBlob`, `GenerationConfig` and `V1mainMediaResolution` were read.
Reference pages: [ai.google.dev/api/generate-content](https://ai.google.dev/api/generate-content),
[ai.google.dev/api/files](https://ai.google.dev/api/files).
Guides — note Google now runs **two trees**, and the `docs/generate-content/*` tree is
the one that still documents genuine `generateContent` REST:
[generate-content/image-understanding](https://ai.google.dev/gemini-api/docs/generate-content/image-understanding),
[generate-content/function-calling](https://ai.google.dev/gemini-api/docs/generate-content/function-calling),
[generate-content/document-processing](https://ai.google.dev/gemini-api/docs/generate-content/document-processing),
[generate-content/files](https://ai.google.dev/gemini-api/docs/generate-content/files),
[generate-content/media-resolution](https://ai.google.dev/gemini-api/docs/generate-content/media-resolution).
Interactions-rewritten pages, used only for MIME lists and limits:
[image-understanding](https://ai.google.dev/gemini-api/docs/image-understanding),
[document-processing](https://ai.google.dev/gemini-api/docs/document-processing),
[files](https://ai.google.dev/gemini-api/docs/files),
[audio](https://ai.google.dev/gemini-api/docs/audio),
[video-understanding](https://ai.google.dev/gemini-api/docs/video-understanding).
Vertex: [model-reference/inference](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference).
Sourcing caveat, extending the one in `provider-quirks.md`: `ai.google.dev/api/caching`
**no longer defines** `Part` / `Blob` / `FileData` — those moved to
`ai.google.dev/api/generate-content`, and `ai.google.dev/api/rest/v1beta/Content` 302s
there. The `gemini-api/docs/*` guides have been rewritten around the newer Interactions
API (`POST /v1beta/interactions`, `input[]`, `{"type":"image","uri":…}`) and their
examples are **not** `generateContent`.

**Local runtimes** — Ollama:
[docs/api/openai-compatibility.mdx](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx),
[docs/capabilities/vision.mdx](https://github.com/ollama/ollama/blob/main/docs/capabilities/vision.mdx),
[docs/api.md](https://github.com/ollama/ollama/blob/main/docs/api.md),
[docs/openapi.yaml](https://github.com/ollama/ollama/blob/main/docs/openapi.yaml)
(native API only — the `/v1` compat surface is not in it).
vLLM: [features/multimodal_inputs](https://docs.vllm.ai/en/latest/features/multimodal_inputs/),
[serving/online_serving](https://docs.vllm.ai/en/latest/serving/online_serving/)
(the old `serving/openai_compatible_server/` URL now 301s here).
llama.cpp: [tools/server/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md),
[docs/multimodal.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md).
LM Studio: [openai-compat/chat-completions](https://lmstudio.ai/docs/developer/openai-compat/chat-completions),
[openai-compat/responses](https://lmstudio.ai/docs/developer/openai-compat/responses),
[llms.txt](https://lmstudio.ai/llms.txt) and `llms-full.txt` (the full docs corpus,
searched for `image_url` — zero occurrences).

---

## Consolidated unknowns

Cells left deliberately blank, with the reason. Each is a candidate for a follow-up
probe against a live endpoint — which this ticket, like #10, explicitly did not do.

| Provider | Axis | Why unknown |
|---|---|---|
| Anthropic | per-image byte limit for **URL-sourced** images | every published figure is qualified "(base64-encoded)"; no URL-fetch cap is stated |
| Anthropic | behaviour on an unsupported image MIME type | not on the vision page; the errors page's validation-error list does not cover it |
| Anthropic | numeric value of the stricter per-image dimension limit above 20 images | the doc says the 400 message reports it at runtime; 2000 px is offered only as safe guidance |
| Anthropic | separate cap on images per `tool_result` | none documented; they count toward request-wide totals only |
| Anthropic | whether `document` blocks count toward the 20-image threshold on the **direct** API | that sentence is scoped to Bedrock and Google Cloud only |
| Anthropic | exact member types of `ContentBlockSourceContent` (inside `document.source.type: "content"`) | the reference names the alias without expanding it; `text` + `image` is inferred, image nesting confirmed only by vision-coordinates prose |
| Anthropic | a downloadable API spec artefact | none published |
| OpenAI | whether `detail: "original"` is accepted on `/v1/chat/completions` | present in the vision guide's prose, absent from the Chat Completions enum in spec 2.3.0 and the chat reference |
| OpenAI | runtime behaviour of a non-text part in a `role:"tool"` message | schema-invalid, but no error text, no prose, no example. 400 vs silent drop is not documented |
| OpenAI | whether a `file` part carrying an image `file_id` works on Chat Completions | the image-by-`file_id` path is documented only for Responses (`input_image.file_id`, `purpose: "vision"`) |
| OpenAI | per-image byte limit | none documented — only the 512 MB request payload |
| OpenAI | PDF page-count limit | none documented |
| OpenAI | whether the documented `input_file` type list applies verbatim to the Chat Completions `file` part | the file-types table is written in Responses wording |
| OpenAI | data URI in `image_url.url` on Chat Completions specifically | the schema says "or the base64 encoded image data"; every worked base64 example on the page is Responses-shaped |
| OpenAI | audio size or duration limits | none documented |
| Gemini | the actual inline-bytes threshold | 20 MB / 100 MB / 7 MB across three primary pages, unreconciled |
| Gemini | the authoritative image MIME list | guide lists five, schema lists eight |
| Gemini | whether a sibling `inlineData` part beside `functionResponse` is legal | none documented — neither permitted nor forbidden; structurally expressible |
| Gemini | image resize / max-dimension behaviour for standalone images | no rule stated; Vertex's *"There is no limit on image resolution"* is not the same claim |
| Gemini | per-model image limits | no table exists; Vertex defers to a models page |
| Gemini | `FunctionResponseBlob.displayName` | used in the worked example and the SDK, missing from the reference field table |
| Gemini | text prompt before or after the image | the legacy tree says after, the Interactions-rewritten tree says before |
| Generic | whether Ollama accepts the OpenAI **object** form of `image_url` | only the bare-string form appears in its docs; the object form is never shown |
| Generic | whether vLLM's *online* endpoint accepts a `data:` URI | the data-URL example is in the offline `llm.chat()` section; online is documented as "supported according to OpenAI Vision API" |
| Generic | whether vLLM 400s or silently ignores `detail` | documented as "not supported"; the failure mode is not stated |
| Generic | LM Studio's image wire shape on `/v1/chat/completions` | `image_url` appears **nowhere** in its docs corpus; images are asserted in prose, the shape never given |
| Generic | whether LM Studio accepts array-of-parts `content` at all | never documented; the page defers to the OpenAI reference |
| Generic | `role:"tool"` with non-text parts, at any of the four runtimes | none documented across every relevant page |
| Generic | any byte-size limit, at any of the four runtimes | none advertised |
| All | behaviour when an image exceeds a limit mid-conversation | only Anthropic and OpenAI state a rejection policy at all, and Anthropic's is split between downscale (default) and reject (`transformations`, and unconditionally for computer/browser-use tool results) |

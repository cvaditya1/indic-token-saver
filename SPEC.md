# indic-token-saver — SPEC

Version: **v0.2.0**  
Status: v0.2 keeps the week-2 IndicTrans2 path and makes the translate policy explicit. Default: translate only when the detected language is `hi` or `te`, unless `X-Bypass-Translation: 1`. `GET /stats` summarizes the existing JSONL log. This document is the spec. There is no `specs/` tree.

Author: **Aditya Venkat Chalamchala**  
This is a personal open-source project. It is unaffiliated with any employer.

License: MIT.

## Problem

Indic text, especially Telugu and Hindi, often costs more than the same meaning in English because chat models emit a longer reply. Output tokens dominate published list prices. Week 2 puts a local IndicTrans2 model on both sides of the paid call for Hindi and Telugu: the paid model sees English, and the caller gets the reply in the detected Indic language.

**No savings claim yet.** The only live token counts in this spec are the passthrough baseline below. Week 2 does not compare a translated call with that baseline.

The free tier’s actual bill is ₹0. Every rupee figure in the log is a **published-price estimate, not a charge**. The estimate uses the upstream `usage` of the call that was actually made (the English call when translation ran).

## Author’s hand check (2026-10-10)

The author checked published prices and left them as written. `USD_INR_RATE` stays **96.64**. The token prices in `src/indic_token_saver/cost.py` stay as in the cost table below.

Same model, `gemini-3.5-flash-lite`, one weather question, passthrough (no translation). These two rows are the author’s measured baseline:

| Language | User text | prompt_tokens | completion_tokens | total | Sample |
| --- | --- | --- | --- | --- | --- |
| English | What is the weather in Hyderabad today? | 9 | 27 | 36 | complete |
| Hindi | आज हैदराबाद में मौसम कैसा है? | 8 | 120 | 128 | complete |
| Telugu | — | — | — | — | **incomplete** |

The Telugu curl was truncated and the shell line was corrupted (`curcurl`, a `<200>` inside the prompt). This spec does not invent a Telugu token count.

On this model the input token counts were similar (9 English, 8 Hindi). The Hindi reply was much larger (120 completion tokens versus 27). That is why week 2 translates the reply side as well as the request. This is a baseline, not a savings result.

## When translate-first loses

On `gemini-3.5-flash-lite`, this short prompt did **not** cost more input tokens in Hindi than in English (8 versus 9). The reply side is where the Indic text grew (120 completion tokens versus 27).

Translation can lose in these cases, even though the default policy still translates `hi` and `te`:

- The English reply is longer than a direct Indic reply, so the paid completion (priced on the English call) costs more than answering in Indic.
- The reply is already short, so there is little output-token difference to recover, while local translation still adds latency.
- Masking and placeholders damage the answer. Placeholders that the translator rewrites are not restored, and person names are not reliably protected.

v0.2 does not claim a savings number. The passthrough rows above are the only paired language baseline. A later single translated call, if recorded in `RESULTS.md`, is one live proxy request. It is not a controlled before/after, and it is not a savings result. The Telugu baseline is still incomplete. Do not invent a Telugu token count.

## Audience and positioning

People who call Gemini or Groq with Telugu, Hindi, or English and want a private log of language, latency, and estimated list-price cost, with local translation for Hindi and Telugu.

- Personal project, not a product of any workplace.
- Indic-specific. Savings, if they show up later, are aimed at **output** tokens via a local translator.
- One-line difference from prior art: Indic-specific, local translator, savings aimed at output. v0.2 does not claim savings.

### Prior art

- **lingua-proxy** — generic proxy, LLM translation, mainly input savings.
- **Tokenizer Tax** — public writing on how non-English text inflates token counts.
- **IndicTrans2** (AI4Bharat, MIT) — local Indic↔English translation, used in week 2 for `hi` and `te`.
- **EMNLP 2024 translate-first findings** — research that translating into English before a model call can change quality and cost. Not reproduced here.

## Non-goals

**Forever, for this repo:** software testing products, load-testing products, eval/assurance/governance/compliance products, PII redaction products, OCR products.

**Not in this pass:** streaming, a translator microservice, a Hugging Face Space, GitHub Pages, a recorded GIF, OpenTelemetry (the JSONL log and `GET /stats` are the observability), an eval harness, LLM-as-judge, guardrails. The public README is the launch artifact. Feedback from other builders is not collected.

## Policy (v0.2)

Small and explicit. Not an eval harness. The decision does not look at reply length, quality, or a prompt set.

```
translate = detected language is hi or te, and X-Bypass-Translation is not 1
```

| Detected language | `X-Bypass-Translation: 1` | Action |
| --- | --- | --- |
| `hi` or `te` | absent | mask, IndicTrans2 both ways, restore spans |
| `hi` or `te` | present | passthrough |
| `en`, `mixed`, `unknown` | either | passthrough |

The header value must be the string `1`. Any other value does not bypass.

## v0.2 success

- `GET /health` returns version `0.2.0`.
- The policy table above is what the proxy does.
- `GET /stats` reads the JSONL log and returns count, p50 and p95 `latency_ms`, and totals of `prompt_tokens`, `completion_tokens`, and `estimated_inr`, split by `was_translated` and `detected_lang`. An empty or missing log returns zeros. No new database.
- `RESULTS.md` records the passthrough baseline, when translate-first can lose, and either one live Hindi proxy call or the failure. No invented numbers. The 40-prompt file is not run as a batch.
- Offline tests cover `/stats` percentiles on a tiny fixture and the policy default plus bypass. They do not load torch and do not call Gemini.

## Week-2 behavior (still in v0.2)

- `GET /health` returned version `0.1.0` during week 2. v0.2 reports `0.2.0`.
- English, `unknown`, and `mixed` requests pass through with no translation.
- `hi` and `te` requests are masked, translated to English, sent upstream, and the assistant reply is translated back, then masked spans are restored.
- `X-Bypass-Translation: 1` forces passthrough for `hi` and `te`.
- A translation cache hit does not call the translator again for the same masked text.
- Missing IndicTrans2 weights return HTTP 503 and do not crash import.
- Offline tests inject a fake translator. No live Gemini, Groq, or weight download in tests.
- The JSONL log gains `was_translated` and `translation_cache` and still stores no prompt or completion body.
- The slim image installs `requirements.txt` only (no torch) and does not copy `.env`.

## Human ownership

The author reviews diffs. The price constants and the two complete baseline rows above are the author’s check. The Telugu baseline row is still open. Do not publish a savings number from this tree.

## API

OpenAI-compatible proxy.

### `GET /health`

```json
{"status": "ok", "version": "0.2.0"}
```

### `GET /stats`

Reads `LOG_PATH` (the same append-only JSONL). No new database. A missing file, an empty file, or a file with no usable rows returns zeros and empty splits:

```json
{
  "count": 0,
  "p50_latency_ms": 0,
  "p95_latency_ms": 0,
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "estimated_inr": "0.000000",
  "by_was_translated": {},
  "by_detected_lang": {}
}
```

When rows exist, the top-level object has the same fields for every usable row. `by_was_translated` has keys `"true"` and/or `"false"`. `by_detected_lang` has one key per observed `detected_lang`. Each split value has the same six fields, computed only on that subset.

Percentiles use the nearest-rank method on `latency_ms` sorted ascending. For `n` values and percent `p` (50 or 95), the index is `ceil(p/100 * n) - 1`, clamped to the array. One row makes p50 and p95 that row’s latency. Tokens that are JSON `null` add zero. `estimated_inr` values are summed as decimals and the total is quantized to 6 decimal places. A line that is not a JSON object, or a row whose `latency_ms` is not an integer, is skipped. The response does not include prompt or completion text.

### `POST /v1/chat/completions`

Implemented request fields:

| Field | Rule |
| --- | --- |
| `messages` | Required array. Each item has `role` and `content`. String `content` only. Non-string content returns HTTP 400. |
| `model` | Optional string. See provider selection. If omitted, the default model for the selected provider is sent upstream. |
| `stream` | Omitted or `false` only. `stream: true` returns HTTP 400 and does not call upstream. |

Other JSON keys (`temperature`, `max_tokens`, and so on) are forwarded as-is.

Language is detected on the original user text (see below). Translation runs only when that label is `hi` or `te`, unless the bypass header is set.

Success: OpenAI-shaped JSON.

- Passthrough (`en`, `unknown`, `mixed`, or bypass): upstream status and body unchanged.
- Translated: same upstream object, except each `choices[].message.content` string is the Indic translation of the English reply with masked spans restored. `usage` stays the upstream usage of the English call. Upstream HTTP status is kept.

Response headers (week 1 headers stay):

- `X-Detected-Language`: `en`, `hi`, `te`, `mixed`, or `unknown`
- `X-Estimated-Cost-Inr`: decimal string of the list-price estimate, or empty if the model has no price constant
- `X-Request-Id`: id also stored in the log
- `X-Was-Translated`: `1` or `0`
- `X-Translation-Cache`: `hit`, `miss`, or `off`

`X-Translation-Cache` is `off` when no translation was attempted. It is `hit` when every translation lookup in that request was served from the cache. It is `miss` when any lookup called the translator.

Upstream non-JSON body: HTTP 502, small error JSON, still no prompt text in the log. Translation headers are still set.

Missing API key for the chosen provider: HTTP 401, no upstream call.

IndicTrans2 weights or the translate extra missing when a `hi`/`te` request needs translation: HTTP 503, short JSON error that names both model ids and `requirements-translate.txt`. No upstream call. Importing the app does not load torch and does not crash if torch is absent.

### Bypass

Request header `X-Bypass-Translation: 1` forces passthrough even when detection is `hi` or `te`. No mask, no translation, cache status `off`.

### Provider selection

| Condition | Provider | Model sent upstream |
| --- | --- | --- |
| `model` starts with `groq/` | Groq | remainder after the prefix |
| `model` starts with `gemini/` | Gemini | remainder after the prefix |
| `model` starts with `gemini-` | Gemini | unchanged |
| `model` starts with `openai/`, `qwen/`, `meta-llama/`, or `llama-` | Groq | unchanged |
| `model` omitted or any other id | `DEFAULT_PROVIDER` (default `gemini`) | the given id, or that provider’s default model if omitted |

Base URLs:

- Gemini OpenAI-compatible: `https://generativelanguage.googleapis.com/v1beta/openai/` (`POST .../chat/completions`)
- Groq: `https://api.groq.com/openai/v1` (`POST .../chat/completions`)

Auth: `Authorization: Bearer <key>`.

Default model ids (confirm they are still on the free tier before relying on them):

- Gemini: `gemini-3.5-flash-lite`
- Groq: `openai/gpt-oss-20b`

The clients are the week-1 Gemini and Groq clients. Translation does not add a third paid provider.

## Week-2 translation path

For user text detected as `hi` or `te`, and when bypass is not set:

1. Mask protected spans in each **user** message (system and earlier assistant messages stay as written).
2. Translate each masked user message Indic → English with local IndicTrans2.
3. Call the upstream model with that English text.
4. Translate each assistant reply string English → Indic.
5. Restore masked spans in the translated reply.
6. Return OpenAI-shaped JSON.

Both IndicTrans2 checkpoints are loaded on the first `hi`/`te` request that is not bypassed, before the upstream call. A later request reuses them.

Only `role == "user"` contents are translated on the way in. The new completion’s `choices[].message.content` strings are translated on the way back. The reply target language is the detected label (`hi` → `hin_Deva`, `te` → `tel_Telu`).

English, `unknown`, and `mixed`: passthrough, no translation.

### Masking

Applied to each user message **before** translation, in this order:

1. Fenced code (` ``` ... ``` `) and inline code (single backticks on one line).
2. URLs (`http://`, `https://`, and `www.`).
3. Currency amounts with `₹`, `Rs`, or `INR`, optional space, then a number (`₹80`, `Rs. 1,200`).
4. Dates, recognized conservatively: ISO `YYYY-MM-DD` with an optional `T` time, and numeric day-month-year `D/M/Y` or `D-M-Y`. This is recognition, not calendar validation.
5. Standalone ASCII numbers, including grouped digits and a decimal part (`80`, `1,234`, `3.14`).

Each span becomes a stable placeholder `<<P0>>`, `<<P1>>`, … numbered in that order across the message. IndicTrans2 is given the masked string. After the reverse translation, each exact placeholder is replaced with the original span.

Placeholders are restored by exact match. If the translator rewrites a placeholder, that span is not restored.

**Person names are not reliably protected in v0.2.** There is no named-entity model. A name written in Latin or in the Indic script can be translated or altered. That is one way masking can damage an answer (see “When translate-first loses”).

### IndicTrans2

Default checkpoints, chosen so an M4 with 24GB can run them:

- Indic → English: `ai4bharat/indictrans2-indic-en-dist-200M`
- English → Indic: `ai4bharat/indictrans2-en-indic-dist-200M`

Language tags:

| Label | Tag |
| --- | --- |
| English | `eng_Latn` |
| Hindi | `hin_Deva` |
| Telugu | `tel_Telu` |

Runtime: `IndicTransToolkit` `IndicProcessor(inference=True)`, then the Hugging Face seq2seq model. Device is CUDA when present, otherwise Apple MPS when present, otherwise CPU. No FlashAttention requirement. Generation follows the model-card shape: beam size 5, `max_length` 256. A reply longer than that can be cut off.

Weights load lazily, `local_files_only`, on first use. This project does not download weights at startup. If the translate extra is not installed, or the weights are not on disk, the request returns HTTP 503. The message names both model ids and `requirements-translate.txt`.

Heavy dependencies live in `requirements-translate-cpu.txt` / `requirements-translate-cuda.txt` (torch variant + shared `requirements-translate-common.txt`). `requirements-translate.txt` includes the CPU file for local venv installs. `requirements.txt` stays free of torch so the slim image still builds.

### Translation cache

SQLite file at `CACHE_PATH` (default `data/translation_cache.sqlite`).

Primary key: direction (`indic-en` or `en-indic`), source lang tag, target lang tag, IndicTrans2 model id, and the masked source text.

The stored value is the model output text only, before span restore. A hit returns that text and does not call the translator. The JSONL request log is separate and still has no bodies. The cache file itself holds masked source text and translated text so a repeat can skip IndicTrans2.

## Language detection

Unchanged from week 1. Input is the concatenation of `content` from messages with `role == "user"`, joined by newlines. System and assistant text are ignored. Empty user text is `unknown`.

Before counting:

1. Remove fenced code blocks (` ``` ... ``` `).
2. Remove inline code spans (single backticks on one line).
3. Remove URLs (`http://`, `https://`, and `www.`).

Then count code points only:

- **Telugu:** U+0C00–U+0C7F except Telugu digits U+0C66–U+0C6F
- **Devanagari:** U+0900–U+097F except Devanagari digits U+0966–U+096F
- **Latin:** ASCII letters A–Z and a–z

Ignored and unable to flip the label by themselves: digits, punctuation, whitespace, currency signs such as `₹`, emoji, and anything removed as code or URL. A string that is only a URL, only a number, or only `₹` is `unknown`.

Let `total` be the sum of the three counts.

- `total == 0` → `unknown`
- Otherwise let `share` be each count divided by `total`. If the largest share is **≥ 0.80** → `te` (Telugu block), `hi` (Devanagari), or `en` (Latin).
- Otherwise → `mixed`.

Devanagari is labeled `hi`. Marathi, Nepali, and Sanskrit use the same block and will also be labeled `hi`. That limitation is accepted. Unfenced code is not stripped; Latin identifiers inside it count as English letters.

## Cost model

```
estimated_usd = (prompt_tokens * input_usd_per_million
               + completion_tokens * output_usd_per_million) / 1_000_000
estimated_inr = estimated_usd * usd_inr_rate
```

Usage fields read: `usage.prompt_tokens` and `usage.completion_tokens` from the upstream response. When translation ran, those counts are for the **English** call, not for the Indic text the caller sent or received. No other usage fields. Cached tokens are not discounted. Reasoning tokens are not added on top; if the provider folds them into `completion_tokens`, they are priced as output, which matches Gemini’s “output includes thinking tokens” list price. Missing `usage` or a model id with no row below yields `estimated_inr: null` (header empty). The math uses `decimal.Decimal` and the log stores the INR value quantized to 6 decimal places.

**This number is a published paid-tier list-price estimate. It is not a charge. On the free tier the actual bill is ₹0.**

The author confirmed the published prices below on 2026-10-10. The constants are unchanged.

| Constant | Value | Source note |
| --- | --- | --- |
| `USD_INR_RATE` default | **96.64** | Author-confirmed assumption for 2026-10-10. Same-day public quotes differed (about 96.59 to 96.78). Override with env `USD_INR_RATE`. |
| `gemini-3.5-flash-lite` | **$0.30** input / **$2.50** output per 1M tokens | [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), standard paid tier, text. Page lists free tier as free of charge. |
| `gemini-2.5-flash` | **$0.30** / **$2.50** | Same page, text/image/video input. |
| `gemini-2.5-flash-lite` | **$0.10** / **$0.40** | Same page, text/image/video input. |
| `openai/gpt-oss-20b` | **$0.075** / **$0.30** | [Groq models](https://console.groq.com/docs/models). Free-plan rate-limit row was reported for this id; confirm before use. |
| `openai/gpt-oss-120b` | **$0.15** / **$0.60** | Same Groq models page. |
| `qwen/qwen3.8-27b` | **$0.80** / **$4.00** | Same Groq models page. |

Audio, cache, batch, grounding, and storage fees are out of this estimate. Unknown model ids are not given an invented price.

## Log format

Append-only JSONL at `LOG_PATH` (default `logs/requests.jsonl`). One object per finished upstream attempt (success or upstream error). No prompt or completion body. A 503 before the upstream call writes no row.

Fields:

| Field | Meaning |
| --- | --- |
| `ts` | UTC time, ISO-8601, suffix `Z` |
| `provider` | `gemini` or `groq` |
| `model` | model id sent upstream |
| `detected_lang` | `en` \| `hi` \| `te` \| `mixed` \| `unknown` |
| `prompt_tokens` | integer or null, from upstream usage |
| `completion_tokens` | integer or null, from upstream usage |
| `latency_ms` | integer milliseconds, including translation when it ran |
| `estimated_inr` | decimal string or null |
| `request_id` | UUID |
| `cost_basis` | always `published_list_price_estimate` |
| `was_translated` | bool, true when the IndicTrans2 path ran |
| `translation_cache` | `hit` \| `miss` \| `off` |

`LOG_PROMPT_HASH=1` adds `prompt_sha256` (SHA-256 hex of the same original user text used for detection). Default is off. The raw prompt is never written.

## Config

| Env | Default |
| --- | --- |
| `GEMINI_API_KEY` | empty |
| `GROQ_API_KEY` | empty |
| `USD_INR_RATE` | `96.64` |
| `LOG_PATH` | `logs/requests.jsonl` |
| `CACHE_PATH` | `data/translation_cache.sqlite` |
| `DEFAULT_PROVIDER` | `gemini` |
| `DEFAULT_GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `DEFAULT_GROQ_MODEL` | `openai/gpt-oss-20b` |
| `LOG_PROMPT_HASH` | `0` |

See `.env.example`. Real keys stay in untracked `.env`.

## Prompt file

`data/prompts_v0.jsonl`: objects with `id`, `lang` (`en`|`hi`|`te`), `text`, `source`.

About 40 rows, at least 12 per language, roughly even. **All rows are homemade** short original sentences (weather, cooking, directions, code-help, prices in ₹). No FLORES-200 sample: a public corpus was not copied into this repo. No book text, lyrics, employer text, or client text.

## Stack

Python 3.11+. FastAPI, uvicorn, httpx, pydantic. Tests: pytest, offline only, with `httpx.MockTransport` and an injected fake translator. No live Gemini or Groq calls, even if keys are present. Tests do not download IndicTrans2 weights.

Package: `src/indic_token_saver/`.

Translate extra (not installed in the slim image): see `requirements-translate.txt`.

## v0.2 done vs deferred

**Done:** week-1 passthrough, script detection, JSONL cost/latency log, priced constants, homemade prompt file, mask / IndicTrans2 / reply translation / SQLite cache, the explicit hi/te policy with bypass, and `GET /stats`. `RESULTS.md` holds the measured baseline and the loss cases. No savings claim.

**Deferred:** streaming, a separate translator service, Hugging Face Space, GitHub Pages, a GIF. No OpenTelemetry stack.

### Container image

Dockerfile targets:

| Target | Contents |
| --- | --- |
| `slim` | Gateway only; `requirements.txt`; no torch |
| `translate-cpu` | slim + CPU PyTorch wheels + IndicTrans2 deps (`requirements-translate-cpu.txt`) |
| `translate-cuda` | slim + CUDA PyTorch wheels (`requirements-translate-cuda.txt`, cu124 index) |

On a personal machine, the recommended path is `docker compose up`, which builds **translate-cpu** (default). It mounts the host Hugging Face cache read-only at `/home/appuser/.cache/huggingface` so weights already on disk are reused; the first Hindi or Telugu request that is not bypassed loads models from that mount and can be slow. Compose also mounts `./logs` and `./data` for the JSONL log and SQLite translation cache. `.env` is not baked into the image; `env_file: .env` supplies API keys at run time.

NVIDIA GPU hosts: `docker compose --profile gpu up --build app-gpu` (target `translate-cuda`, `gpus: all` / compose device reservation). Mac hosts use CPU in Docker; native venv may set `TRANSLATE_DEVICE=mps`. AMD GPU users: host venv or CPU container (no ROCm image in v0.2).

Gateway-only (no torch, Hindi and Telugu return HTTP 503): `docker compose --profile slim up --build app-slim`, or `docker build --target slim`.

`docker build .` (no `--target`) builds **translate-cpu**. Neither image downloads model weights at build time.

Runtime device for IndicTrans2: optional `TRANSLATE_DEVICE` (`cpu` \| `cuda` \| `mps`); if unset, use CUDA when available, else CPU. Logged once at first model load (INFO).

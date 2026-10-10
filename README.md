# indic-token-saver

OpenAI-compatible proxy for people who call Gemini or Groq with Hindi, Telugu, or English. Indic chat replies often use more tokens than the same meaning in English, and output tokens dominate published list prices. This proxy translates Hindi and Telugu locally with IndicTrans2 so the paid model sees English, translates the reply back, and logs language, latency, and a list-price estimate in rupees.

Version **0.2.0**. Personal project by Aditya Venkat Chalamchala. Unaffiliated with any employer. Built with AI coding agents; design, review, and measurements by the author.

Design: [SPEC.md](SPEC.md). Measurements: [RESULTS.md](RESULTS.md). License: MIT.

## What it does

1. Detects the user text as English, Hindi, Telugu, mixed, or unknown from script counts.
2. For Hindi and Telugu, masks code, URLs, currency amounts, conservative dates, and standalone numbers, translates the rest to English with local IndicTrans2, calls Gemini or Groq, translates the assistant reply back, and restores the masked spans.
3. Logs one JSONL row per finished upstream call: provider, model, detected language, token counts, latency, estimated INR, and whether translation ran. The log does not store the prompt or the completion.
4. `GET /stats` summarizes that log (count, p50 and p95 latency, token totals, estimated INR), split by whether translation ran and by detected language.

The rupee figure is a published paid-tier **list-price estimate** of the call that was actually made (the English call when translation ran). It is not a charge. On the free tier the actual bill is ₹0.

This repo does not claim token savings. The only measured language baseline is one short weather question on `gemini-3.5-flash-lite`, passthrough: English 9 prompt / 27 completion, Hindi 8 / 120. On that prompt, Hindi did not cost more input tokens than English. The reply side is where the Indic text grew. The Telugu sample is incomplete and is not given a token count. See [RESULTS.md](RESULTS.md).

## API

`GET /health`

```json
{"status": "ok", "version": "0.2.0"}
```

`GET /stats`

Reads `logs/requests.jsonl` (override with `LOG_PATH`). An empty log returns zeros. Percentiles are nearest-rank on `latency_ms`. Details are in [SPEC.md](SPEC.md).

`POST /v1/chat/completions`

OpenAI-shaped chat completions. `messages` is required and `content` must be a string. `stream: true` returns HTTP 400. Other JSON fields are forwarded.

| `model` | Where it goes |
| --- | --- |
| starts with `gemini/` or `gemini-` | Gemini |
| starts with `groq/` | Groq, prefix removed |
| starts with `openai/`, `qwen/`, `meta-llama/`, or `llama-` | Groq |
| omitted or anything else | `DEFAULT_PROVIDER` (default `gemini`) |

Default model ids: Gemini `gemini-3.5-flash-lite`, Groq `openai/gpt-oss-20b`. Confirm they are still on the free tier before relying on them.

Response headers:

| Header | Meaning |
| --- | --- |
| `X-Detected-Language` | `en`, `hi`, `te`, `mixed`, or `unknown` |
| `X-Estimated-Cost-Inr` | list-price estimate, or empty if the model has no price row |
| `X-Request-Id` | id also stored in the log |
| `X-Was-Translated` | `1` or `0` |
| `X-Translation-Cache` | `hit`, `miss`, or `off` |

Missing API key: HTTP 401. IndicTrans2 missing when a Hindi or Telugu request needs it: HTTP 503. The slim install does not include torch, so those requests 503 until the translate extra and the weights are present.

## When translation is skipped

Translation runs only when the detected language is `hi` or `te`.

It is skipped when:

- the text is English, mixed, or unknown
- the request sends `X-Bypass-Translation: 1` (the original Hindi or Telugu text is sent upstream)

Translation can also lose even when it runs. On the measured baseline, input tokens were not the expensive side. It can lose when the English reply is longer than a direct Indic reply, when the reply is already short, or when masking and placeholders damage the answer. Person names are not reliably protected. The policy does not try to predict those cases. It stays the rule above.

## How cost is estimated

```
estimated_usd = (prompt_tokens * input_usd_per_million
               + completion_tokens * output_usd_per_million) / 1_000_000
estimated_inr = estimated_usd * usd_inr_rate
```

`USD_INR_RATE` default is **96.64**, confirmed by the author on 2026-10-10. Token prices live in `src/indic_token_saver/cost.py` and were confirmed the same day (for example `gemini-3.5-flash-lite` at $0.30 input / $2.50 output per 1M tokens on the published standard paid tier). Unknown model ids are not given a made-up price. Cached tokens are not discounted. The free-tier bill is ₹0. The log still stores the list-price estimate.

## Prior art

- [lingua-proxy](https://github.com/hanyoungYoo/lingua-proxy) — generic proxy that translates with an LLM, aimed mainly at input tokens.
- Tokenizer Tax — public writing on how non-English text inflates token counts.
- [IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) (AI4Bharat, MIT) — the local Indic↔English models this proxy calls for Hindi and Telugu.
- EMNLP 2024 translate-first findings — research that translating into English before a model call can change quality and cost. Not reproduced here.

Difference: this proxy is Indic-specific, uses a local translator, and is aimed at output tokens. It does not claim a measured saving.

## Run

Python 3.11+. Two installs: a slim app with no torch, and a translate extra that adds IndicTrans2.

Slim (passthrough, English, and the bypass header; Hindi and Telugu return HTTP 503):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set GEMINI_API_KEY and/or GROQ_API_KEY
PYTHONPATH=src uvicorn indic_token_saver.app:create_app --factory --host 127.0.0.1 --port 8000
```

Translate extra (local IndicTrans2). Weights are not downloaded by the app. Put them on disk yourself. A machine that already has them under the Hugging Face cache does not need to download them again.

```bash
pip install -r requirements-translate.txt
huggingface-cli download ai4bharat/indictrans2-indic-en-dist-200M
huggingface-cli download ai4bharat/indictrans2-en-indic-dist-200M
```

Models: `ai4bharat/indictrans2-indic-en-dist-200M` and `ai4bharat/indictrans2-en-indic-dist-200M`. They load on the first Hindi or Telugu request that is not bypassed.

```bash
curl -s localhost:8000/health
curl -s localhost:8000/stats
curl -s localhost:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"gemini-3.5-flash-lite","messages":[{"role":"user","content":"What is the weather in Hyderabad today?"}]}'
```

Hindi, translated by default:

```bash
curl -s localhost:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"gemini-3.5-flash-lite","messages":[{"role":"user","content":"आज हैदराबाद में मौसम कैसा है?"}]}'
```

Same Hindi prompt, translation skipped:

```bash
curl -s localhost:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -H 'X-Bypass-Translation: 1' \
  -d '{"model":"gemini-3.5-flash-lite","messages":[{"role":"user","content":"आज हैदराबाद में मौसम कैसा है?"}]}'
```

Telugu:

```bash
curl -s localhost:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"gemini-3.5-flash-lite","messages":[{"role":"user","content":"ఈరోజు హైదరాబాద్‌లో వాతావరణం ఎలా ఉంది?"}]}'
```

The app reads environment variables and, if present, a `.env` file in the working directory. `.env` is not committed. The translation cache is SQLite at `data/translation_cache.sqlite` (`CACHE_PATH`).

| Variable | Default |
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

## Tests

```bash
pytest
```

Tests are offline. They mock HTTP and inject a fake translator. They do not call Gemini or Groq, do not download weights, and do not load torch.

## Docker

The default image installs `requirements.txt` only. It does not install torch, and it does not copy `.env` or model weights. Keys come from the environment at run time.

```bash
cp .env.example .env
# edit .env on the host; do not commit it
docker compose up --build
```

Without Compose:

```bash
docker build -t indic-token-saver .
docker run --rm --env-file .env -p 8000:8000 indic-token-saver
```

The translate image is a separate target. It installs `requirements-translate.txt` on top of the slim image. It still does not bake weights or `.env` into the image. `docker compose up` does not start it.

```bash
docker build --target translate -t indic-token-saver:translate .
# or: docker compose --profile translate up --build translate
```

The process listens on `0.0.0.0:8000`. Mount `logs/` and `data/` if those files should outlive the container.

## Disclaimer

This is a personal open-source project by Aditya Venkat Chalamchala. It is unaffiliated with any employer. Built with AI coding agents; design, review, and measurements by the author.

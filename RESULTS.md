# Results

Author: Aditya Venkat Chalamchala. Personal project, unaffiliated with any employer.

No savings claim. Figures below are either the author’s passthrough baseline or one live proxy call. The 40-prompt file was not run as a batch. The Telugu baseline is incomplete. This file does not invent a Telugu token count.

List-price INR is an estimate from published paid-tier prices and `USD_INR_RATE` 96.64. On the free tier the actual bill is ₹0.

## Passthrough baseline (author, 2026-10-10)

Model: `gemini-3.5-flash-lite`. Translation off. One weather question.

| Language | User text | prompt_tokens | completion_tokens | total | Sample |
| --- | --- | --- | --- | --- | --- |
| English | What is the weather in Hyderabad today? | 9 | 27 | 36 | complete |
| Hindi | आज हैदराबाद में मौसम कैसा है? | 8 | 120 | 128 | complete |
| Telugu | — | — | — | — | incomplete |

On this short prompt, Hindi did not use more input tokens than English (8 versus 9). The Hindi reply was larger (120 completion tokens versus 27).

## When translate-first loses

The default policy still translates `hi` and `te` unless `X-Bypass-Translation: 1`. It does not score each request. From the baseline above, translation can lose when:

- the English reply is longer than a direct Indic reply, so the paid completion costs more than answering in Indic
- the reply is already short, so there is little output-token difference, while local translation still adds latency
- masking or placeholders damage the answer (a rewritten placeholder is not restored; person names are not reliably protected)

## Live proxy call (2026-10-10)

One Hindi weather question through the v0.2 proxy. Model `gemini-3.5-flash-lite`. The proxy was started from this repo’s `.venv` on `127.0.0.1:8000` and stopped afterward. `GET /health` on that address returned version `0.2.0`. Port 8000 also had a Docker listener whose `/health` was version `0.0.1`; the call below was the `0.2.0` process.

Prompt: `आज हैदराबाद में मौसम कैसा है?`

| Field | Value |
| --- | --- |
| HTTP | 200 |
| `X-Detected-Language` | `hi` |
| `X-Was-Translated` | `1` |
| `X-Translation-Cache` | `miss` |
| prompt_tokens | 10 |
| completion_tokens | 26 |
| estimated INR | 0.006572 |
| latency_ms | 6349 |

The reply was a Hindi sentence saying it does not have live weather and to check a weather app or site (119 characters). `latency_ms` includes local translation. The INR figure is the published list-price estimate (`USD_INR_RATE` 96.64). On the free tier the actual bill is ₹0.

This is one unpaired call. It is not a before/after against the passthrough baseline, and it is not a savings result. The passthrough Hindi row was 8 prompt / 120 completion for a different reply. Do not read 10 / 26 as a measured saving.

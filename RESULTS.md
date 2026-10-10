# Results

Author: Aditya Venkat Chalamchala. Personal project, unaffiliated with any employer.

No savings claim. Figures below are author-measured on **2026-10-10** with model **`gemini-3.5-flash-lite`**, one weather question, three languages (English, Hindi, Telugu). Same prompt meaning; replies differ between modes and runs.

List-price INR (when shown) is an estimate from published paid-tier prices and `USD_INR_RATE` 96.64. On the free tier the actual bill is **₹0**.

**Headline (completion tokens):** On this single question, passthrough Indic replies were much longer than translate-first (Hindi **102 → 26**, Telugu **91 → 26**). Prompt tokens stayed in the same ballpark. Latency includes local translation on translate-first runs. **n = 1** per cell; not a production guarantee.

Prompt: English — *What is the weather in Hyderabad today?* Hindi — *आज हैदराबाद में मौसम कैसा है?* Telugu — equivalent weather question in Telugu script (author’s wording).

## Translate-first (default proxy)

Translation runs for `hi` and `te` unless bypassed. `X-Was-Translated: 1` when the request was translated to English before the model call.

| Language | prompt_tokens | completion_tokens | latency_ms (approx) | translated |
| --- | ---: | ---: | ---: | --- |
| English | 9 | 27 | 1790 | 0 |
| Hindi | 10 | 26 | 1008 | 1 |
| Telugu | 10 | 26 | 6669 | 1 |

One earlier Hindi translate-first call on the same day (same question, v0.2 proxy, cache miss) reported **10 / 26**, estimated INR **0.006572**, latency **6349** ms — same completion count as the row above, slower cold-start translation.

## Passthrough (`X-Bypass-Translation: 1`)

Original Indic (or English) text sent upstream; no local translation.

| Language | prompt_tokens | completion_tokens | latency_ms (approx) |
| --- | ---: | ---: | ---: |
| English | 9 | 26 | 1161 |
| Hindi | 8 | 102 | 1225 |
| Telugu | 13 | 91 | 1268 |

## Interpretation

- **Completion tokens** are the main contrast on this prompt: direct Hindi and Telugu answers used **102** and **91** completion tokens versus **26** after translate-first (English model reply, then translated back).
- **Prompt tokens** did not swing wildly (roughly 8–13 passthrough, 9–10 translate-first on these runs).
- **Latency:** translate-first adds local IndicTrans2 work; Telugu translate-first was slow on this run (~6.7 s) while passthrough Telugu was ~1.3 s. English translate-first was slower than English passthrough here (~1.8 s vs ~1.2 s) despite `translated=0` — same question, different reply length and stack timing.
- Replies are **not identical** between modes; comparing token counts is not comparing the same text.
- This is a **paired weather trio on one date**, still **n = 1**, not a benchmark suite and not a promise of bill savings.

## When translate-first loses

The default policy still translates `hi` and `te` unless `X-Bypass-Translation: 1`. It does not score each request. Translation can lose when:

- the English reply is longer than a direct Indic reply, so the paid completion costs more than answering in Indic
- the reply is already short, so there is little output-token difference, while local translation still adds latency
- masking or placeholders damage the answer (a rewritten placeholder is not restored; person names are not reliably protected)

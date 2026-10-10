# Release notes — v0.2.0

**Author:** Aditya Venkat Chalamchala. Personal project, unaffiliated with any employer.

## What shipped

- OpenAI-compatible gateway on FastAPI: language detection, optional local IndicTrans2 translation for Hindi and Telugu, Gemini/Groq routing, JSONL request log, and `GET /stats`.
- Design and API contract: [SPEC.md](SPEC.md).
- Measurements and limitations: [RESULTS.md](RESULTS.md).

## Rollout (author plan)

| Week | Focus |
| --- | --- |
| 1 | Measure only — passthrough and proxy runs on a small prompt set (`data/prompts_v0.jsonl`), no savings claims |
| 2 | Translation path — Hindi/Telugu through local IndicTrans2, log `was_translated` and latency |
| 3 | Policy + `/stats` — default translate for `hi`/`te`, bypass header, aggregates from the log |

## Author baselines (2026-10-10)

Model `gemini-3.5-flash-lite`, translation off (passthrough), one weather question:

| Language | prompt_tokens | completion_tokens |
| --- | --- | --- |
| English | 9 | 27 |
| Hindi | 8 | 120 |
| Telugu | — | — (incomplete; no token count in [RESULTS.md](RESULTS.md)) |

One Hindi weather question through the v0.2 proxy (translation on): **10** prompt / **26** completion tokens. That single call is not paired with the passthrough row and is **not** a savings result.

## Known limitations

- Person names are not reliably masked before translation.
- Telugu passthrough baseline was not completed; do not infer Telugu token counts from this release.
- List-price INR in headers and logs uses published paid-tier constants; free-tier bills are ₹0.
- The 40-prompt file has not been run as an automated batch in CI (CI stays offline).

## After clone

```bash
git push origin v0.2.0   # personal remote, e.g. git@github.com-personal:cvaditya1/indic-token-saver.git
```

Run the local measure script (proxy on `127.0.0.1:8000` with keys in `.env`): see README **Measure**.

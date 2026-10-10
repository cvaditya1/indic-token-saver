"""Published list-price estimates. Not a bill.

The author confirmed these published prices on 2026-10-10.
The constants below are unchanged. Free-tier actual charge is INR 0.
estimated_inr is a counterfactual paid-tier list price, not a bill.
Do not quote a savings number from the passthrough baseline alone.

Sources read 2026-10-10 (assumptions, not a measurement):

USD→INR default 96.64
  Same-day public quotes sat roughly between 96.59 and 96.78.
  https://exchangeratetool.com/historical/usd-inr/2026 listed 96.64
  for 2026-10-10. Confirm before use. Override with USD_INR_RATE.

Gemini standard paid tier, text, per 1M tokens
  https://ai.google.dev/gemini-api/docs/pricing
  gemini-3.5-flash-lite  input 0.30  output 2.50
  gemini-2.5-flash       input 0.30  output 2.50  (text/image/video)
  gemini-2.5-flash-lite  input 0.10  output 0.40  (text/image/video)
  The pricing page lists the free tier as free of charge. Confirm the
  model id is still on the free tier. Output price includes thinking
  tokens on that page; this module prices usage.completion_tokens as
  output and does not add a separate reasoning field.

Groq, per 1M tokens
  https://console.groq.com/docs/models
  openai/gpt-oss-20b    input 0.075  output 0.30
  openai/gpt-oss-120b   input 0.15   output 0.60
  qwen/qwen3.8-27b      input 0.80   output 4.00
  Confirm the id is still on the free tier before use.

Audio, cache reads, batch, grounding, and storage are not priced.
Unknown model ids return None. Do not invent a price.
"""

from __future__ import annotations

from decimal import Decimal

# Author-confirmed published-price assumption, 2026-10-10. Value unchanged.
DEFAULT_USD_INR_RATE = Decimal("96.64")

# (input USD per 1M tokens, output USD per 1M tokens)
# Author-confirmed 2026-10-10. Values unchanged.
PRICES_USD_PER_MILLION: dict[str, tuple[Decimal, Decimal]] = {
    "gemini-3.5-flash-lite": (Decimal("0.30"), Decimal("2.50")),
    "gemini-2.5-flash": (Decimal("0.30"), Decimal("2.50")),
    "gemini-2.5-flash-lite": (Decimal("0.10"), Decimal("0.40")),
    "openai/gpt-oss-20b": (Decimal("0.075"), Decimal("0.30")),
    "openai/gpt-oss-120b": (Decimal("0.15"), Decimal("0.60")),
    "qwen/qwen3.8-27b": (Decimal("0.80"), Decimal("4.00")),
}

_MILLION = Decimal("1000000")
_INR_QUANTUM = Decimal("0.000001")
COST_BASIS = "published_list_price_estimate"


def estimate_inr(
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    usd_inr_rate: Decimal = DEFAULT_USD_INR_RATE,
) -> Decimal | None:
    """Return INR list-price estimate quantized to 6 decimal places, or None."""
    if prompt_tokens is None or completion_tokens is None:
        return None
    prices = PRICES_USD_PER_MILLION.get(model)
    if prices is None:
        return None
    input_price, output_price = prices
    usd = (
        Decimal(prompt_tokens) * input_price + Decimal(completion_tokens) * output_price
    ) / _MILLION
    return (usd * usd_inr_rate).quantize(_INR_QUANTUM)

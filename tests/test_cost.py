from decimal import Decimal

from indic_token_saver.cost import estimate_inr


def test_formula_gemini_flash_lite():
    # (1000 * 0.30 + 2000 * 2.50) / 1_000_000 * 96.64 = 0.512192
    got = estimate_inr(
        "gemini-3.5-flash-lite",
        1000,
        2000,
        usd_inr_rate=Decimal("96.64"),
    )
    assert got == Decimal("0.512192")


def test_groq_gpt_oss_20b():
    # (1_000_000 * 0.075 + 0) / 1_000_000 * 96.64 = 7.248
    got = estimate_inr(
        "openai/gpt-oss-20b",
        1_000_000,
        0,
        usd_inr_rate=Decimal("96.64"),
    )
    assert got == Decimal("7.248000")


def test_unknown_model_is_unpriced():
    assert estimate_inr("not-a-real-model", 10, 10) is None


def test_missing_usage_is_unpriced():
    assert estimate_inr("gemini-2.5-flash", None, 10) is None

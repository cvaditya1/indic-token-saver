from indic_token_saver.mask import mask_spans, restore_spans


def test_mask_round_trip_in_order():
    text = (
        "ధర ```print(1)``` మరియు `qty` చూడండి "
        "https://example.com/secret Rs. 1,200 ₹80 "
        "2026-10-10 10/10/2026 మొత్తం 42"
    )
    masked, spans = mask_spans(text)
    assert spans == [
        "```print(1)```",
        "`qty`",
        "https://example.com/secret",
        "Rs. 1,200",
        "₹80",
        "2026-10-10",
        "10/10/2026",
        "42",
    ]
    assert "https://example.com/secret" not in masked
    assert "<<P0>>" in masked
    assert "<<P7>>" in masked
    assert restore_spans(masked, spans) == text


def test_restore_leaves_unknown_placeholder():
    assert restore_spans("see <<P3>>", ["only"]) == "see <<P3>>"

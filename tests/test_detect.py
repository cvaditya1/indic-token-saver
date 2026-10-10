from indic_token_saver.detect import detect_language


def test_english():
    assert detect_language("What is the weather in Hyderabad today?") == "en"


def test_hindi():
    assert detect_language("आज हैदराबाद में मौसम कैसा है?") == "hi"


def test_telugu():
    assert detect_language("ఈరోజు హైదరాబాద్‌లో వాతావరణం ఎలా ఉంది?") == "te"


def test_mixed_telugu_and_english():
    assert detect_language("Hello నమస్కారం") == "mixed"


def test_english_with_rupee_amount_stays_english():
    assert detect_language("Onions cost ₹80 per kg today") == "en"


def test_digits_currency_and_url_alone_are_unknown():
    assert detect_language("₹500") == "unknown"
    assert detect_language("https://example.com/price") == "unknown"
    assert detect_language("120") == "unknown"


def test_fenced_telugu_does_not_flip_english():
    text = "Please explain this snippet.\n```python\nprint('తెలుగు')\n```"
    assert detect_language(text) == "en"


def test_inline_code_and_url_do_not_add_latin():
    text = "ధర చూడండి `price` https://example.com/onions"
    assert detect_language(text) == "te"

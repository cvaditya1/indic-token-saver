"""Policy: translate hi/te by default; bypass and other languages do not."""

import json

import httpx

from indic_token_saver.policy import should_translate
from tests.test_week2 import FakeTranslator, _client, _completion


def test_default_translates_only_hi_and_te():
    assert should_translate("hi", bypass=False) is True
    assert should_translate("te", bypass=False) is True
    assert should_translate("en", bypass=False) is False
    assert should_translate("mixed", bypass=False) is False
    assert should_translate("unknown", bypass=False) is False


def test_bypass_skips_hi_and_te():
    assert should_translate("hi", bypass=True) is False
    assert should_translate("te", bypass=True) is False
    assert should_translate("en", bypass=True) is False


def test_default_hindi_translates_and_bypass_does_not(tmp_path):
    translator = FakeTranslator()
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body["messages"][0]["content"])
        return httpx.Response(200, json=_completion("Sunny."))

    client = _client(tmp_path, translator, handler)
    prompt = "आज हैदराबाद में मौसम कैसा है?"
    payload = {
        "model": "gemini-3.5-flash-lite",
        "messages": [{"role": "user", "content": prompt}],
    }

    translated = client.post("/v1/chat/completions", json=payload)
    assert translated.status_code == 200
    assert translated.headers["x-was-translated"] == "1"
    assert translated.headers["x-detected-language"] == "hi"
    assert seen[0] != prompt
    assert translator.calls

    bypassed = client.post(
        "/v1/chat/completions",
        json=payload,
        headers={"X-Bypass-Translation": "1"},
    )
    assert bypassed.status_code == 200
    assert bypassed.headers["x-was-translated"] == "0"
    assert bypassed.headers["x-translation-cache"] == "off"
    assert seen[1] == prompt

    english = client.post(
        "/v1/chat/completions",
        json={
            "model": "gemini-3.5-flash-lite",
            "messages": [
                {"role": "user", "content": "What is the weather in Hyderabad today?"}
            ],
        },
    )
    assert english.status_code == 200
    assert english.headers["x-was-translated"] == "0"
    assert english.headers["x-detected-language"] == "en"

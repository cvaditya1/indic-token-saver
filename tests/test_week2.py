import json
import sys
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from indic_token_saver.config import Settings
from indic_token_saver.translate import TranslationUnavailable, unavailable_message


class FakeTranslator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        self.calls.append((src_lang, tgt_lang, text))
        return f"[{tgt_lang}]{text}"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        gemini_api_key="test-gemini",
        groq_api_key="test-groq",
        usd_inr_rate=Decimal("96.64"),
        log_path=tmp_path / "requests.jsonl",
        default_provider="gemini",
        default_gemini_model="gemini-3.5-flash-lite",
        default_groq_model="openai/gpt-oss-20b",
        log_prompt_hash=False,
        cache_path=tmp_path / "translation_cache.sqlite",
    )


def _completion(content: str, prompt_tokens: int = 9, completion_tokens: int = 27) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }


def _client(tmp_path: Path, translator, handler, **settings_kwargs):
    from indic_token_saver.app import create_app

    settings = _settings(tmp_path)
    if settings_kwargs:
        settings = Settings(**{**settings.__dict__, **settings_kwargs})
    app = create_app(
        settings=settings,
        transport=httpx.MockTransport(handler),
        translator=translator,
    )
    return TestClient(app)


@pytest.mark.parametrize(
    ("prompt", "src_tag", "tgt_tag"),
    [
        ("ధర https://example.com/wx చూడండి", "tel_Telu", "tel_Telu"),
        ("आज मौसम https://example.com/wx कैसा है?", "hin_Deva", "hin_Deva"),
    ],
)
def test_indic_translates_then_upstream_then_back(tmp_path, prompt, src_tag, tgt_tag):
    events: list[tuple] = []
    translator = FakeTranslator()

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        events.append(("upstream", body["messages"]))
        return httpx.Response(200, json=_completion("See <<P0>> soon"))

    def recording_translate(text: str, src_lang: str, tgt_lang: str) -> str:
        events.append(("translate", src_lang, tgt_lang, text))
        return FakeTranslator.translate(translator, text, src_lang, tgt_lang)

    translator.translate = recording_translate  # type: ignore[method-assign]
    client = _client(tmp_path, translator, handler)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gemini-3.5-flash-lite",
            "messages": [
                {"role": "system", "content": "Be brief."},
                {"role": "user", "content": prompt},
            ],
        },
    )
    assert response.status_code == 200
    assert events[0][0] == "translate"
    assert events[0][1:3] == (src_tag, "eng_Latn")
    assert "https://example.com/wx" not in events[0][3]
    assert "<<P0>>" in events[0][3]
    assert events[1][0] == "upstream"
    assert events[1][1][0]["content"] == "Be brief."
    assert events[1][1][1]["content"] == f"[eng_Latn]{events[0][3]}"
    assert events[2] == ("translate", "eng_Latn", tgt_tag, "See <<P0>> soon")
    body = response.json()
    assert body["usage"]["prompt_tokens"] == 9
    assert body["usage"]["completion_tokens"] == 27
    assert body["choices"][0]["message"]["content"] == (
        f"[{tgt_tag}]See https://example.com/wx soon"
    )
    assert response.headers["x-was-translated"] == "1"
    assert response.headers["x-translation-cache"] == "miss"
    row = json.loads((tmp_path / "requests.jsonl").read_text(encoding="utf-8"))
    assert row["was_translated"] is True
    assert row["translation_cache"] == "miss"
    assert row["prompt_tokens"] == 9
    assert row["completion_tokens"] == 27
    assert prompt not in json.dumps(row)
    assert "See <<P0>> soon" not in json.dumps(row)
    assert "https://example.com/wx" not in json.dumps(row)


def test_cache_hit_does_not_call_translator_twice(tmp_path):
    translator = FakeTranslator()
    prompt = "ఈరోజు వాతావరణం ఎలా ఉంది?"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_completion("Sunny."))

    client = _client(tmp_path, translator, handler)
    payload = {
        "model": "gemini-3.5-flash-lite",
        "messages": [{"role": "user", "content": prompt}],
    }
    first = client.post("/v1/chat/completions", json=payload)
    calls_after_first = len(translator.calls)
    assert first.status_code == 200
    assert first.headers["x-translation-cache"] == "miss"
    assert calls_after_first == 2
    second = client.post("/v1/chat/completions", json=payload)
    assert second.status_code == 200
    assert second.headers["x-translation-cache"] == "hit"
    assert len(translator.calls) == calls_after_first
    assert second.json()["choices"][0]["message"]["content"] == first.json()["choices"][0]["message"]["content"]


def test_bypass_header_skips_translation(tmp_path):
    translator = FakeTranslator()
    seen = {}
    prompt = "आज हैदराबाद में मौसम कैसा है?"

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion("Sunny."))

    client = _client(tmp_path, translator, handler)
    response = client.post(
        "/v1/chat/completions",
        headers={"X-Bypass-Translation": "1"},
        json={
            "model": "gemini-3.5-flash-lite",
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    assert response.status_code == 200
    assert translator.calls == []
    assert seen["body"]["messages"][0]["content"] == prompt
    assert response.json()["choices"][0]["message"]["content"] == "Sunny."
    assert response.headers["x-was-translated"] == "0"
    assert response.headers["x-translation-cache"] == "off"
    assert response.headers["x-detected-language"] == "hi"


def test_english_passthrough_does_not_translate(tmp_path):
    translator = FakeTranslator()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion("Sunny."))

    client = _client(tmp_path, translator, handler)
    prompt = "What is the weather in Hyderabad today?"
    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": prompt}]},
    )
    assert response.status_code == 200
    assert translator.calls == []
    assert seen["body"]["messages"][0]["content"] == prompt
    assert response.headers["x-was-translated"] == "0"
    assert response.headers["x-translation-cache"] == "off"


@pytest.mark.parametrize("prompt", ["Hello నమస్కారం", "120"])
def test_mixed_and_unknown_passthrough(tmp_path, prompt):
    translator = FakeTranslator()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_completion("Sunny."))

    client = _client(tmp_path, translator, handler)
    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": prompt}]},
    )
    assert response.status_code == 200
    assert translator.calls == []
    assert response.headers["x-translation-cache"] == "off"


def test_missing_weights_return_503_without_upstream(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("upstream should not be called")

    class Unavailable:
        def ensure_ready(self) -> None:
            raise TranslationUnavailable(unavailable_message())

        def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
            raise AssertionError("translator should not run")

    client = _client(tmp_path, Unavailable(), handler)
    response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "ఈరోజు వాతావరణం ఎలా ఉంది?"}],
        },
    )
    assert response.status_code == 503
    message = response.json()["error"]["message"]
    assert "ai4bharat/indictrans2-indic-en-dist-200M" in message
    assert "ai4bharat/indictrans2-en-indic-dist-200M" in message
    assert "requirements-translate.txt" in message
    assert not (tmp_path / "requests.jsonl").exists()


def test_import_does_not_load_torch():
    import indic_token_saver.app  # noqa: F401
    import indic_token_saver.translate  # noqa: F401

    assert "torch" not in sys.modules


def test_slim_requirements_and_dockerfile_skip_torch():
    root = Path(__file__).resolve().parents[1]
    requirements = (root / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "torch" not in requirements
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY .env" not in dockerfile
    assert "translate-cpu" in dockerfile
    assert "translate-cuda" in dockerfile
    assert dockerfile.rstrip().endswith("FROM translate-cpu AS default")
    translate_cpu = (root / "requirements-translate-cpu.txt").read_text(encoding="utf-8")
    assert "torch" in translate_cpu

import json
from decimal import Decimal
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from indic_token_saver.config import Settings
from indic_token_saver.detect import detect_language


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = dict(
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
    values.update(overrides)
    return Settings(**values)


def _completion(prompt_tokens=1000, completion_tokens=2000):
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Sunny."},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }


def test_mocked_completion_writes_log(tmp_path):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion())

    from indic_token_saver.app import create_app

    app = create_app(
        settings=_settings(tmp_path),
        transport=httpx.MockTransport(handler),
    )
    prompt = "What is the weather in Hyderabad today?"
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gemini-3.5-flash-lite",
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Sunny."
    assert response.headers["x-detected-language"] == "en"
    assert response.headers["x-estimated-cost-inr"] == "0.512192"
    assert response.headers["x-was-translated"] == "0"
    assert response.headers["x-translation-cache"] == "off"
    assert seen["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    )
    assert seen["auth"] == "Bearer test-gemini"
    assert seen["body"]["model"] == "gemini-3.5-flash-lite"
    lines = (tmp_path / "requests.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["provider"] == "gemini"
    assert row["detected_lang"] == "en"
    assert row["prompt_tokens"] == 1000
    assert row["completion_tokens"] == 2000
    assert row["estimated_inr"] == "0.512192"
    assert row["cost_basis"] == "published_list_price_estimate"
    assert row["was_translated"] is False
    assert row["translation_cache"] == "off"
    assert prompt not in lines[0]
    assert "prompt_sha256" not in row


def test_groq_prefix(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.groq.com"
        body = json.loads(request.content)
        assert body["model"] == "openai/gpt-oss-20b"
        assert request.headers["authorization"] == "Bearer test-groq"
        return httpx.Response(200, json=_completion(10, 0))

    from indic_token_saver.app import create_app

    class _Echo:
        def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
            return text

    app = create_app(
        settings=_settings(tmp_path),
        transport=httpx.MockTransport(handler),
        translator=_Echo(),
    )
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "groq/openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": "आज हैदराबाद में मौसम कैसा है?"}],
        },
    )
    assert response.status_code == 200
    assert response.headers["x-detected-language"] == "hi"


def test_stream_rejected_without_upstream(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("upstream should not be called")

    from indic_token_saver.app import create_app

    app = create_app(
        settings=_settings(tmp_path),
        transport=httpx.MockTransport(handler),
    )
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gemini-3.5-flash-lite",
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 400
    assert not (tmp_path / "requests.jsonl").exists()


def test_missing_key(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("upstream should not be called")

    from indic_token_saver.app import create_app

    app = create_app(
        settings=_settings(tmp_path, gemini_api_key=""),
        transport=httpx.MockTransport(handler),
    )
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 401


def test_health_ok(tmp_path):
    from indic_token_saver.app import create_app

    client = TestClient(create_app(settings=_settings(tmp_path)))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "0.2.0"


def test_prompt_file_languages_and_balance():
    path = Path(__file__).resolve().parents[1] / "data" / "prompts_v0.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert 36 <= len(rows) <= 48
    counts = {"en": 0, "hi": 0, "te": 0}
    for row in rows:
        assert row["source"] == "homemade"
        assert row["lang"] in counts
        assert detect_language(row["text"]) == row["lang"]
        counts[row["lang"]] += 1
    assert counts["en"] >= 12
    assert counts["hi"] >= 12
    assert counts["te"] >= 12

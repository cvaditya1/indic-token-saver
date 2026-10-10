"""GET /stats percentiles on a tiny JSONL fixture. Offline, no torch."""

import json

from fastapi.testclient import TestClient

from indic_token_saver.stats import percentile_nearest_rank, summarize_log
from test_route import _settings


def _row(**overrides) -> dict:
    record = {
        "ts": "2026-10-10T00:00:00.000000Z",
        "provider": "gemini",
        "model": "gemini-3.5-flash-lite",
        "detected_lang": "en",
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "latency_ms": 1,
        "estimated_inr": "0.100000",
        "request_id": "r",
        "cost_basis": "published_list_price_estimate",
        "was_translated": False,
        "translation_cache": "off",
    }
    record.update(overrides)
    return record


# Five latencies. Nearest rank: p50 index ceil(2.5)-1 = 2 → 30.
# p95 index ceil(4.75)-1 = 4 → 100.
_FIXTURE = [
    _row(latency_ms=10, prompt_tokens=9, completion_tokens=27, estimated_inr="0.010000", was_translated=False, detected_lang="en", request_id="1"),
    _row(latency_ms=20, prompt_tokens=8, completion_tokens=12, estimated_inr="0.020000", was_translated=False, detected_lang="hi", request_id="2"),
    _row(latency_ms=30, prompt_tokens=4, completion_tokens=5, estimated_inr="0.030000", was_translated=True, detected_lang="hi", request_id="3"),
    _row(latency_ms=40, prompt_tokens=2, completion_tokens=3, estimated_inr="0.040000", was_translated=True, detected_lang="te", request_id="4"),
    _row(latency_ms=100, prompt_tokens=1, completion_tokens=1, estimated_inr=None, was_translated=True, detected_lang="te", request_id="5"),
]


def test_nearest_rank_on_the_fixture_latencies():
    latencies = [row["latency_ms"] for row in _FIXTURE]
    assert percentile_nearest_rank(latencies, 50) == 30
    assert percentile_nearest_rank(latencies, 95) == 100
    assert percentile_nearest_rank([], 50) == 0


def test_stats_empty_log_is_zeros(tmp_path):
    from indic_token_saver.app import create_app

    client = TestClient(create_app(settings=_settings(tmp_path)))
    response = client.get("/stats")
    assert response.status_code == 200
    assert response.json() == {
        "count": 0,
        "p50_latency_ms": 0,
        "p95_latency_ms": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "estimated_inr": "0.000000",
        "by_was_translated": {},
        "by_detected_lang": {},
    }


def test_stats_fixture_percentiles_and_splits(tmp_path):
    log_path = tmp_path / "requests.jsonl"
    lines = [json.dumps(row) for row in _FIXTURE]
    lines.append("not-json")
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    body = summarize_log(log_path)
    assert body["count"] == 5
    assert body["p50_latency_ms"] == 30
    assert body["p95_latency_ms"] == 100
    assert body["prompt_tokens"] == 9 + 8 + 4 + 2 + 1
    assert body["completion_tokens"] == 27 + 12 + 5 + 3 + 1
    assert body["estimated_inr"] == "0.100000"

    passthrough = body["by_was_translated"]["false"]
    assert passthrough["count"] == 2
    assert passthrough["p50_latency_ms"] == 10
    assert passthrough["p95_latency_ms"] == 20
    assert passthrough["prompt_tokens"] == 17
    assert passthrough["completion_tokens"] == 39

    translated = body["by_was_translated"]["true"]
    assert translated["count"] == 3
    assert translated["p50_latency_ms"] == 40
    assert translated["p95_latency_ms"] == 100
    assert translated["estimated_inr"] == "0.070000"

    assert body["by_detected_lang"]["en"]["count"] == 1
    assert body["by_detected_lang"]["en"]["p50_latency_ms"] == 10
    assert body["by_detected_lang"]["en"]["p95_latency_ms"] == 10
    assert body["by_detected_lang"]["hi"]["p50_latency_ms"] == 20
    assert body["by_detected_lang"]["hi"]["p95_latency_ms"] == 30
    assert body["by_detected_lang"]["te"]["p50_latency_ms"] == 40
    assert body["by_detected_lang"]["te"]["p95_latency_ms"] == 100

    from indic_token_saver.app import create_app

    client = TestClient(create_app(settings=_settings(tmp_path)))
    assert client.get("/stats").json() == body

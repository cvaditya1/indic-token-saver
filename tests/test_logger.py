import json

from indic_token_saver.jsonl_log import append_jsonl, build_record


def test_one_json_line_without_prompt(tmp_path):
    prompt = "UNIQUE_PROMPT_BODY_should_not_be_logged_ధర"
    path = tmp_path / "nested" / "requests.jsonl"
    record = build_record(
        provider="gemini",
        model="gemini-3.5-flash-lite",
        detected_lang="te",
        prompt_tokens=12,
        completion_tokens=4,
        latency_ms=30,
        estimated_inr="0.010000",
        request_id="req-1",
        was_translated=False,
        translation_cache="off",
        ts="2026-10-10T00:00:00.000000Z",
    )
    append_jsonl(path, record)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    loaded = json.loads(lines[0])
    assert loaded["provider"] == "gemini"
    assert loaded["estimated_inr"] == "0.010000"
    assert loaded["cost_basis"] == "published_list_price_estimate"
    assert loaded["was_translated"] is False
    assert loaded["translation_cache"] == "off"
    assert prompt not in lines[0]
    assert "prompt" not in loaded
    assert "messages" not in loaded

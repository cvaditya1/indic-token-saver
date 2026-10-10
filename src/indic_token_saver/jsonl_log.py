"""Append-only JSONL request log. Never stores prompt or completion text."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from indic_token_saver.cost import COST_BASIS

_REQUIRED = (
    "ts",
    "provider",
    "model",
    "detected_lang",
    "prompt_tokens",
    "completion_tokens",
    "latency_ms",
    "estimated_inr",
    "request_id",
    "cost_basis",
    "was_translated",
    "translation_cache",
)

_CACHE_VALUES = {"hit", "miss", "off"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def build_record(
    *,
    provider: str,
    model: str,
    detected_lang: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    latency_ms: int,
    estimated_inr: str | None,
    request_id: str,
    was_translated: bool,
    translation_cache: str,
    prompt_sha256: str | None = None,
    ts: str | None = None,
) -> dict:
    if not isinstance(was_translated, bool):
        raise ValueError("was_translated must be a bool")
    if translation_cache not in _CACHE_VALUES:
        raise ValueError("translation_cache must be hit, miss, or off")
    record = {
        "ts": ts or utc_now(),
        "provider": provider,
        "model": model,
        "detected_lang": detected_lang,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": latency_ms,
        "estimated_inr": estimated_inr,
        "request_id": request_id,
        "cost_basis": COST_BASIS,
        "was_translated": was_translated,
        "translation_cache": translation_cache,
    }
    if prompt_sha256 is not None:
        record["prompt_sha256"] = prompt_sha256
    return record


def append_jsonl(path: Path, record: dict) -> None:
    missing = [key for key in _REQUIRED if key not in record]
    if missing:
        raise ValueError(f"log record missing {missing}")
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")

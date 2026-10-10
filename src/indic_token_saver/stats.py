"""Summarize the JSONL request log. No new database."""

from __future__ import annotations

import json
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path

_INR_QUANTUM = Decimal("0.000001")
_ZERO_INR = format(Decimal("0").quantize(_INR_QUANTUM), "f")


def summarize_log(path: Path) -> dict:
    """Return counts, latency percentiles, and token/INR totals.

    An empty or missing log returns zeros and empty splits.
    """
    rows = _usable_rows(path)
    return {
        **_bucket(rows),
        "by_was_translated": _split(rows, lambda row: "true" if row["was_translated"] else "false"),
        "by_detected_lang": _split(rows, lambda row: row["detected_lang"]),
    }


def percentile_nearest_rank(values: list[int], percent: int) -> int:
    """Nearest-rank percentile. Index is ceil(p/100 * n) - 1."""
    if not values:
        return 0
    ordered = sorted(values)
    rank = math.ceil((percent / 100) * len(ordered)) - 1
    rank = max(0, min(rank, len(ordered) - 1))
    return ordered[rank]


def _split(rows: list[dict], key_fn) -> dict:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(str(key_fn(row)), []).append(row)
    return {key: _bucket(group) for key, group in groups.items()}


def _bucket(rows: list[dict]) -> dict:
    if not rows:
        return {
            "count": 0,
            "p50_latency_ms": 0,
            "p95_latency_ms": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "estimated_inr": _ZERO_INR,
        }
    latencies = [row["latency_ms"] for row in rows]
    inr = sum((row["estimated_inr"] for row in rows), Decimal("0")).quantize(_INR_QUANTUM)
    return {
        "count": len(rows),
        "p50_latency_ms": percentile_nearest_rank(latencies, 50),
        "p95_latency_ms": percentile_nearest_rank(latencies, 95),
        "prompt_tokens": sum(row["prompt_tokens"] for row in rows),
        "completion_tokens": sum(row["completion_tokens"] for row in rows),
        "estimated_inr": format(inr, "f"),
    }


def _usable_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        parsed = _parse_row(raw)
        if parsed is not None:
            rows.append(parsed)
    return rows


def _parse_row(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    latency = raw.get("latency_ms")
    if isinstance(latency, bool) or not isinstance(latency, int):
        return None
    if not isinstance(raw.get("was_translated"), bool):
        return None
    lang = raw.get("detected_lang")
    if not isinstance(lang, str):
        return None
    prompt = _token_count(raw.get("prompt_tokens"))
    completion = _token_count(raw.get("completion_tokens"))
    inr = _inr(raw.get("estimated_inr"))
    if prompt is None or completion is None or inr is None:
        return None
    return {
        "latency_ms": latency,
        "was_translated": raw["was_translated"],
        "detected_lang": lang,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "estimated_inr": inr,
    }


def _token_count(value: object) -> int | None:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _inr(value: object) -> Decimal | None:
    if value is None:
        return Decimal("0")
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None

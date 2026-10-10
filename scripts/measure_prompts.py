#!/usr/bin/env python3
"""POST prompts from data/prompts_v0.jsonl to a local indic-token-saver proxy."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any

import httpx

DEFAULT_BASE = "http://127.0.0.1:8000"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_PROMPTS = Path(__file__).resolve().parent.parent / "data" / "prompts_v0.jsonl"


def _load_prompts(path: Path, limit: int | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def _measure_one(
    client: httpx.Client,
    base_url: str,
    model: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": row["text"]}],
    }
    started = time.perf_counter()
    response = client.post(f"{base_url}/v1/chat/completions", json=payload)
    latency_ms = int((time.perf_counter() - started) * 1000)
    headers = response.headers
    body: dict[str, Any] = {}
    if response.content:
        try:
            body = response.json()
        except json.JSONDecodeError:
            body = {"raw": response.text[:500]}

    usage = body.get("usage") or {}
    return {
        "id": row.get("id"),
        "expected_lang": row.get("lang"),
        "http_status": response.status_code,
        "detected_lang": headers.get("x-detected-language"),
        "was_translated": headers.get("x-was-translated"),
        "estimated_inr": headers.get("x-estimated-cost-inr"),
        "translation_cache": headers.get("x-translation-cache"),
        "request_id": headers.get("x-request-id"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "latency_ms": latency_ms,
        "error": body.get("error") if response.status_code >= 400 else None,
    }


def _print_summary(records: list[dict[str, Any]]) -> None:
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        key = rec.get("expected_lang") or rec.get("detected_lang") or "?"
        by_lang[key].append(rec)

    print("\nSummary by expected_lang (successful HTTP 200 only):")
    print(
        f"{'lang':<6} {'n':>4} {'p50_lat':>8} {'avg_prompt':>10} "
        f"{'avg_compl':>10} {'translated':>10}"
    )
    for lang in sorted(by_lang):
        ok = [r for r in by_lang[lang] if r.get("http_status") == 200]
        if not ok:
            print(f"{lang:<6} {0:>4}  (no 200 responses)")
            continue
        lats = sorted(r["latency_ms"] for r in ok)
        p50 = lats[len(lats) // 2]
        prompts = [r["prompt_tokens"] for r in ok if r.get("prompt_tokens") is not None]
        compl = [r["completion_tokens"] for r in ok if r.get("completion_tokens") is not None]
        translated = sum(1 for r in ok if r.get("was_translated") == "1")
        avg_p = f"{mean(prompts):.1f}" if prompts else "—"
        avg_c = f"{mean(compl):.1f}" if compl else "—"
        print(
            f"{lang:<6} {len(ok):>4} {p50:>8} {avg_p:>10} {avg_c:>10} {translated:>10}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompts",
        type=Path,
        default=DEFAULT_PROMPTS,
        help=f"JSONL prompt file (default: {DEFAULT_PROMPTS.name})",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE, help="Proxy base URL")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model id for completions")
    parser.add_argument("--limit", type=int, default=None, help="Max prompts to run")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="JSONL output (default: results/measure_YYYYMMDD.jsonl)",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Skip writing JSONL; print summary only",
    )
    args = parser.parse_args(argv)

    if not args.prompts.is_file():
        print(f"Prompt file not found: {args.prompts}", file=sys.stderr)
        return 1

    rows = _load_prompts(args.prompts, args.limit)
    if not rows:
        print("No prompts loaded.", file=sys.stderr)
        return 1

    out_path = args.out
    if out_path is None and not args.no_write:
        out_dir = Path(__file__).resolve().parent.parent / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"measure_{date.today():%Y%m%d}.jsonl"

    records: list[dict[str, Any]] = []
    timeout = httpx.Timeout(120.0, connect=10.0)
    with httpx.Client(timeout=timeout) as client:
        health = client.get(f"{args.base_url.rstrip('/')}/health")
        if health.status_code != 200:
            print(
                f"Proxy not healthy at {args.base_url} (HTTP {health.status_code}). "
                "Start uvicorn locally with API keys in .env.",
                file=sys.stderr,
            )
            return 1
        for row in rows:
            rec = _measure_one(client, args.base_url.rstrip("/"), args.model, row)
            records.append(rec)
            print(
                f"{rec['id']}: HTTP {rec['http_status']} "
                f"detected={rec['detected_lang']} translated={rec['was_translated']} "
                f"tokens={rec.get('prompt_tokens')}/{rec.get('completion_tokens')} "
                f"latency_ms={rec['latency_ms']}",
                flush=True,
            )

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"\nWrote {len(records)} rows to {out_path}")

    _print_summary(records)
    failed = sum(1 for r in records if r.get("http_status") != 200)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

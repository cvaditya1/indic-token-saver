"""Gemini and Groq OpenAI-compatible clients. Passthrough only."""

from __future__ import annotations

import json
from typing import Any

import httpx

from indic_token_saver.config import Settings

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
GROQ_BASE = "https://api.groq.com/openai/v1"
_GROQ_MODEL_PREFIXES = ("openai/", "qwen/", "meta-llama/", "llama-")


def select_provider(model: str | None, settings: Settings) -> tuple[str, str]:
    """Return (provider, upstream model id)."""
    if model is None or model.strip() == "":
        if settings.default_provider == "groq":
            return "groq", settings.default_groq_model
        return "gemini", settings.default_gemini_model
    if model.startswith("groq/"):
        return "groq", model[len("groq/") :]
    if model.startswith("gemini/"):
        return "gemini", model[len("gemini/") :]
    if model.startswith("gemini-"):
        return "gemini", model
    if model.startswith(_GROQ_MODEL_PREFIXES):
        return "groq", model
    if settings.default_provider == "groq":
        return "groq", model
    return "gemini", model


def endpoint(provider: str) -> str:
    base = GROQ_BASE if provider == "groq" else GEMINI_BASE
    return f"{base}/chat/completions"


def api_key(provider: str, settings: Settings) -> str:
    if provider == "groq":
        return settings.groq_api_key
    return settings.gemini_api_key


def usage_tokens(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if not isinstance(prompt, int) or not isinstance(completion, int):
        return None, None
    return prompt, completion


async def post_chat(
    provider: str,
    model: str,
    body: dict[str, Any],
    settings: Settings,
    transport: httpx.BaseTransport | None = None,
) -> httpx.Response:
    payload = dict(body)
    payload["model"] = model
    payload.pop("stream", None)
    headers = {
        "Authorization": f"Bearer {api_key(provider, settings)}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(transport=transport, timeout=60.0) as client:
        response = await client.post(endpoint(provider), json=payload, headers=headers)
        await response.aread()
        return response


def parse_json(response: httpx.Response) -> dict[str, Any] | None:
    try:
        parsed = response.json()
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None

"""FastAPI app: passthrough chat completions, optional Indic translation, measure log."""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from indic_token_saver import __version__
from indic_token_saver.cache import TranslationCache
from indic_token_saver.config import Settings
from indic_token_saver.cost import estimate_inr
from indic_token_saver.detect import detect_language, user_text
from indic_token_saver.jsonl_log import append_jsonl, build_record
from indic_token_saver.mask import mask_spans, restore_spans
from indic_token_saver.policy import should_translate
from indic_token_saver.stats import summarize_log
from indic_token_saver.providers import (
    api_key,
    parse_json,
    post_chat,
    select_provider,
    usage_tokens,
)
from indic_token_saver.translate import (
    LANG_TAGS,
    IndicTrans2Translator,
    TranslationUnavailable,
    Translator,
    merge_cache_status,
    route,
    unavailable_message,
)


def create_app(
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
    translator: Translator | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="indic-token-saver", version=__version__)
    app.state.settings = settings
    app.state.transport = transport
    app.state.translator = translator if translator is not None else IndicTrans2Translator()
    app.state.translation_cache = TranslationCache(settings.cache_path)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/stats")
    def stats() -> dict:
        return summarize_log(settings.log_path)

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        try:
            body = await request.json()
        except Exception:
            return _error(400, "request body must be JSON", "invalid_request_error")
        if not isinstance(body, dict):
            return _error(400, "request body must be a JSON object", "invalid_request_error")

        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            return _error(400, "messages is required", "invalid_request_error")
        for message in messages:
            if not isinstance(message, dict) or "role" not in message:
                return _error(400, "each message needs a role", "invalid_request_error")
            if not isinstance(message.get("content"), str):
                return _error(
                    400,
                    "string message content only",
                    "invalid_request_error",
                )
        if body.get("stream") is True:
            return _error(400, "stream=true is not supported", "invalid_request_error")

        model_field = body.get("model")
        if model_field is not None and not isinstance(model_field, str):
            return _error(400, "model must be a string", "invalid_request_error")

        provider, upstream_model = select_provider(model_field, settings)
        key = api_key(provider, settings)
        if not key:
            env_name = "GROQ_API_KEY" if provider == "groq" else "GEMINI_API_KEY"
            return _error(401, f"missing {env_name}", "auth_error")

        text = user_text(messages)
        detected = detect_language(text)
        bypass = request.headers.get("x-bypass-translation") == "1"
        translate_now = should_translate(detected, bypass=bypass)
        translator_impl: Translator = request.app.state.translator
        cache: TranslationCache = request.app.state.translation_cache
        cache_statuses: list[str] = []
        spans: list[str] = []
        outgoing = body

        started = time.perf_counter()
        if translate_now:
            try:
                await _ensure_ready(translator_impl)
                outgoing, spans, request_statuses = await _translate_request(
                    messages,
                    body,
                    LANG_TAGS[detected],
                    cache,
                    translator_impl,
                )
            except TranslationUnavailable:
                return _error(503, unavailable_message(), "translation_unavailable")
            cache_statuses.extend(request_statuses)

        request_id = str(uuid.uuid4())
        try:
            upstream = await post_chat(
                provider,
                upstream_model,
                outgoing,
                settings,
                transport=request.app.state.transport,
            )
        except httpx.HTTPError:
            return _error(502, "upstream request failed", "proxy_error")

        payload = parse_json(upstream)
        prompt_tokens = None
        completion_tokens = None
        if payload is not None:
            prompt_tokens, completion_tokens = usage_tokens(payload)

        reply_payload = payload
        if translate_now and payload is not None and upstream.status_code == 200:
            try:
                reply_payload, reply_statuses = await _translate_reply(
                    payload,
                    LANG_TAGS[detected],
                    spans,
                    cache,
                    translator_impl,
                )
            except TranslationUnavailable:
                reply_payload = None
                reply_failed = True
                reply_statuses = []
            else:
                reply_failed = False
            cache_statuses.extend(reply_statuses)
        else:
            reply_failed = False

        latency_ms = int((time.perf_counter() - started) * 1000)
        inr = estimate_inr(
            upstream_model,
            prompt_tokens,
            completion_tokens,
            usd_inr_rate=settings.usd_inr_rate,
        )
        was_translated = translate_now
        translation_cache = merge_cache_status(cache_statuses) if translate_now else "off"
        prompt_sha = None
        if settings.log_prompt_hash:
            prompt_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        append_jsonl(
            settings.log_path,
            build_record(
                provider=provider,
                model=upstream_model,
                detected_lang=detected,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                estimated_inr=format(inr, "f") if inr is not None else None,
                request_id=request_id,
                was_translated=was_translated,
                translation_cache=translation_cache,
                prompt_sha256=prompt_sha,
            ),
        )

        headers = {
            "X-Detected-Language": detected,
            "X-Estimated-Cost-Inr": format(inr, "f") if inr is not None else "",
            "X-Request-Id": request_id,
            "X-Was-Translated": "1" if was_translated else "0",
            "X-Translation-Cache": translation_cache,
        }
        if reply_failed:
            return _error(503, unavailable_message(), "translation_unavailable")
        if payload is None:
            return JSONResponse(
                status_code=502,
                content={
                    "error": {
                        "message": "upstream response was not JSON",
                        "type": "proxy_error",
                    }
                },
                headers=headers,
            )
        if translate_now:
            return JSONResponse(
                status_code=upstream.status_code,
                content=reply_payload,
                headers=headers,
            )
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type="application/json",
            headers=headers,
        )

    return app


async def _ensure_ready(translator: Translator) -> None:
    ready = getattr(translator, "ensure_ready", None)
    if ready is None:
        return
    await asyncio.to_thread(ready)


async def _cached_translate(
    cache: TranslationCache,
    translator: Translator,
    text: str,
    src_lang: str,
    tgt_lang: str,
) -> tuple[str, str]:
    direction, model_id = route(src_lang, tgt_lang)
    cached = cache.get(direction, src_lang, tgt_lang, model_id, text)
    if cached is not None:
        return cached, "hit"
    output = await asyncio.to_thread(translator.translate, text, src_lang, tgt_lang)
    cache.put(direction, src_lang, tgt_lang, model_id, text, output)
    return output, "miss"


async def _translate_request(
    messages: list[dict],
    body: dict,
    src_tag: str,
    cache: TranslationCache,
    translator: Translator,
) -> tuple[dict, list[str], list[str]]:
    spans: list[str] = []
    statuses: list[str] = []
    prepared: list[dict] = []
    for message in messages:
        if message.get("role") != "user":
            prepared.append(dict(message))
            continue
        masked, local_spans = mask_spans(message["content"])
        english, status = await _cached_translate(
            cache, translator, masked, src_tag, "eng_Latn"
        )
        english = _shift_placeholders(english, len(spans), len(local_spans))
        spans.extend(local_spans)
        statuses.append(status)
        prepared.append({**message, "content": english})
    outgoing = dict(body)
    outgoing["messages"] = prepared
    return outgoing, spans, statuses


async def _translate_reply(
    payload: dict,
    tgt_tag: str,
    spans: list[str],
    cache: TranslationCache,
    translator: Translator,
) -> tuple[dict, list[str]]:
    statuses: list[str] = []
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return payload, statuses
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        translated, status = await _cached_translate(
            cache, translator, content, "eng_Latn", tgt_tag
        )
        statuses.append(status)
        message["content"] = restore_spans(translated, spans)
    return payload, statuses


def _shift_placeholders(text: str, offset: int, count: int) -> str:
    if offset == 0 or count == 0:
        return text
    for index in range(count - 1, -1, -1):
        text = text.replace(f"<<P{index}>>", f"<<P{offset + index}>>")
    return text


def _error(status: int, message: str, error_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": error_type}},
    )

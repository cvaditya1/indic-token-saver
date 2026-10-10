"""Local IndicTrans2. Torch imports stay inside the loader.

Tests inject a fake translator. This module does not download weights.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Protocol

logger = logging.getLogger(__name__)

_device_logged = False

INDIC_EN_MODEL = "ai4bharat/indictrans2-indic-en-dist-200M"
EN_INDIC_MODEL = "ai4bharat/indictrans2-en-indic-dist-200M"

LANG_TAGS = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "te": "tel_Telu",
}


class TranslationUnavailable(Exception):
    """Weights or the translate extra are not installed."""


class Translator(Protocol):
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """Translate one string. Language values are IndicTrans2 tags."""


def unavailable_message() -> str:
    return (
        "IndicTrans2 is not available. "
        f"Models: {INDIC_EN_MODEL}, {EN_INDIC_MODEL}. "
        "Install the translate extra: pip install -r requirements-translate.txt"
    )


def route(src_lang: str, tgt_lang: str) -> tuple[str, str]:
    """Return (direction, model id) for a language-tag pair."""
    if tgt_lang == "eng_Latn" and src_lang in {"hin_Deva", "tel_Telu"}:
        return "indic-en", INDIC_EN_MODEL
    if src_lang == "eng_Latn" and tgt_lang in {"hin_Deva", "tel_Telu"}:
        return "en-indic", EN_INDIC_MODEL
    raise ValueError(f"unsupported translation {src_lang} -> {tgt_lang}")


def merge_cache_status(statuses: list[str]) -> str:
    if not statuses:
        return "off"
    if "miss" in statuses:
        return "miss"
    return "hit"


class IndicTrans2Translator:
    """Lazy loader. First hi/te request loads both distilled checkpoints."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bundles: dict[str, tuple[object, object, object, str]] = {}

    def ensure_ready(self) -> None:
        self._bundle(INDIC_EN_MODEL)
        self._bundle(EN_INDIC_MODEL)

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        if text == "":
            return ""
        _direction, model_id = route(src_lang, tgt_lang)
        model, tokenizer, processor, device = self._bundle(model_id)
        import torch

        batch = processor.preprocess_batch(
            [text],
            src_lang=src_lang,
            tgt_lang=tgt_lang,
        )
        inputs = tokenizer(
            batch,
            truncation=True,
            padding="longest",
            return_tensors="pt",
            return_attention_mask=True,
        )
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                use_cache=True,
                min_length=0,
                max_length=256,
                num_beams=5,
                num_return_sequences=1,
            )
        decoded = tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )
        outputs = processor.postprocess_batch(decoded, lang=tgt_lang)
        return str(outputs[0])

    def _bundle(self, model_id: str) -> tuple[object, object, object, str]:
        with self._lock:
            cached = self._bundles.get(model_id)
            if cached is not None:
                return cached
            loaded = _load_model(model_id)
            self._bundles[model_id] = loaded
            return loaded


def _resolve_device(torch: object) -> tuple[str, object]:
    """Pick inference device: TRANSLATE_DEVICE, else CUDA if available, else CPU."""
    global _device_logged
    raw = os.environ.get("TRANSLATE_DEVICE", "").strip().lower()
    if raw:
        if raw not in {"cpu", "cuda", "mps"}:
            raise ValueError(
                f"invalid TRANSLATE_DEVICE={raw!r}; use cpu, cuda, or mps"
            )
        device = raw
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"

    dtype = torch.float16 if device == "cuda" else torch.float32
    if not _device_logged:
        logger.info("IndicTrans2 inference device: %s", device)
        _device_logged = True
    return device, dtype


def _load_model(model_id: str) -> tuple[object, object, object, str]:
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as exc:
        raise TranslationUnavailable(unavailable_message()) from exc
    try:
        from IndicTransToolkit.processor import IndicProcessor
    except ImportError:
        try:
            from IndicTransToolkit import IndicProcessor
        except ImportError as exc:
            raise TranslationUnavailable(unavailable_message()) from exc

    device, dtype = _resolve_device(torch)

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            trust_remote_code=True,
            local_files_only=True,
        )
        model = AutoModelForSeq2SeqLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            local_files_only=True,
            torch_dtype=dtype,
        )
    except Exception as exc:
        raise TranslationUnavailable(unavailable_message()) from exc

    model = model.to(device)
    model.eval()
    # transformers 4.51+ feeds encoder-decoder generate() a DynamicCache.
    # IndicTrans2 modeling only accepts the legacy tuple cache.
    model.__class__._supports_default_dynamic_cache = classmethod(lambda cls: False)
    processor = IndicProcessor(inference=True)
    return model, tokenizer, processor, device

"""Translate policy. Explicit and small. Not an eval harness."""

from __future__ import annotations

TRANSLATE_LANGS = frozenset({"hi", "te"})


def should_translate(detected_lang: str, *, bypass: bool) -> bool:
    """Translate only Hindi and Telugu, unless the caller sets the bypass header.

    `bypass` is true only when `X-Bypass-Translation` is the string ``1``.
    English, mixed, and unknown stay passthrough either way.
    """
    if bypass:
        return False
    return detected_lang in TRANSLATE_LANGS

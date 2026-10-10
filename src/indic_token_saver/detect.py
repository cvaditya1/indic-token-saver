"""Script detection for Telugu, Hindi (Devanagari), and English.

Code fences, inline code, and URLs are removed before counting.
Digits, punctuation, and currency signs are not counted, so they
cannot flip the label on their own.
"""

from __future__ import annotations

import re

_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE = re.compile(r"`[^`\n]*`")
_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

_DOMINANT = 0.80


def user_text(messages: list[dict]) -> str:
    parts: list[str] = []
    for message in messages:
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            parts.append(message["content"])
    return "\n".join(parts)


def _strip_non_prose(text: str) -> str:
    text = _FENCE.sub(" ", text)
    text = _INLINE.sub(" ", text)
    text = _URL.sub(" ", text)
    return text


def detect_language(text: str) -> str:
    """Return en, hi, te, mixed, or unknown."""
    te = hi = en = 0
    for ch in _strip_non_prose(text):
        code = ord(ch)
        if 0x0C00 <= code <= 0x0C7F:
            if not 0x0C66 <= code <= 0x0C6F:
                te += 1
        elif 0x0900 <= code <= 0x097F:
            if not 0x0966 <= code <= 0x096F:
                hi += 1
        elif "A" <= ch <= "Z" or "a" <= ch <= "z":
            en += 1
    total = te + hi + en
    if total == 0:
        return "unknown"
    counts = {"te": te, "hi": hi, "en": en}
    label, count = max(counts.items(), key=lambda item: item[1])
    if count / total >= _DOMINANT:
        return label
    return "mixed"

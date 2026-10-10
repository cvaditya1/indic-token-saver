"""Mask spans that translation should copy through unchanged.

Order: fenced and inline code, URLs, currency amounts, conservative
dates, then standalone numbers. Person names are not detected.
"""

from __future__ import annotations

import re

_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE = re.compile(r"`[^`\n]*`")
_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_CURRENCY = re.compile(r"(?:₹|Rs\.?|INR)\s*\d[\d,]*(?:\.\d+)?", re.IGNORECASE)
_DATE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b"
    r"|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
)
_NUMBER = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")

_PATTERNS = (_FENCE, _INLINE, _URL, _CURRENCY, _DATE, _NUMBER)
_TOKEN = "\uE000\uE001"
_PLACEHOLDER = re.compile(r"<<P(\d+)>>")


def mask_spans(text: str) -> tuple[str, list[str]]:
    """Replace protected spans with <<P0>>, <<P1>>, ... in scan order."""
    spans: list[str] = []

    def _hold(match: re.Match[str]) -> str:
        spans.append(match.group(0))
        return _TOKEN

    masked = text
    for pattern in _PATTERNS:
        masked = pattern.sub(_hold, masked)
    for index in range(len(spans)):
        masked = masked.replace(_TOKEN, f"<<P{index}>>", 1)
    return masked, spans


def restore_spans(text: str, spans: list[str]) -> str:
    """Put original spans back. Exact placeholders only."""

    def _put(match: re.Match[str]) -> str:
        index = int(match.group(1))
        if 0 <= index < len(spans):
            return spans[index]
        return match.group(0)

    return _PLACEHOLDER.sub(_put, text)

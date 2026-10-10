"""Environment configuration. Does not read API keys into logs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """Set missing environment variables from a local .env file."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    groq_api_key: str
    usd_inr_rate: Decimal
    log_path: Path
    default_provider: str
    default_gemini_model: str
    default_groq_model: str
    log_prompt_hash: bool
    cache_path: Path

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> Settings:
        load_dotenv(dotenv_path or Path(".env"))
        rate_raw = os.environ.get("USD_INR_RATE", "96.64")
        try:
            rate = Decimal(rate_raw)
        except InvalidOperation as exc:
            raise ValueError(f"USD_INR_RATE is not a decimal: {rate_raw}") from exc
        provider = os.environ.get("DEFAULT_PROVIDER", "gemini").strip().lower()
        if provider not in {"gemini", "groq"}:
            raise ValueError("DEFAULT_PROVIDER must be gemini or groq")
        return cls(
            gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
            groq_api_key=os.environ.get("GROQ_API_KEY", ""),
            usd_inr_rate=rate,
            log_path=Path(os.environ.get("LOG_PATH", "logs/requests.jsonl")),
            default_provider=provider,
            default_gemini_model=os.environ.get(
                "DEFAULT_GEMINI_MODEL", "gemini-3.5-flash-lite"
            ),
            default_groq_model=os.environ.get(
                "DEFAULT_GROQ_MODEL", "openai/gpt-oss-20b"
            ),
            log_prompt_hash=os.environ.get("LOG_PROMPT_HASH", "0") == "1",
            cache_path=Path(
                os.environ.get("CACHE_PATH", "data/translation_cache.sqlite")
            ),
        )

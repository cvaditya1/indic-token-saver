"""SQLite cache of IndicTrans2 outputs. Keys include the masked source text."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

_CREATE = """
CREATE TABLE IF NOT EXISTS translation_cache (
    direction TEXT NOT NULL,
    source_lang TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    model_id TEXT NOT NULL,
    masked_text TEXT NOT NULL,
    output_text TEXT NOT NULL,
    PRIMARY KEY (direction, source_lang, target_lang, model_id, masked_text)
)
"""


class TranslationCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(_CREATE)
        self._conn.commit()

    def get(
        self,
        direction: str,
        source_lang: str,
        target_lang: str,
        model_id: str,
        masked_text: str,
    ) -> str | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT output_text FROM translation_cache
                WHERE direction = ? AND source_lang = ? AND target_lang = ?
                  AND model_id = ? AND masked_text = ?
                """,
                (direction, source_lang, target_lang, model_id, masked_text),
            ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def put(
        self,
        direction: str,
        source_lang: str,
        target_lang: str,
        model_id: str,
        masked_text: str,
        output_text: str,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO translation_cache (
                    direction, source_lang, target_lang, model_id,
                    masked_text, output_text
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(direction, source_lang, target_lang, model_id, masked_text)
                DO UPDATE SET output_text = excluded.output_text
                """,
                (
                    direction,
                    source_lang,
                    target_lang,
                    model_id,
                    masked_text,
                    output_text,
                ),
            )
            self._conn.commit()

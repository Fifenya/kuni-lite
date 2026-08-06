from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from llm.base import LLMBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS diary_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at REAL NOT NULL,
    -- "свежесть" записи для сортировки при консолидации: после каждого
    -- слияния запись получает новый id/created_at и снова считается "недавней"
    consolidated_from TEXT DEFAULT NULL
);
"""


@dataclass
class DiaryEntry:
    id: int
    chat_id: int
    text: str
    created_at: float
    score: float = 0.0


class Diary:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def add(self, chat_id: int, text: str, embedding: list[float]) -> int:
        blob = np.array(embedding, dtype=np.float32).tobytes()
        cur = self._conn.execute(
            "INSERT INTO diary_entries (chat_id, text, embedding, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, text, blob, time.time()),
        )
        self._conn.commit()
        return cur.lastrowid

    def _all_rows(self, chat_id: int | None = None):
        if chat_id is None:
            return self._conn.execute(
                "SELECT id, chat_id, text, embedding, created_at FROM diary_entries"
            ).fetchall()
        return self._conn.execute(
            "SELECT id, chat_id, text, embedding, created_at FROM diary_entries WHERE chat_id = ?",
            (chat_id,),
        ).fetchall()

    async def recall(
        self, backend: LLMBackend, query: str, *, chat_id: int | None = None, top_k: int = 6
    ) -> list[DiaryEntry]:
        """RAG-поиск: находит top_k наиболее релевантных записей дневника по
        косинусной близости эмбеддингов относительно текущего запроса."""
        rows = self._all_rows(chat_id)
        if not rows:
            return []

        query_vec = np.array(await backend.embed(query), dtype=np.float32)
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)

        scored: list[DiaryEntry] = []
        for row_id, row_chat_id, text, blob, created_at in rows:
            vec = np.frombuffer(blob, dtype=np.float32)
            vec_norm = vec / (np.linalg.norm(vec) + 1e-8)
            score = float(np.dot(query_norm, vec_norm))
            scored.append(DiaryEntry(row_id, row_chat_id, text, created_at, score))

        scored.sort(key=lambda e: e.score, reverse=True)
        return scored[:top_k]

    def delete(self, ids: list[int]) -> None:
        self._conn.executemany("DELETE FROM diary_entries WHERE id = ?", [(i,) for i in ids])
        self._conn.commit()

    def oldest_first_chunk(self, chunk_size: int, recent_bias: bool = True) -> list[DiaryEntry]:
        """Выбирает пачку записей для консолидации: с уклоном в сторону
        недавних, но иногда захватывает и старые (как описано в README Kuni)."""
        rows = self._conn.execute(
            "SELECT id, chat_id, text, embedding, created_at FROM diary_entries "
            "ORDER BY created_at DESC LIMIT ?",
            (chunk_size * 3,),
        ).fetchall()
        entries = [DiaryEntry(r[0], r[1], r[2], r[4]) for r in rows]
        if recent_bias:
            import random

            random.shuffle(entries)
        return entries[:chunk_size]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM diary_entries").fetchone()[0]

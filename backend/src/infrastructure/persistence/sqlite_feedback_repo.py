"""SQLite feedback repository. Async wrapper via asyncio.to_thread."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from src.application.ports.feedback_repository import FeedbackEntry, FeedbackRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id TEXT NOT NULL,
    trace_id TEXT,
    user_role TEXT NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT,
    final_answer_excerpt TEXT,
    participating_agents TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at DESC);
"""


class SqliteFeedbackRepo(FeedbackRepository):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript(SCHEMA)

    async def save(self, entry: FeedbackEntry) -> None:
        await asyncio.to_thread(self._save_sync, entry)

    def _save_sync(self, entry: FeedbackEntry) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO feedback (query_id, trace_id, user_role, rating, comment,
                                      final_answer_excerpt, participating_agents)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.query_id,
                    entry.trace_id,
                    entry.user_role,
                    entry.rating,
                    entry.comment,
                    entry.final_answer_excerpt,
                    json.dumps(list(entry.participating_agents)),
                ),
            )

    async def list_recent(self, limit: int = 50) -> list[FeedbackEntry]:
        return await asyncio.to_thread(self._list_sync, limit)

    def _list_sync(self, limit: int) -> list[FeedbackEntry]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT query_id, trace_id, user_role, rating, comment,
                       final_answer_excerpt, participating_agents
                FROM feedback ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            FeedbackEntry(
                query_id=r[0],
                trace_id=r[1],
                user_role=r[2],
                rating=r[3],
                comment=r[4],
                final_answer_excerpt=r[5] or "",
                participating_agents=tuple(json.loads(r[6] or "[]")),
            )
            for r in rows
        ]

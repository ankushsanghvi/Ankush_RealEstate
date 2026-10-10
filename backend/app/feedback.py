"""Feedback loop storage (SQLite, stdlib). Every pipeline response is logged
with its estimate so that feedback can be joined back to it; corrected values
become labelled cases that the evaluation runner picks up automatically."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path


class FeedbackStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS requests (request_id TEXT PRIMARY KEY, created_at REAL, query TEXT, estimate INTEGER, subject TEXT, verdict TEXT, engine TEXT, latency_ms INTEGER)")
            c.execute("CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT, created_at REAL, rating TEXT, corrected_value INTEGER, comment TEXT)")

    def _conn(self):
        return sqlite3.connect(self.path, check_same_thread=False)

    def log_request(self, request_id: str, query: str, estimate: int | None, subject: dict | None, verdict: str | None, engine: str, latency_ms: int) -> None:
        with self._lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO requests VALUES (?,?,?,?,?,?,?,?)", (request_id, time.time(), query, estimate, json.dumps(subject or {}), verdict, engine, latency_ms))

    def add_feedback(self, request_id: str, rating: str, corrected: int | None, comment: str | None) -> dict | None:
        """Store feedback against a logged request. Returns None (and stores nothing) when the
        request id is unknown, so the table never holds orphans that inflate the counts."""
        with self._lock, self._conn() as c:
            row = c.execute("SELECT query, estimate FROM requests WHERE request_id=?", (request_id,)).fetchone()
            if row is None:
                return None
            c.execute("INSERT INTO feedback (request_id, created_at, rating, corrected_value, comment) VALUES (?,?,?,?,?)", (request_id, time.time(), rating, corrected, comment))
        return {"linked": True, "query": row[0], "estimate": row[1]}

    def counts(self) -> dict:
        with self._conn() as c:
            pos = c.execute("SELECT COUNT(*) FROM feedback WHERE rating='up'").fetchone()[0]
            neg = c.execute("SELECT COUNT(*) FROM feedback WHERE rating='down'").fetchone()[0]
            cor = c.execute("SELECT COUNT(*) FROM feedback WHERE corrected_value IS NOT NULL").fetchone()[0]
        return {"positive": pos, "negative": neg, "corrected": cor}

    def corrected_cases(self) -> list[dict]:
        """Labelled cases contributed by humans — consumed by the eval runner."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT r.query, f.corrected_value, r.estimate FROM feedback f JOIN requests r ON r.request_id=f.request_id WHERE f.corrected_value IS NOT NULL ORDER BY f.created_at DESC LIMIT 200"
            ).fetchall()
        return [{"query": q, "expected_value": cv, "model_estimate": est} for q, cv, est in rows]

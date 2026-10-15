"""Typed SQLite knowledge and conversation-memory adapter.

SQLite uses WAL and a bounded busy timeout to allow readers alongside writers.
The store is local-first and never calls a model or network service.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class MemoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        return db

    def _init(self) -> None:
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS knowledge("
                "id TEXT PRIMARY KEY,title TEXT NOT NULL,content TEXT NOT NULL,"
                "kind TEXT NOT NULL DEFAULT 'note',tags TEXT NOT NULL DEFAULT '[]',"
                "source TEXT NOT NULL DEFAULT 'user',created_at REAL NOT NULL,"
                "updated_at REAL NOT NULL,pinned INTEGER NOT NULL DEFAULT 0)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_updated ON knowledge(updated_at DESC)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS conversation_archive("
                "id TEXT PRIMARY KEY,session_id TEXT NOT NULL,role TEXT NOT NULL,"
                "content TEXT NOT NULL,created_at REAL NOT NULL,metadata TEXT NOT NULL DEFAULT '{}')"
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_archive_session ON conversation_archive(session_id,created_at)")

    @staticmethod
    def _item(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["tags"] = json.loads(item.get("tags") or "[]")
        item["pinned"] = bool(item.get("pinned", 0))
        return item

    def add(
        self, title: str, content: str, *, kind: str = "note",
        tags: list[str] | None = None, source: str = "user", pinned: bool = False,
    ) -> dict[str, Any]:
        title, content = title.strip(), content.strip()
        if not title or not content:
            raise ValueError("Title and content are required.")
        if len(title) > 240 or len(content) > 20000:
            raise ValueError("Title or content exceeds limits.")
        now, ident = time.time(), uuid.uuid4().hex
        with self._connect() as db:
            db.execute(
                "INSERT INTO knowledge VALUES(?,?,?,?,?,?,?,?,?)",
                (ident, title, content, kind, json.dumps(list(tags or [])[:30]), source, now, now, int(pinned)),
            )
        item = self.get(ident)
        assert item is not None
        return item

    def get(self, ident: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM knowledge WHERE id=?", (ident,)).fetchone()
        return self._item(row) if row else None

    def list(self, limit: int = 100, kind: str | None = None) -> list[dict[str, Any]]:
        bounded = max(1, min(limit, 500))
        with self._connect() as db:
            sql = "SELECT * FROM knowledge" + (" WHERE kind=?" if kind else "") + " ORDER BY pinned DESC,updated_at DESC LIMIT ?"
            rows = db.execute(sql, (kind, bounded) if kind else (bounded,)).fetchall()
        return [self._item(row) for row in rows]

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        terms = [term.casefold() for term in query.split() if len(term) > 1]
        if not terms:
            return []
        scored: list[tuple[int, dict[str, Any]]] = []
        for item in self.list(500):
            title = item["title"].casefold()
            body = item["content"].casefold()
            tags = " ".join(item["tags"]).casefold()
            score = sum((4 if term in title else 0) + (3 if term in tags else 0) + (1 if term in body else 0) for term in terms)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: (pair[0], pair[1]["pinned"], pair[1]["updated_at"]), reverse=True)
        return [{"score": score, **item} for score, item in scored[:max(1, min(limit, 50))]]

    def delete(self, ident: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM knowledge WHERE id=?", (ident,))
        return cursor.rowcount > 0

    def archive_message(
        self, session_id: str, role: str, content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        content = str(content).strip()
        if content:
            with self._connect() as db:
                db.execute(
                    "INSERT INTO conversation_archive VALUES(?,?,?,?,?,?)",
                    (uuid.uuid4().hex, session_id, role, content[:30000], time.time(), json.dumps(metadata or {})),
                )

    def archive_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        terms = [term.casefold() for term in query.split() if len(term) > 1]
        if not terms:
            return []
        with self._connect() as db:
            rows = db.execute("SELECT * FROM conversation_archive ORDER BY created_at DESC LIMIT 2000").fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            score = sum(row["content"].casefold().count(term) for term in terms)
            if score:
                results.append({
                    "score": score, "id": row["id"], "session_id": row["session_id"],
                    "role": row["role"], "content": row["content"], "created_at": row["created_at"],
                })
        return sorted(results, key=lambda item: (item["score"], item["created_at"]), reverse=True)[:max(1, min(limit, 50))]

"""Persistent, approval-aware task lifecycle ledger.

The ledger records plans and links existing Command Control operations. It never
executes tools. Execution status is read from the authoritative command queue.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from application.learning import ALGORITHMS, TASK_TYPES

_MAX_TASKS = 2000


class TaskLifecycleStore:
    """Bounded SQLite ledger for plan -> approval -> execution -> verification -> review."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS task_runs (
                    id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    operation_id TEXT,
                    execution_status TEXT,
                    verification_json TEXT,
                    review_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_created ON task_runs(created_at DESC)")
            db.commit()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        return db

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["steps"] = json.loads(item.pop("steps_json"))
        verification_json = item.pop("verification_json")
        review_json = item.pop("review_json")
        item["verification"] = json.loads(verification_json) if verification_json else None
        item["review"] = json.loads(review_json) if review_json else None
        return item

    def create(self, *, goal: str, task_type: str, algorithm: str, risk: str,
               steps: list[str]) -> dict[str, Any]:
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 4000:
            raise ValueError("goal must be 1-4000 characters")
        if not isinstance(task_type, str) or task_type not in TASK_TYPES:
            raise ValueError("task_type is invalid")
        if not isinstance(algorithm, str) or algorithm not in ALGORITHMS:
            raise ValueError("algorithm is invalid")
        if risk not in {"read", "low", "medium", "high", "critical"}:
            raise ValueError("risk is invalid")
        if not isinstance(steps, list) or not 1 <= len(steps) <= 30 or any(
            not isinstance(s, str) or not s.strip() or len(s) > 500 for s in steps
        ):
            raise ValueError("steps must contain 1-30 non-empty strings of at most 500 characters")
        ident, now = uuid.uuid4().hex, time.time()
        with self._connect() as db:
            db.execute(
                "INSERT INTO task_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (ident, goal.strip(), task_type, algorithm, risk, json.dumps(steps),
                 "planned", None, None, None, None, now, now),
            )
            db.execute(
                "DELETE FROM task_runs WHERE id NOT IN (SELECT id FROM task_runs ORDER BY created_at DESC LIMIT ?)",
                (_MAX_TASKS,),
            )
            db.commit()
            row = db.execute("SELECT * FROM task_runs WHERE id=?", (ident,)).fetchone()
        return self._decode(row)

    def get(self, ident: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM task_runs WHERE id=?", (ident,)).fetchone()
        return self._decode(row) if row else None

    def list(self, limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self._connect() as db:
            if status:
                rows = db.execute("SELECT * FROM task_runs WHERE status=? ORDER BY created_at DESC LIMIT ?",
                                  (status, limit)).fetchall()
            else:
                rows = db.execute("SELECT * FROM task_runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._decode(row) for row in rows]

    def link_operation(self, ident: str, operation: dict[str, Any]) -> dict[str, Any]:
        if operation.get("status") not in {"pending", "approved", "executing", "executed", "failed", "rejected", "expired"}:
            raise ValueError("operation has an unsupported status")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM task_runs WHERE id=?", (ident,)).fetchone()
            if not row:
                db.rollback()
                raise KeyError("task not found")
            if row["status"] != "planned" or row["operation_id"]:
                db.rollback()
                raise ValueError("an operation can only be linked once to a planned task")
            status = "awaiting_approval" if operation["status"] == "pending" else self._status_for_operation(operation["status"])
            db.execute("UPDATE task_runs SET operation_id=?,execution_status=?,status=?,updated_at=? WHERE id=?",
                       (operation["id"], operation["status"], status, time.time(), ident))
            db.commit()
        result = self.get(ident)
        assert result is not None
        return result

    @staticmethod
    def _status_for_operation(operation_status: str) -> str:
        return {
            "pending": "awaiting_approval", "approved": "approved",
            "executing": "executing", "executed": "executed",
            "failed": "failed", "rejected": "rejected", "expired": "expired",
        }[operation_status]

    def sync_operation(self, ident: str, operation: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM task_runs WHERE id=?", (ident,)).fetchone()
            if not row:
                db.rollback()
                raise KeyError("task not found")
            if row["operation_id"] != operation.get("id"):
                db.rollback()
                raise ValueError("operation does not match the task's linked operation")
            if row["status"] in {"verified", "reviewed"} or row["verification_json"] is not None:
                db.commit()
                return self._decode(row)
            status = self._status_for_operation(operation["status"])
            db.execute("UPDATE task_runs SET execution_status=?,status=?,updated_at=? WHERE id=?",
                       (operation["status"], status, time.time(), ident))
            db.commit()
        result = self.get(ident)
        assert result is not None
        return result

    def verify(self, ident: str, *, passed: bool, evidence: str, verifier: str) -> dict[str, Any]:
        if not isinstance(passed, bool):
            raise ValueError("passed must be boolean")
        if not isinstance(evidence, str) or not evidence.strip() or len(evidence) > 4000:
            raise ValueError("evidence must be 1-4000 characters")
        if not isinstance(verifier, str) or not verifier.strip() or len(verifier) > 100:
            raise ValueError("verifier must be 1-100 characters")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM task_runs WHERE id=?", (ident,)).fetchone()
            if not row:
                db.rollback()
                raise KeyError("task not found")
            if row["status"] != "executed" or row["execution_status"] != "executed":
                db.rollback()
                raise ValueError("verification requires a linked operation recorded as executed")
            verification = {"passed": passed, "evidence": evidence.strip(),
                            "verifier": verifier.strip(), "verified_at": time.time()}
            status = "verified" if passed else "failed"
            db.execute("UPDATE task_runs SET verification_json=?,status=?,updated_at=? WHERE id=?",
                       (json.dumps(verification, ensure_ascii=False), status, time.time(), ident))
            db.commit()
        result = self.get(ident)
        assert result is not None
        return result

    def review(self, ident: str, *, outcome: str, rating: int, reviewer: str) -> dict[str, Any]:
        if outcome not in {"success", "partial", "failure"}:
            raise ValueError("outcome must be success, partial, or failure")
        if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5:
            raise ValueError("rating must be an integer from 1 to 5")
        if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 100:
            raise ValueError("reviewer must be 1-100 characters")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM task_runs WHERE id=?", (ident,)).fetchone()
            if not row:
                db.rollback()
                raise KeyError("task not found")
            if row["status"] != "verified" or not row["verification_json"]:
                db.rollback()
                raise ValueError("only independently verified tasks can enter review")
            verification = json.loads(row["verification_json"])
            if verification.get("passed") is not True:
                db.rollback()
                raise ValueError("verification must pass before learning review")
            review = {"outcome": outcome, "rating": rating, "reviewer": reviewer.strip(),
                      "reviewed_at": time.time(), "verified": True}
            db.execute("UPDATE task_runs SET review_json=?,status='reviewed',updated_at=? WHERE id=?",
                       (json.dumps(review, ensure_ascii=False), time.time(), ident))
            db.commit()
        result = self.get(ident)
        assert result is not None
        return result

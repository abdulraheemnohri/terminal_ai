"""Bounded, proposal-only recovery guidance for tracked task failures."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

MAX_PROPOSALS_PER_TASK = 3
MAX_PROPOSALS_TOTAL = 5000
FAILURE_CATEGORIES = {
    "timeout", "transient_network", "rate_limit", "missing_dependency",
    "validation", "permission", "destructive", "unknown",
}
_RETRYABLE = {"timeout", "transient_network", "rate_limit"}
_CHANGE_REQUIRED = {"missing_dependency", "validation"}
_BLOCKED = {"permission", "destructive", "unknown"}


class RecoveryProposalStore:
    """Store bounded recovery proposals; never runs or dispatches an operation."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS recovery_proposals (
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL, attempt INTEGER NOT NULL,
                failure_category TEXT NOT NULL, error_summary TEXT NOT NULL,
                recovery_json TEXT NOT NULL, retry_policy TEXT NOT NULL,
                status TEXT NOT NULL, reviewer TEXT, review_note TEXT,
                new_operation_id TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL
            )""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(recovery_proposals)").fetchall()}
            if "new_operation_id" not in columns:
                db.execute("ALTER TABLE recovery_proposals ADD COLUMN new_operation_id TEXT")
            db.execute("CREATE INDEX IF NOT EXISTS idx_recovery_task_created ON recovery_proposals(task_id, created_at DESC)")
            db.commit()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        return db

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["recovery_steps"] = json.loads(result.pop("recovery_json"))
        result["may_retry_after_review"] = result["retry_policy"] == "retryable_after_human_review"
        result["execution_started"] = False
        return result

    def list_for_task(self, task_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM recovery_proposals WHERE task_id=? ORDER BY attempt ASC",
                (task_id,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def propose(self, *, task_id: str, failure_category: str, error_summary: str) -> dict[str, Any]:
        if not isinstance(task_id, str) or not task_id or len(task_id) > 100:
            raise ValueError("task_id is invalid")
        if not isinstance(failure_category, str) or failure_category not in FAILURE_CATEGORIES:
            raise ValueError("failure_category is invalid")
        if not isinstance(error_summary, str) or not error_summary.strip() or len(error_summary) > 500:
            raise ValueError("error_summary must be 1-500 characters and must not contain secrets")
        if failure_category in _RETRYABLE:
            policy = "retryable_after_human_review"
            steps = [
                "Inspect the recorded failure and confirm no partial side effect occurred.",
                "Check whether the transient condition has cleared; do not repeat a non-idempotent action blindly.",
                "If still appropriate, create a new Command Control operation with exact arguments and obtain fresh human approval.",
                "Execute the new operation only through the existing approved dispatcher, then independently verify its result.",
            ]
        elif failure_category in _CHANGE_REQUIRED:
            policy = "requires_change_and_fresh_approval"
            steps = [
                "Diagnose and correct the stated validation or dependency problem without changing the prior operation record.",
                "Review the revised plan and exact arguments.",
                "Create a new Command Control operation and obtain fresh human approval before any execution.",
                "Independently verify the outcome; do not learn from an unverified attempt.",
            ]
        else:
            policy = "no_retry_recommended"
            steps = [
                "Do not retry automatically or reuse the prior approval.",
                "Have an operator inspect the permission, destructive-risk, or unknown failure and its potential partial effects.",
                "Resolve the underlying safety or authorization issue through the normal policy process.",
                "If a different operation is justified, create a new operation with exact arguments and fresh human approval.",
            ]
        ident, now = uuid.uuid4().hex, time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT COUNT(*) FROM recovery_proposals WHERE task_id=?", (task_id,)).fetchone()[0]
            if count >= MAX_PROPOSALS_PER_TASK:
                db.rollback()
                raise ValueError("recovery proposal limit reached for this task (maximum 3)")
            db.execute(
                """INSERT INTO recovery_proposals
                (id, task_id, attempt, failure_category, error_summary, recovery_json,
                 retry_policy, status, reviewer, review_note, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ident, task_id, count + 1, failure_category, error_summary.strip(),
                 json.dumps(steps), policy, "proposed", None, None, now, now),
            )
            db.execute(
                "DELETE FROM recovery_proposals WHERE id NOT IN (SELECT id FROM recovery_proposals ORDER BY created_at DESC LIMIT ?)",
                (MAX_PROPOSALS_TOTAL,),
            )
            db.commit()
            row = db.execute("SELECT * FROM recovery_proposals WHERE id=?", (ident,)).fetchone()
        assert row is not None
        return self._decode(row)

    def prepare_operation_queue(self, *, task_id: str, proposal_id: str) -> dict[str, Any]:
        """Atomically reserve one fresh operation queue attempt for an approved proposal."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM recovery_proposals WHERE id=? AND task_id=?",
                             (proposal_id, task_id)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError("recovery proposal not found")
            if row["status"] != "approved_for_replanning":
                db.rollback()
                raise ValueError("proposal must be approved for replanning before creating an operation")
            updated = db.execute(
                "UPDATE recovery_proposals SET status='queueing', updated_at=? WHERE id=? AND status='approved_for_replanning'",
                (time.time(), proposal_id),
            )
            if updated.rowcount != 1:
                db.rollback()
                raise ValueError("operation queue is already being created for this proposal")
            db.commit()
            row = db.execute("SELECT * FROM recovery_proposals WHERE id=?", (proposal_id,)).fetchone()
        assert row is not None
        return self._decode(row)

    def attach_new_operation(self, *, task_id: str, proposal_id: str, operation_id: str) -> dict[str, Any]:
        if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 100:
            raise ValueError("operation_id is invalid")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM recovery_proposals WHERE id=? AND task_id=?",
                             (proposal_id, task_id)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError("recovery proposal not found")
            if row["status"] != "queueing" or row["new_operation_id"]:
                db.rollback()
                raise ValueError("proposal is not awaiting a new operation link")
            db.execute("UPDATE recovery_proposals SET status='operation_queued', new_operation_id=?, updated_at=? WHERE id=?",
                       (operation_id, time.time(), proposal_id))
            db.commit()
            updated = db.execute("SELECT * FROM recovery_proposals WHERE id=?", (proposal_id,)).fetchone()
        assert updated is not None
        return self._decode(updated)

    def release_operation_queue(self, *, task_id: str, proposal_id: str) -> None:
        """Allow a safe retry of queue creation only when queueing itself failed."""
        with self._connect() as db:
            db.execute(
                "UPDATE recovery_proposals SET status='approved_for_replanning', updated_at=? WHERE id=? AND task_id=? AND status='queueing' AND new_operation_id IS NULL",
                (time.time(), proposal_id, task_id),
            )
            db.commit()

    def review(self, *, task_id: str, proposal_id: str, decision: str,
               reviewer: str, note: str = "") -> dict[str, Any]:
        if not isinstance(decision, str) or decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")
        if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 100:
            raise ValueError("reviewer must be 1-100 characters")
        if not isinstance(note, str) or len(note) > 500:
            raise ValueError("review note must be at most 500 characters")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM recovery_proposals WHERE id=? AND task_id=?",
                             (proposal_id, task_id)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError("recovery proposal not found")
            if row["status"] != "proposed":
                db.rollback()
                raise ValueError("recovery proposal has already been reviewed")
            if decision == "approve" and row["retry_policy"] == "no_retry_recommended":
                db.rollback()
                raise ValueError("this failure category is not eligible for retry approval")
            status = "approved_for_replanning" if decision == "approve" else "rejected"
            db.execute("UPDATE recovery_proposals SET status=?, reviewer=?, review_note=?, updated_at=? WHERE id=?",
                       (status, reviewer.strip(), note.strip(), time.time(), proposal_id))
            db.commit()
            updated = db.execute("SELECT * FROM recovery_proposals WHERE id=?", (proposal_id,)).fetchone()
        assert updated is not None
        return self._decode(updated)

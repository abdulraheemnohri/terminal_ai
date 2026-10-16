"""Durable queue for bounded autonomy decisions; it never runs arbitrary tools."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable

_ALLOWED_ACTIONS = {"workspace_overview", "learning_summary", "world_model_summary", "plan_task"}
_MAX_ATTEMPTS = 2
_MAX_JOBS = 1000


class AutonomyJobQueue:
    """SQLite-backed resumable queue with bounded retries and cooperative cancellation."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS autonomy_jobs (
                    id TEXT PRIMARY KEY, payload_json TEXT NOT NULL,
                    status TEXT NOT NULL, progress TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL,
                    result_json TEXT, error TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL, started_at REAL,
                    finished_at REAL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_autonomy_jobs_status_created ON autonomy_jobs(status, created_at)")
            # A process may have exited while a job was running. Retry once on startup;
            # a second interrupted attempt is marked failed instead of looping forever.
            db.execute("UPDATE autonomy_jobs SET status='queued', progress='Recovered after process restart', updated_at=? WHERE status='running' AND attempts < max_attempts", (time.time(),))
            db.execute("UPDATE autonomy_jobs SET status='failed', error='Worker stopped during final allowed attempt', progress='Failed during recovery', finished_at=?, updated_at=? WHERE status='running' AND attempts >= max_attempts", (time.time(), time.time()))
            db.commit()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        return db

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        raw_result = result.pop("result_json")
        result["result"] = json.loads(raw_result) if raw_result else None
        result["cancel_requested"] = bool(result["cancel_requested"])
        return result

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("job payload must be an object")
        allowed = {"goal", "action", "complexity", "risk", "has_external_side_effects"}
        if set(payload) - allowed:
            raise ValueError("job contains unsupported fields")
        goal = payload.get("goal")
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 4000:
            raise ValueError("goal must be a non-empty string of at most 4000 characters")
        action = payload.get("action")
        if action is not None and (not isinstance(action, str) or action not in _ALLOWED_ACTIONS):
            raise ValueError("action must be one of the registered safe actions")
        complexity = payload.get("complexity", 1)
        if isinstance(complexity, bool) or not isinstance(complexity, int) or not 1 <= complexity <= 10:
            raise ValueError("complexity must be an integer from 1 to 10")
        risk = payload.get("risk", "read")
        if not isinstance(risk, str) or risk not in {"read", "low", "medium", "high", "critical"}:
            raise ValueError("invalid risk level")
        side_effects = payload.get("has_external_side_effects", False)
        if not isinstance(side_effects, bool):
            raise ValueError("has_external_side_effects must be boolean")
        normalized = {"goal": goal.strip(), "complexity": complexity, "risk": risk,
                      "has_external_side_effects": side_effects}
        if action is not None:
            normalized["action"] = action
        ident, now = uuid.uuid4().hex, time.time()
        with self._connect() as db:
            count = db.execute("SELECT COUNT(*) FROM autonomy_jobs WHERE status IN ('queued','running')").fetchone()[0]
            if count >= 100:
                raise ValueError("autonomy queue is full (maximum 100 pending/running jobs)")
            db.execute("INSERT INTO autonomy_jobs(id,payload_json,status,progress,attempts,max_attempts,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                       (ident, json.dumps(normalized, separators=(",", ":")), "queued", "Waiting for worker", 0, _MAX_ATTEMPTS, now, now))
            db.execute("DELETE FROM autonomy_jobs WHERE id IN (SELECT id FROM autonomy_jobs WHERE status IN ('completed','failed','cancelled') ORDER BY updated_at DESC LIMIT -1 OFFSET ?)", (_MAX_JOBS,))
            db.commit()
        return self.get(ident)  # type: ignore[return-value]

    def claim(self) -> dict[str, Any] | None:
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM autonomy_jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if row is None:
                db.commit()
                return None
            db.execute("UPDATE autonomy_jobs SET status='running', attempts=attempts+1, progress='Starting bounded decision cycle', started_at=?, updated_at=? WHERE id=? AND status='queued'",
                       (now, now, row["id"]))
            db.commit()
        return self.get(row["id"])

    def update_progress(self, ident: str, progress: str) -> bool:
        with self._connect() as db:
            cur = db.execute("UPDATE autonomy_jobs SET progress=?,updated_at=? WHERE id=? AND status='running'",
                             (str(progress)[:300], time.time(), ident))
            db.commit()
            return cur.rowcount > 0

    def finish(self, ident: str, result: dict[str, Any]) -> bool:
        now = time.time()
        with self._connect() as db:
            row = db.execute("SELECT cancel_requested FROM autonomy_jobs WHERE id=?", (ident,)).fetchone()
            if not row:
                return False
            status = "cancelled" if row["cancel_requested"] else "completed"
            progress = "Cancelled after safe decision cycle" if status == "cancelled" else "Decision cycle completed"
            cur = db.execute("UPDATE autonomy_jobs SET status=?,progress=?,result_json=?,error=NULL,finished_at=?,updated_at=? WHERE id=? AND status='running'",
                             (status, progress, json.dumps(result, ensure_ascii=False, default=str), now, now, ident))
            db.commit()
            return cur.rowcount > 0

    def fail(self, ident: str, error: str) -> str:
        now = time.time()
        with self._connect() as db:
            row = db.execute("SELECT attempts,max_attempts,cancel_requested FROM autonomy_jobs WHERE id=?", (ident,)).fetchone()
            if row is None:
                return "missing"
            if row["cancel_requested"]:
                status, progress = "cancelled", "Cancelled"
            elif row["attempts"] < row["max_attempts"]:
                status, progress = "queued", "Retry queued after a recoverable worker error"
            else:
                status, progress = "failed", "Retry limit reached"
            finished = now if status in {"cancelled", "failed"} else None
            db.execute("UPDATE autonomy_jobs SET status=?,progress=?,error=?,finished_at=?,updated_at=? WHERE id=?",
                       (status, progress, str(error)[:500], finished, now, ident))
            db.commit()
            return status

    def cancel(self, ident: str) -> dict[str, Any] | None:
        now = time.time()
        with self._connect() as db:
            row = db.execute("SELECT status FROM autonomy_jobs WHERE id=?", (ident,)).fetchone()
            if not row:
                return None
            if row["status"] == "queued":
                db.execute("UPDATE autonomy_jobs SET status='cancelled',cancel_requested=1,progress='Cancelled before start',finished_at=?,updated_at=? WHERE id=?",
                           (now, now, ident))
            elif row["status"] == "running":
                db.execute("UPDATE autonomy_jobs SET cancel_requested=1,progress='Cancellation requested; waiting for current safe action to return',updated_at=? WHERE id=?",
                           (now, ident))
            db.commit()
        return self.get(ident)

    def get(self, ident: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM autonomy_jobs WHERE id=?", (ident,)).fetchone()
        return self._decode(row)

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        with self._connect() as db:
            rows = db.execute("SELECT * FROM autonomy_jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._decode(row) for row in rows]  # type: ignore[misc]

    def status(self) -> dict[str, Any]:
        with self._connect() as db:
            rows = db.execute("SELECT status,COUNT(*) AS count FROM autonomy_jobs GROUP BY status").fetchall()
        return {"by_status": {row["status"]: row["count"] for row in rows}, "max_attempts": _MAX_ATTEMPTS}


class AutonomyJobWorker:
    """Single-process async poller. Only invokes AutonomyEngine's bounded safe decision cycle."""

    def __init__(self, queue: AutonomyJobQueue, run_decision: Callable[..., dict[str, Any]],
                 audit: Callable[..., Any], poll_seconds: float = 1.0) -> None:
        self.queue, self.run_decision, self.audit = queue, run_decision, audit
        self.poll_seconds = max(0.2, min(float(poll_seconds), 10.0))
        self._task: asyncio.Task | None = None
        self._stopping = False

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping = False
            self._task = asyncio.create_task(self._loop(), name="terminal-ai-autonomy-worker")

    async def stop(self) -> None:
        self._stopping = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while not self._stopping:
            job = await asyncio.to_thread(self.queue.claim)
            if job is None:
                await asyncio.sleep(self.poll_seconds)
                continue
            ident = job["id"]
            try:
                self.queue.update_progress(ident, "Validating request and selecting bounded action")
                payload = job["payload"]
                result = await asyncio.to_thread(self.run_decision, **payload)
                self.queue.finish(ident, result)
                self.audit("autonomy", "autonomy.job.completed", ident,
                           {"attempts": job["attempts"], "status": self.queue.get(ident)["status"]})
            except asyncio.CancelledError:
                # A shutdown does not erase the job; restart recovery requeues it within the retry bound.
                raise
            except Exception as exc:
                status = self.queue.fail(ident, type(exc).__name__ + ": " + str(exc))
                self.audit("autonomy", "autonomy.job." + status, ident,
                           {"attempts": job["attempts"], "reason": type(exc).__name__})

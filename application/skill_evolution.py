"""Human-reviewed workflow for proposing safe, non-executable skill improvements.

Skill proposals are plain procedure text. Validation is structural/static only;
this module never imports, evaluates, or executes proposal content.
"""
from __future__ import annotations

from contextlib import closing
import json
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from terminal_ai_runtime import init_sqlite

_STATUSES = {"proposed", "validated", "approved", "rejected", "promoted"}
_WORD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{1,79}$")
_MAX_PROPOSALS = 1000
_MAX_STEPS = 20
_MAX_TEXT = 2000


class SkillEvolutionStore:
    """Bounded SQLite proposal queue with explicit review and promotion states."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with closing(init_sqlite(self.path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_proposals (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    evidence_summary TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('proposed','validated','approved','rejected','promoted')),
                    review_note TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_proposals_status ON skill_proposals(status, created_at)")
            conn.commit()

    @staticmethod
    def validate_fields(name: Any, task_type: Any, rationale: Any, steps: Any,
                        evidence_summary: Any) -> list[str]:
        errors: list[str] = []
        if not isinstance(name, str) or not _WORD.fullmatch(name.strip()):
            errors.append("name must be 2-80 safe letters, digits, spaces, dots, underscores, or hyphens")
        if not isinstance(task_type, str) or task_type not in {"debugging", "software_change", "research", "browser_work", "planning", "writing", "general"}:
            errors.append("unsupported task_type")
        for field, value in (("rationale", rationale), ("evidence_summary", evidence_summary)):
            if not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
                errors.append(f"{field} must contain 1-{_MAX_TEXT} characters")
        if not isinstance(steps, list) or not 1 <= len(steps) <= _MAX_STEPS:
            errors.append(f"steps must contain 1-{_MAX_STEPS} plain-text items")
        elif any(not isinstance(step, str) or not step.strip() or len(step) > 500 for step in steps):
            errors.append("each step must be plain text of 1-500 characters")
        if isinstance(steps, list) and sum(len(s) for s in steps if isinstance(s, str)) > 8000:
            errors.append("combined step text exceeds 8000 characters")
        # This is a deliberately small structural check, not a sandbox/security scanner.
        if isinstance(steps, list) and any(
            isinstance(step, str) and re.search(r"(^|\s)(exec|eval|subprocess|os\.system)\s*\(", step, re.I)
            for step in steps
        ):
            errors.append("executable-code patterns are not allowed in skill procedure text")
        return errors

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        return {
            "id": row[0], "name": row[1], "task_type": row[2], "rationale": row[3],
            "steps": json.loads(row[4]), "evidence_summary": row[5], "status": row[6],
            "review_note": row[7], "created_at": row[8], "updated_at": row[9],
            "executable": False,
        }

    def create(self, *, name: Any, task_type: Any, rationale: Any, steps: Any,
               evidence_summary: Any) -> dict[str, Any]:
        errors = self.validate_fields(name, task_type, rationale, steps, evidence_summary)
        if errors:
            raise ValueError("; ".join(errors))
        now = time.time()
        ident = uuid.uuid4().hex
        values = (ident, name.strip(), task_type, rationale.strip(), json.dumps([s.strip() for s in steps]),
                  evidence_summary.strip(), "proposed", "", now, now)
        with self._lock, closing(init_sqlite(self.path)) as conn:
            conn.execute("""
                INSERT INTO skill_proposals(id,name,task_type,rationale,steps_json,evidence_summary,status,review_note,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)
            """, values)
            conn.execute("DELETE FROM skill_proposals WHERE id NOT IN (SELECT id FROM skill_proposals ORDER BY created_at DESC LIMIT ?)", (_MAX_PROPOSALS,))
            conn.commit()
        return self.get(ident)  # type: ignore[return-value]

    def get(self, ident: str) -> dict[str, Any] | None:
        with self._lock, closing(init_sqlite(self.path)) as conn:
            row = conn.execute("SELECT id,name,task_type,rationale,steps_json,evidence_summary,status,review_note,created_at,updated_at FROM skill_proposals WHERE id=?", (ident,)).fetchone()
        return self._row(row) if row else None

    def list(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if status is not None and status not in _STATUSES:
            raise ValueError("unsupported status")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        with self._lock, closing(init_sqlite(self.path)) as conn:
            if status:
                rows = conn.execute("SELECT id,name,task_type,rationale,steps_json,evidence_summary,status,review_note,created_at,updated_at FROM skill_proposals WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, limit)).fetchall()
            else:
                rows = conn.execute("SELECT id,name,task_type,rationale,steps_json,evidence_summary,status,review_note,created_at,updated_at FROM skill_proposals ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._row(row) for row in rows]

    def transition(self, ident: str, action: str, note: str = "") -> dict[str, Any]:
        if not isinstance(note, str) or len(note) > 500:
            raise ValueError("review note must be at most 500 characters")
        transitions = {
            ("proposed", "validate"): "validated",
            ("validated", "approve"): "approved",
            ("proposed", "reject"): "rejected",
            ("validated", "reject"): "rejected",
            ("approved", "reject"): "rejected",
            ("approved", "promote"): "promoted",
        }
        with self._lock, closing(init_sqlite(self.path)) as conn:
            row = conn.execute("SELECT status FROM skill_proposals WHERE id=?", (ident,)).fetchone()
            if not row:
                raise KeyError("proposal not found")
            next_status = transitions.get((row[0], action))
            if not next_status:
                raise ValueError(f"cannot {action} a proposal in {row[0]} state")
            now = time.time()
            conn.execute("UPDATE skill_proposals SET status=?, review_note=?, updated_at=? WHERE id=? AND status=?",
                         (next_status, note.strip(), now, ident, row[0]))
            conn.commit()
        item = self.get(ident)
        assert item is not None
        return item

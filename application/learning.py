"""Persistent, bounded outcome memory for improving workflow recommendations.

Only coarse, explicitly verified outcomes are stored. This data never grants
permissions, executes tools, or changes the approval policy.
"""
from __future__ import annotations

from contextlib import closing
import threading
import time
from pathlib import Path
from typing import Any

from terminal_ai_runtime import init_sqlite

TASK_TYPES = {"debugging", "software_change", "research", "browser_work", "planning", "writing", "general"}
ALGORITHMS = {
    "evidence-first", "decompose-and-verify", "test-driven-loop",
    "observe-act-verify", "direct-verify",
}
OUTCOMES = {"success", "partial", "failure"}
_MAX_RECORDS = 5000


class LearningStore:
    """SQLite store for reviewed outcomes and conservative strategy suggestions."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with closing(init_sqlite(self.path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    verified INTEGER NOT NULL CHECK (verified = 1),
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_outcomes_family_algorithm ON task_outcomes(task_type, algorithm)")
            conn.commit()

    @staticmethod
    def _validate(task_type: Any, algorithm: Any, outcome: Any, rating: Any, verified: Any) -> None:
        if not isinstance(task_type, str) or task_type not in TASK_TYPES:
            raise ValueError("unsupported task_type")
        if not isinstance(algorithm, str) or algorithm not in ALGORITHMS:
            raise ValueError("unsupported algorithm")
        if not isinstance(outcome, str) or outcome not in OUTCOMES:
            raise ValueError("outcome must be success, partial, or failure")
        if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5:
            raise ValueError("rating must be an integer from 1 to 5")
        if verified is not True:
            raise ValueError("outcome must be explicitly verified before it can be learned")

    def record(self, *, task_type: str, algorithm: str, outcome: str,
               rating: int, verified: bool, source_ref: str | None = None) -> dict[str, Any]:
        self._validate(task_type, algorithm, outcome, rating, verified)
        if source_ref is not None and (not isinstance(source_ref, str) or not source_ref.strip() or len(source_ref) > 200):
            raise ValueError("source_ref must be 1-200 characters")
        now = time.time()
        with self._lock, closing(init_sqlite(self.path)) as conn:
            if source_ref:
                existing = conn.execute("SELECT * FROM task_outcomes WHERE source_ref=?", (source_ref,)).fetchone()
                if existing is not None:
                    if (existing["task_type"], existing["algorithm"], existing["outcome"], existing["rating"]) != (task_type, algorithm, outcome, rating):
                        raise ValueError("source_ref was already used for a different reviewed outcome")
                    return {"id": existing["id"], "task_type": existing["task_type"],
                            "algorithm": existing["algorithm"], "outcome": existing["outcome"],
                            "rating": existing["rating"], "verified": True,
                            "created_at": existing["created_at"], "source_ref": source_ref,
                            "idempotent_replay": True}
            conn.execute(
                "INSERT INTO task_outcomes(task_type, algorithm, outcome, rating, verified, created_at, source_ref) VALUES(?,?,?,?,1,?,?)",
                (task_type, algorithm, outcome, rating, now, source_ref),
            )
            conn.execute(
                "DELETE FROM task_outcomes WHERE id NOT IN (SELECT id FROM task_outcomes ORDER BY id DESC LIMIT ?)",
                (_MAX_RECORDS,),
            )
            conn.commit()
            row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"id": row_id, "task_type": task_type, "algorithm": algorithm,
                "outcome": outcome, "rating": rating, "verified": True, "created_at": now,
                "source_ref": source_ref, "idempotent_replay": False}

    def summary(self) -> dict[str, Any]:
        with self._lock, closing(init_sqlite(self.path)) as conn:
            rows = conn.execute("""
                SELECT task_type, algorithm, COUNT(*),
                    AVG(CASE outcome WHEN 'success' THEN 1.0 WHEN 'partial' THEN 0.5 ELSE 0.0 END),
                    AVG(rating), MAX(created_at)
                FROM task_outcomes GROUP BY task_type, algorithm
                ORDER BY task_type, algorithm
            """).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM task_outcomes").fetchone()[0]
        groups = [
            {"task_type": r[0], "algorithm": r[1], "samples": r[2],
             "success_score": round(float(r[3]), 3), "average_rating": round(float(r[4]), 2),
             "last_observed_at": r[5]}
            for r in rows
        ]
        return {"count": total, "max_records": _MAX_RECORDS, "groups": groups,
                "minimum_samples_for_adaptation": 3}

    def recommend(self, task_type: str, default_algorithm: str) -> dict[str, Any]:
        """Prefer a better-reviewed strategy only with >=3 samples and a clear margin."""
        with self._lock, init_sqlite(self.path) as conn:
            rows = conn.execute("""
                SELECT algorithm, COUNT(*),
                    AVG(CASE outcome WHEN 'success' THEN 1.0 WHEN 'partial' THEN 0.5 ELSE 0.0 END),
                    AVG(rating)
                FROM task_outcomes WHERE task_type = ?
                GROUP BY algorithm HAVING COUNT(*) >= 3
            """, (task_type,)).fetchall()
        candidates = [
            {"algorithm": r[0], "samples": int(r[1]), "success_score": float(r[2]),
             "average_rating": float(r[3])}
            for r in rows if r[0] in ALGORITHMS
        ]
        if not candidates:
            return {"algorithm": default_algorithm, "adapted": False, "reason": "insufficient_reviewed_outcomes"}
        best = max(candidates, key=lambda item: (item["success_score"], item["average_rating"], item["samples"]))
        baseline = next((item for item in candidates if item["algorithm"] == default_algorithm), None)
        if best["algorithm"] == default_algorithm:
            return {"algorithm": default_algorithm, "adapted": False, "reason": "default_strategy_is_best_reviewed"}
        if baseline is None:
            if best["success_score"] >= 0.8:
                return {"algorithm": best["algorithm"], "adapted": True,
                        "reason": "repeated_high_scoring_reviewed_outcomes",
                        "samples": best["samples"], "success_score": round(best["success_score"], 3)}
            return {"algorithm": default_algorithm, "adapted": False, "reason": "no_reviewed_baseline"}
        if best["success_score"] < baseline["success_score"] + 0.1:
            return {"algorithm": default_algorithm, "adapted": False, "reason": "no_clear_reviewed_improvement"}
        return {"algorithm": best["algorithm"], "adapted": True,
                "reason": "better_reviewed_outcome_score", "samples": best["samples"],
                "success_score": round(best["success_score"], 3)}

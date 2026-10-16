"""Bounded autonomous decision loop for safe, local-first agent workflows.

The engine automatically performs only registered read-only actions. Anything that
could mutate files, execute commands, access external services, or change policy is
returned as a plan requiring the existing approval path.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable

_SAFE_ACTIONS = {"workspace_overview", "learning_summary", "world_model_summary", "plan_task"}
_MAX_RUNS = 2000


class AutonomyStore:
    """Small persistent ledger for autonomy decisions and bounded execution summaries."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS autonomy_runs (
                    id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    action TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_autonomy_runs_created ON autonomy_runs(created_at DESC)")
            db.commit()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def record(self, *, goal: str, action: str, decision: str,
               status: str, result: dict[str, Any]) -> dict[str, Any]:
        ident = uuid.uuid4().hex
        now = time.time()
        payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
        with self._connect() as db:
            db.execute(
                "INSERT INTO autonomy_runs(id,goal,action,decision,status,result_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (ident, goal[:4000], action, decision, status, payload, now),
            )
            db.execute("""
                DELETE FROM autonomy_runs WHERE id IN (
                    SELECT id FROM autonomy_runs ORDER BY created_at DESC LIMIT -1 OFFSET ?
                )
            """, (_MAX_RUNS,))
            db.commit()
        return {"id": ident, "goal": goal, "action": action, "decision": decision,
                "status": status, "result": result, "created_at": now}

    def summary(self) -> dict[str, Any]:
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) FROM autonomy_runs").fetchone()[0]
            rows = db.execute(
                "SELECT status, COUNT(*) AS count FROM autonomy_runs GROUP BY status"
            ).fetchall()
            latest = db.execute(
                "SELECT id,goal,action,decision,status,created_at FROM autonomy_runs ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
        return {"count": total, "by_status": {row["status"]: row["count"] for row in rows},
                "recent": [dict(row) for row in latest]}


class AutonomyEngine:
    """Select and run a small allowlisted set of deterministic, read-only actions."""

    def __init__(self, *, store: AutonomyStore, workspace: Any,
                 learning: Any, world_model: Any, planner: Any,
                 analyze: Callable[..., dict[str, Any]],
                 task_lifecycle: Any, audit: Callable[..., Any]) -> None:
        self.store = store
        self.workspace = workspace
        self.learning = learning
        self.world_model = world_model
        self.planner = planner
        self.analyze = analyze
        self.task_lifecycle = task_lifecycle
        self.audit = audit

    @staticmethod
    def select_action(goal: str, requested: Any = None) -> str:
        if requested is not None:
            if not isinstance(requested, str) or requested not in _SAFE_ACTIONS:
                raise ValueError("action must be one of the registered safe actions")
            return requested
        normalized = goal.casefold()
        if any(word in normalized for word in ("workspace overview", "list workspace", "inspect workspace", "list files")):
            return "workspace_overview"
        if any(word in normalized for word in ("learning summary", "learning statistics", "reviewed outcomes")):
            return "learning_summary"
        if any(word in normalized for word in ("world model", "known facts", "observations")):
            return "world_model_summary"
        return "plan_task"

    def run(self, *, goal: str, action: Any = None, complexity: int = 1,
            risk: str = "read", has_external_side_effects: bool = False) -> dict[str, Any]:
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 4000:
            raise ValueError("goal must be a non-empty string of at most 4000 characters")
        if isinstance(complexity, bool) or not isinstance(complexity, int) or not 1 <= complexity <= 10:
            raise ValueError("complexity must be an integer from 1 to 10")
        if risk not in {"read", "low", "medium", "high", "critical"}:
            raise ValueError("invalid risk level")
        if not isinstance(has_external_side_effects, bool):
            raise ValueError("has_external_side_effects must be boolean")

        chosen = self.select_action(goal, action)
        signals = self.analyze(goal, evidence_available=chosen in {"workspace_overview", "learning_summary", "world_model_summary"})
        recommendation = self.learning.recommend(str(signals["task_type"]), str(signals["algorithm"]))
        signals["default_algorithm"] = signals["algorithm"]
        signals["algorithm"] = recommendation["algorithm"]
        signals["learning"] = recommendation

        # Mutating, external, or high-risk work never enters the autonomous executor.
        action_intent_markers = (
            "write ", "delete ", "remove ", "modify ", "change ", "edit ",
            "send ", "purchase ", "deploy ", "install ", "execute ", "run command",
            "commit ", "push ", "restart ", "upload ", "email ", "publish ",
        )
        inferred_side_effects = any(marker in goal.casefold() for marker in action_intent_markers)
        needs_review = (has_external_side_effects or inferred_side_effects
                        or risk in {"low", "medium", "high", "critical"})
        if needs_review and chosen != "plan_task":
            chosen = "plan_task"

        if chosen == "workspace_overview" and not needs_review and self.workspace is not None:
            result = {"files": self.workspace.list_files("."), "count_limit": 500,
                      "executed_action": "workspace_overview", "read_only": True}
            decision, status = "auto_execute_allowlisted_read_only", "completed"
        elif chosen == "workspace_overview" and self.workspace is None and not needs_review:
            raise ValueError("workspace tools are not available in this application context")
        elif chosen == "learning_summary" and not needs_review:
            result = {"learning": self.learning.summary(), "executed_action": "learning_summary",
                      "read_only": True}
            decision, status = "auto_execute_allowlisted_read_only", "completed"
        elif chosen == "world_model_summary" and not needs_review:
            facts = self.world_model.model.query()
            result = {"facts": facts[:200], "count": len(facts), "executed_action": "world_model_summary",
                      "read_only": True}
            decision, status = "auto_execute_allowlisted_read_only", "completed"
        else:
            plan = self.planner.plan(goal, complexity=complexity, risk=risk,
                                     has_external_side_effects=has_external_side_effects)
            task = self.task_lifecycle.create(
                goal=goal, task_type=str(signals["task_type"]),
                algorithm=str(signals["algorithm"]), risk=risk, steps=plan.steps,
            )
            result = {
                "task": task,
                "plan": {"strategy": plan.strategy, "steps": plan.steps,
                         "risk": plan.risk, "needs_approval": plan.needs_approval,
                         "rationale": plan.rationale},
                "execution_started": False,
                "notice": "Plan created automatically. External actions, writes, commands, and high-risk work are not executed by this loop; use the Command Control Center approval workflow.",
            }
            decision = "plan_and_defer_side_effects" if needs_review or plan.needs_approval else "plan_only_no_registered_executor"
            status = "awaiting_approval" if needs_review or plan.needs_approval else "planned"

        result["adaptive_signals"] = signals
        record = self.store.record(goal=goal, action=chosen, decision=decision, status=status, result=result)
        self.audit("autonomy", "autonomy.run." + status, record["id"], {
            "action": chosen, "decision": decision, "task_type": signals["task_type"],
            "algorithm": signals["algorithm"], "risk": risk, "read_only": status == "completed",
        })
        return {"run": record, "autonomy": {"enabled": True, "mode": "bounded_safe",
                "max_steps": 1, "permissions_changed": False}}

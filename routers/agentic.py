"""Bounded adaptive-planning and evidence world-model API routes."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from litestar import Router, get, post
from litestar.exceptions import HTTPException

from command_control import CommandControl
from application.task_intelligence import analyze_task
from application.learning import LearningStore
from terminal_ai_runtime import AdaptivePlanner, WorldModel, validate_skill_package

_MAX_FACTS_FILE_BYTES = 2_000_000


class PersistentWorldModel:
    """Small JSON-backed evidence store; observations are data, never executable instructions."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.model = WorldModel()
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        try:
            if not self.path.is_file() or self.path.stat().st_size > _MAX_FACTS_FILE_BYTES:
                return
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                return
            for item in payload[:5000]:
                if not isinstance(item, dict):
                    continue
                try:
                    ttl = max(1, float(item["expires_at"]) - float(item["observed_at"])) if item.get("expires_at") else None
                    fact = self.model.observe(
                        str(item["subject"]), str(item["predicate"]), item.get("value"),
                        source=str(item.get("source", "imported-local-state")),
                        confidence=float(item.get("confidence", 0.5)), ttl_seconds=ttl,
                    )
                    fact.observed_at = float(item.get("observed_at", fact.observed_at))
                    # Preserve the original absolute expiry; restarting must not extend a fact's TTL.
                    fact.expires_at = float(item["expires_at"]) if item.get("expires_at") is not None else None
                except (KeyError, TypeError, ValueError):
                    continue
        except (OSError, json.JSONDecodeError):
            return

    def observe(self, subject: str, predicate: str, value: Any, source: str, confidence: float,
                ttl_seconds: float | None) -> dict[str, Any]:
        with self._lock:
            fact = self.model.observe(subject, predicate, value, source=source,
                                      confidence=confidence, ttl_seconds=ttl_seconds)
            facts = self.model.query()
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(json.dumps([fact.__dict__ for fact in facts], ensure_ascii=False,
                                             separators=(",", ":"), default=str), encoding="utf-8")
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            temporary.replace(self.path)
            return fact.__dict__.copy()


def create_agentic_router(control: CommandControl, state_dir: str | Path, learning: LearningStore | None = None) -> Router:
    planner = AdaptivePlanner()
    world = PersistentWorldModel(Path(state_dir) / "world_model.json")
    learning_store = learning or LearningStore(Path(state_dir) / "learning.sqlite3")

    @get("/status")
    async def agentic_status() -> dict[str, Any]:
        return {
            "planning": "adaptive-deterministic",
            "world_model": "persistent-evidence-store",
            "world_facts": len(world.model.query()),
            "learning_records": learning_store.summary()["count"],
            "learning_mode": "verified-outcomes-only",
            "approval_system": "Command Control Center",
            "global_auto_execution": False,
            "self_consciousness": "operational introspection only; no claim of sentience",
        }

    @post("/plan")
    async def plan(data: dict[str, Any]) -> dict[str, Any]:
        goal = data.get("goal")
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 4000:
            raise HTTPException(status_code=400, detail="goal must be a non-empty string of at most 4000 characters.")
        risk = data.get("risk", "read")
        if risk not in {"read", "low", "medium", "high", "critical"}:
            raise HTTPException(status_code=400, detail="Invalid risk level.")
        complexity = data.get("complexity", 1)
        if isinstance(complexity, bool) or not isinstance(complexity, int) or not 1 <= complexity <= 10:
            raise HTTPException(status_code=400, detail="complexity must be an integer from 1 to 10.")
        side_effects = data.get("has_external_side_effects", False)
        if not isinstance(side_effects, bool):
            raise HTTPException(status_code=400, detail="has_external_side_effects must be boolean.")
        evidence_available = data.get("evidence_available", False)
        if not isinstance(evidence_available, bool):
            raise HTTPException(status_code=400, detail="evidence_available must be boolean.")
        try:
            signals = analyze_task(goal, evidence_available=evidence_available)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        learning_decision = learning_store.recommend(str(signals["task_type"]), str(signals["algorithm"]))
        signals["default_algorithm"] = signals["algorithm"]
        signals["algorithm"] = learning_decision["algorithm"]
        signals["learning"] = learning_decision
        if learning_decision["adapted"]:
            signals["reasons"] = list(signals["reasons"]) + ["selected:reviewed-outcome-learning"]
        result = planner.plan(goal, complexity=complexity, risk=risk,
                              has_external_side_effects=side_effects)
        control.audit("agentic", "plan.created", goal[:160], {
            "strategy": result.strategy, "algorithm": signals["algorithm"],
            "task_type": signals["task_type"], "risk": result.risk,
            "needs_approval": result.needs_approval, "complexity": complexity,
        })
        return {"plan": {
            "goal": goal, "strategy": result.strategy, "steps": result.steps,
            "risk": result.risk, "needs_approval": result.needs_approval,
            "rationale": result.rationale, "created_at": time.time(),
            "adaptive_signals": signals,
        }, "execution_started": False}

    @get("/world-model")
    async def list_world_facts(subject: str | None = None) -> dict[str, Any]:
        facts = world.model.query(subject)
        return {"generated_at": time.time(), "count": len(facts),
                "facts": [fact.__dict__ for fact in facts]}

    @post("/world-model/observe")
    async def observe_world_fact(data: dict[str, Any]) -> dict[str, Any]:
        subject, predicate, source = data.get("subject"), data.get("predicate"), data.get("source")
        if not isinstance(subject, str) or not subject.strip() or len(subject) > 200:
            raise HTTPException(status_code=400, detail="subject must be 1-200 characters.")
        if not isinstance(predicate, str) or not predicate.strip() or len(predicate) > 200:
            raise HTTPException(status_code=400, detail="predicate must be 1-200 characters.")
        if not isinstance(source, str) or not source.strip() or len(source) > 300:
            raise HTTPException(status_code=400, detail="source must be 1-300 characters.")
        if "value" not in data:
            raise HTTPException(status_code=400, detail="value is required.")
        try:
            confidence = float(data.get("confidence", 0.5))
            ttl = data.get("ttl_seconds")
            if ttl is not None:
                if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or not 1 <= ttl <= 31_536_000:
                    raise ValueError("ttl_seconds must be between 1 second and 1 year.")
            if not 0 <= confidence <= 1:
                raise ValueError("confidence must be between 0 and 1.")
            # Bound nested JSON size before persistence.
            encoded = json.dumps(data["value"], ensure_ascii=False, default=str)
            if len(encoded) > 20_000:
                raise ValueError("value exceeds 20000 characters.")
            fact = world.observe(subject, predicate, data["value"], source, confidence, ttl)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        control.audit("agentic", "world-model.observed", subject, {
            "predicate": predicate, "source": source, "confidence": confidence,
        })
        return {"fact": fact, "stored": True}

    @post("/skills/validate")
    async def validate_skill(data: dict[str, Any]) -> dict[str, Any]:
        try:
            validated = validate_skill_package(data)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)[:300]) from exc
        return {"skill": validated, "saved": False, "execution_started": False}

    return Router(path="/api/agentic", route_handlers=[
        agentic_status, plan, list_world_facts, observe_world_fact, validate_skill,
    ])

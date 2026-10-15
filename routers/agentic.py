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
from application.skill_evolution import SkillEvolutionStore
from application.task_lifecycle import TaskLifecycleStore
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
    skill_evolution = SkillEvolutionStore(Path(state_dir) / "skill_proposals.sqlite3")
    task_lifecycle = TaskLifecycleStore(Path(state_dir) / "task_lifecycle.sqlite3")

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

    @post("/tasks")
    async def create_task_run(data: dict[str, Any]) -> dict[str, Any]:
        """Persist a bounded plan for tracking; this route never executes its steps."""
        goal = data.get("goal")
        risk = data.get("risk", "read")
        complexity = data.get("complexity", 1)
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 4000:
            raise HTTPException(status_code=400, detail="goal must be a non-empty string of at most 4000 characters.")
        if risk not in {"read", "low", "medium", "high", "critical"}:
            raise HTTPException(status_code=400, detail="Invalid risk level.")
        if isinstance(complexity, bool) or not isinstance(complexity, int) or not 1 <= complexity <= 10:
            raise HTTPException(status_code=400, detail="complexity must be an integer from 1 to 10.")
        side_effects = data.get("has_external_side_effects", False)
        evidence_available = data.get("evidence_available", False)
        if not isinstance(side_effects, bool) or not isinstance(evidence_available, bool):
            raise HTTPException(status_code=400, detail="side-effects and evidence flags must be boolean.")
        try:
            signals = analyze_task(goal, evidence_available=evidence_available)
            decision = learning_store.recommend(str(signals["task_type"]), str(signals["algorithm"]))
            signals["algorithm"] = decision["algorithm"]
            plan_result = planner.plan(goal, complexity=complexity, risk=risk,
                                       has_external_side_effects=side_effects)
            task = task_lifecycle.create(goal=goal, task_type=str(signals["task_type"]),
                                         algorithm=str(signals["algorithm"]), risk=risk,
                                         steps=plan_result.steps)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        control.audit("agentic", "task.created", task["id"], {
            "task_type": task["task_type"], "algorithm": task["algorithm"],
            "risk": risk, "step_count": len(task["steps"]), "execution_started": False,
        })
        return {"task": task, "plan": {"strategy": plan_result.strategy,
                "rationale": plan_result.rationale, "needs_approval": plan_result.needs_approval,
                "adaptive_signals": signals}, "execution_started": False}

    @get("/tasks")
    async def list_task_runs(status: str | None = None, limit: int = 50) -> dict[str, Any]:
        if status is not None and status not in {
            "planned", "awaiting_approval", "approved", "executing", "executed",
            "verified", "reviewed", "failed", "rejected", "expired",
        }:
            raise HTTPException(status_code=400, detail="Invalid task status.")
        items = task_lifecycle.list(limit, status)
        return {"tasks": items, "count": len(items), "execution_started": False}

    @get("/tasks/{task_id:str}")
    async def get_task_run(task_id: str) -> dict[str, Any]:
        task = task_lifecycle.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task run not found.")
        if task.get("operation_id"):
            operation = control.get_operation(task["operation_id"])
            if operation is not None:
                try:
                    task = task_lifecycle.sync_operation(task_id, operation)
                except ValueError:
                    pass
        return {"task": task, "execution_started": False}

    @post("/tasks/{task_id:str}/operation")
    async def link_task_operation(task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        operation_id = data.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id.strip() or len(operation_id) > 80:
            raise HTTPException(status_code=400, detail="operation_id is required.")
        operation = control.get_operation(operation_id)
        if operation is None:
            raise HTTPException(status_code=404, detail="Command Control operation not found.")
        if operation["status"] not in {"pending", "approved", "executing", "executed", "failed"}:
            raise HTTPException(status_code=409, detail="Only active or completed operations can be linked.")
        try:
            task = task_lifecycle.link_operation(task_id, operation)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Task run not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        control.audit("agentic", "task.operation_linked", task_id, {
            "operation_id": operation_id, "operation_status": operation["status"],
            "tool": operation["tool"], "operation": operation["operation"],
        })
        return {"task": task, "execution_started": False,
                "notice": "Linking records the operation association; it does not approve or execute it."}

    @post("/tasks/{task_id:str}/verify")
    async def verify_task_run(task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        task = task_lifecycle.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task run not found.")
        if task.get("operation_id"):
            operation = control.get_operation(task["operation_id"])
            if operation is not None:
                try:
                    task = task_lifecycle.sync_operation(task_id, operation)
                except ValueError:
                    pass
        try:
            task = task_lifecycle.verify(task_id, passed=data.get("passed"),
                                         evidence=data.get("evidence"), verifier=data.get("verifier", "operator"))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Task run not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        control.audit("agentic", "task.verified" if task["status"] == "verified" else "task.verification_failed",
                      task_id, {"passed": task["verification"]["passed"],
                                "verifier": task["verification"]["verifier"]})
        return {"task": task, "learning_recorded": False}

    @post("/tasks/{task_id:str}/review")
    async def review_task_run(task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        task = task_lifecycle.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task run not found.")
        if task.get("operation_id"):
            operation = control.get_operation(task["operation_id"])
            if operation is not None:
                try:
                    task = task_lifecycle.sync_operation(task_id, operation)
                except ValueError:
                    pass
        outcome, rating, reviewer = data.get("outcome"), data.get("rating"), data.get("reviewer", "operator")
        if outcome not in {"success", "partial", "failure"}:
            raise HTTPException(status_code=400, detail="outcome must be success, partial, or failure.")
        if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5:
            raise HTTPException(status_code=400, detail="rating must be an integer from 1 to 5.")
        try:
            task = task_lifecycle.review(task_id, outcome=outcome, rating=rating, reviewer=reviewer)
            record = learning_store.record(task_type=task["task_type"], algorithm=task["algorithm"],
                                           outcome=outcome, rating=rating, verified=True)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Task run not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        control.audit("agentic", "task.reviewed", task_id, {
            "outcome": outcome, "rating": rating, "learning_record_id": record["id"],
            "verified": True, "reviewer": reviewer[:100] if isinstance(reviewer, str) else "operator",
        })
        return {"task": task, "learning_record": record,
                "permissions_changed": False, "execution_started": False}

    @get("/learning/summary")
    async def learning_summary() -> dict[str, Any]:
        return {"generated_at": time.time(), **learning_store.summary()}

    @post("/learning/outcome")
    async def record_learning_outcome(data: dict[str, Any]) -> dict[str, Any]:
        try:
            record = learning_store.record(
                task_type=data.get("task_type"), algorithm=data.get("algorithm"),
                outcome=data.get("outcome"), rating=data.get("rating"), verified=data.get("verified"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        control.audit("agentic", "learning.outcome_recorded", record["task_type"], {
            "algorithm": record["algorithm"], "outcome": record["outcome"],
            "rating": record["rating"], "verified": record["verified"],
        })
        return {"record": record, "stored": True, "permissions_changed": False}

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

    @get("/skills/proposals")
    async def list_skill_proposals(status: str | None = None, limit: int = 100) -> dict[str, Any]:
        try:
            items = skill_evolution.list(status=status, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"proposals": items, "count": len(items), "execution_started": False}

    @post("/skills/proposals/from-learning")
    async def draft_skill_from_reviewed_learning() -> dict[str, Any]:
        """Create a non-executable proposal from repeated, explicitly verified outcomes."""
        groups = learning_store.summary()["groups"]
        candidates = [
            item for item in groups
            if item["samples"] >= 3 and (
                (item["success_score"] >= 0.67 and item["average_rating"] >= 3.5)
                or item["success_score"] <= 0.33
                or item["average_rating"] <= 2.5
            )
        ]
        if not candidates:
            raise HTTPException(
                status_code=409,
                detail="No repeated pattern qualifies yet. Need at least 3 reviewed outcomes and either strong success (score >= 0.67, rating >= 3.5) or a recurring failure/low-rating signal (score <= 0.33 or rating <= 2.5).",
            )
        chosen = max(
            candidates,
            key=lambda item: (
                item["success_score"] <= 0.33 or item["average_rating"] <= 2.5,
                item["samples"], -item["success_score"], item["task_type"],
            ),
        )
        family = chosen["task_type"]
        algorithm = chosen["algorithm"]
        failure_pattern = chosen["success_score"] <= 0.33 or chosen["average_rating"] <= 2.5
        if failure_pattern:
            name = ("Recovery workflow for " + family.replace("_", " "))[:80]
            rationale = (
                "A remediation checklist proposed because repeated reviewed outcomes show a low success or rating signal. "
                "Inspect the cause before use; aggregate evidence alone does not establish a diagnosis."
            )
            steps = [
                "Restate the intended result and capture the observed failure without secrets.",
                "Gather independent evidence and distinguish symptoms from verified causes.",
                "Reproduce the issue in a bounded, non-destructive setting where possible.",
                "Choose a corrective strategy and document its assumptions.",
                "Verify the correction with a focused check or regression test.",
                "Summarize unresolved risks and request human review before side effects.",
            ]
        else:
            name = ("Reviewed " + family.replace("_", " ") + " workflow")[:80]
            rationale = (
                "A candidate checklist derived from repeated, explicitly verified positive outcomes. "
                "This aggregate signal is not proof that the workflow is universally safe or correct."
            )
            steps = [
                "Define the objective and observable success criteria before acting.",
                "Gather relevant evidence and record important uncertainty.",
                "Apply the reviewed strategy: " + algorithm + ".",
                "Verify the result against the stated success criteria.",
                "Summarize the evidence and unresolved risks for human review.",
                "Obtain separate human approval before any side-effectful operation.",
            ]
        item = skill_evolution.create(
            name=name, task_type=family, rationale=rationale, steps=steps,
            evidence_summary=(
                f"{chosen['samples']} verified outcomes; success score {chosen['success_score']:.2f}; "
                f"average reviewer rating {chosen['average_rating']:.1f}/5; strategy {algorithm}; "
                f"pattern {'recurring_failure' if failure_pattern else 'repeated_success'}. "
                "Aggregate evidence only; no task prompts or credentials included."
            ),
        )
        control.audit("skills", "proposal.generated_from_learning", item["name"], {
            "proposal_id": item["id"], "task_type": family, "algorithm": algorithm,
            "samples": chosen["samples"], "success_score": chosen["success_score"],
            "pattern": "recurring_failure" if failure_pattern else "repeated_success",
        })
        return {
            "proposal": item, "generated_from_reviewed_outcomes": True,
            "pattern": "recurring_failure" if failure_pattern else "repeated_success",
            "execution_started": False, "permissions_changed": False,
            "notice": "Draft created in proposed state. Static validation and explicit human approval are still required.",
        }

    @post("/skills/proposals")
    async def create_skill_proposal(data: dict[str, Any]) -> dict[str, Any]:
        try:
            item = skill_evolution.create(
                name=data.get("name"), task_type=data.get("task_type"),
                rationale=data.get("rationale"), steps=data.get("steps"),
                evidence_summary=data.get("evidence_summary"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        control.audit("skills", "proposal.created", item["name"], {"proposal_id": item["id"], "task_type": item["task_type"]})
        return {"proposal": item, "execution_started": False, "permissions_changed": False}

    @post("/skills/proposals/{proposal_id:str}/validate")
    async def validate_skill_proposal(proposal_id: str) -> dict[str, Any]:
        item = skill_evolution.get(proposal_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Skill proposal not found.")
        errors = SkillEvolutionStore.validate_fields(item["name"], item["task_type"], item["rationale"], item["steps"], item["evidence_summary"])
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors))
        try:
            item = skill_evolution.transition(proposal_id, "validate", "Static structural checks passed; no code executed.")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        control.audit("skills", "proposal.validated", item["name"], {"proposal_id": proposal_id})
        return {"proposal": item, "static_validation_only": True, "execution_started": False}

    @post("/skills/proposals/{proposal_id:str}/approve")
    async def approve_skill_proposal(proposal_id: str, data: dict[str, Any]) -> dict[str, Any]:
        note = data.get("note", "")
        try:
            item = skill_evolution.transition(proposal_id, "approve", note)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Skill proposal not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        control.audit("skills", "proposal.approved", item["name"], {"proposal_id": proposal_id, "note": note[:500] if isinstance(note, str) else ""})
        return {"proposal": item, "approved_by_human": True, "execution_started": False, "permissions_changed": False}

    @post("/skills/proposals/{proposal_id:str}/reject")
    async def reject_skill_proposal(proposal_id: str, data: dict[str, Any]) -> dict[str, Any]:
        note = data.get("note", "")
        try:
            item = skill_evolution.transition(proposal_id, "reject", note)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Skill proposal not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        control.audit("skills", "proposal.rejected", item["name"], {"proposal_id": proposal_id, "note": note[:500] if isinstance(note, str) else ""})
        return {"proposal": item, "execution_started": False, "permissions_changed": False}

    @post("/skills/proposals/{proposal_id:str}/promote")
    async def promote_skill_proposal(proposal_id: str, data: dict[str, Any]) -> dict[str, Any]:
        note = data.get("note", "")
        try:
            item = skill_evolution.transition(proposal_id, "promote", note)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Skill proposal not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        control.audit("skills", "proposal.promoted", item["name"], {"proposal_id": proposal_id, "note": note[:500] if isinstance(note, str) else ""})
        return {"proposal": item, "promoted_to_reviewed_catalog": True, "execution_started": False, "permissions_changed": False}

    return Router(path="/api/agentic", route_handlers=[
        agentic_status, plan, create_task_run, list_task_runs, get_task_run, link_task_operation,\n        verify_task_run, review_task_run, learning_summary, record_learning_outcome,
        list_world_facts, observe_world_fact, validate_skill,
        list_skill_proposals, create_skill_proposal, draft_skill_from_reviewed_learning, validate_skill_proposal,
        approve_skill_proposal, reject_skill_proposal, promote_skill_proposal,
    ])

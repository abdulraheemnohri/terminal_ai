"""Adaptive strategy selection using explicit complexity, uncertainty and risk signals."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any

@dataclass(frozen=True)
class PlanDecision:
    strategy: str
    rationale: str
    steps: tuple[str, ...]
    requires_approval: bool
    risk: str
    score: float

class AdaptivePlanner:
    """Deterministic routing policy; it selects a workflow, not a model's hidden thoughts."""
    STRATEGIES = {"direct", "research", "decompose", "review_execute"}
    def choose(self, task: str, *, complexity: float = 0.5, uncertainty: float = 0.3,
               risk: str = "low", external_side_effects: bool = False,
               has_evidence: bool = False) -> dict[str, Any]:
        if not task or not task.strip(): raise ValueError("task cannot be empty")
        for name, value in (("complexity", complexity), ("uncertainty", uncertainty)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        risk = risk.casefold()
        if risk not in {"low", "medium", "high", "critical"}: raise ValueError("invalid risk")
        score = round(0.45*complexity + 0.35*uncertainty + (0.2 if external_side_effects else 0), 3)
        approval = external_side_effects or risk in {"high", "critical"}
        if risk == "critical" or external_side_effects or risk == "high":
            strategy, steps = "review_execute", ("clarify_scope", "draft_plan", "request_approval", "execute_allowlisted_tools", "verify")
            why = "Side effects or elevated risk require review before execution."
        elif uncertainty >= 0.65 and not has_evidence:
            strategy, steps = "research", ("identify_questions", "gather_sources", "cross_check_evidence", "summarize_uncertainty", "verify")
            why = "High uncertainty and insufficient evidence favor research first."
        elif complexity >= 0.6 or score >= 0.55:
            strategy, steps = "decompose", ("break_into_subtasks", "order_dependencies", "execute_bounded_steps", "verify_each_step", "summarize")
            why = "Complexity score favors dependency-aware decomposition."
        else:
            strategy, steps = "direct", ("answer_or_act_with_allowlisted_tools", "verify", "summarize")
            why = "Low-complexity task can use a direct, verified workflow."
        return asdict(PlanDecision(strategy, why, steps, approval, risk, score))

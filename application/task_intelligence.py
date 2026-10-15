"""Explainable task signals for adaptive workflow selection.

This is operational introspection, not consciousness. The classifier is a
heuristic: its estimates are surfaced to callers and never grant permissions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re


@dataclass(frozen=True)
class TaskSignals:
    task_type: str
    complexity_estimate: int
    uncertainty_estimate: float
    algorithm: str
    reasons: tuple[str, ...]


_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("debugging", ("debug", "bug", "error", "traceback", "failing test", "fix")),
    ("software_change", ("implement", "refactor", "add feature", "write code", "repository", "repo")),
    ("research", ("research", "latest", "compare", "sources", "investigate", "look up")),
    ("browser_work", ("browse", "website", "web page", "form", "navigate", "click")),
    ("planning", ("plan", "roadmap", "milestone", "architecture", "design")),
    ("writing", ("write", "draft", "summarize", "translate", "explain")),
)
_COMPLEXITY_MARKERS = (
    " and ", " then ", " end-to-end", " complete ", " all ", " multiple ",
    " integrate ", " migrate ", " across ", " automate ",
)


def analyze_task(task: str, *, evidence_available: bool = False) -> dict[str, object]:
    """Return bounded heuristic signals and a strategy recommendation."""
    if not isinstance(task, str) or not task.strip():
        raise ValueError("task must be a non-empty string")
    if len(task) > 4000:
        raise ValueError("task must be at most 4000 characters")
    if not isinstance(evidence_available, bool):
        raise ValueError("evidence_available must be boolean")

    normalized = " " + re.sub(r"\s+", " ", task.casefold()).strip() + " "
    matches = [(kind, words) for kind, words in _PATTERNS
               if any(word in normalized for word in words)]
    task_type = matches[0][0] if matches else "general"
    reasons: list[str] = [f"task-family:{task_type}"]
    complexity = 1
    complexity += min(4, sum(1 for marker in _COMPLEXITY_MARKERS if marker in normalized))
    if len(task) > 500:
        complexity += 2
        reasons.append("long-task-description")
    elif len(task) > 180:
        complexity += 1
        reasons.append("multi-clause-description")
    if task_type in {"debugging", "software_change", "browser_work", "planning"}:
        complexity += 1
        reasons.append("workflow-requires-validation")
    complexity = min(10, complexity)

    uncertainty = 0.25
    if task_type == "research":
        uncertainty += 0.35
        reasons.append("external-facts-may-change")
    if task_type == "debugging":
        uncertainty += 0.2
        reasons.append("root-cause-not-yet-established")
    if not evidence_available:
        uncertainty += 0.15
        reasons.append("no-evidence-supplied")
    if any(word in normalized for word in ("latest", "current", "today", "recent", "now ")):
        uncertainty += 0.15
        reasons.append("time-sensitive-request")
    uncertainty = round(min(1.0, uncertainty), 2)

    if task_type == "research" or (uncertainty >= 0.65 and not evidence_available):
        algorithm = "evidence-first"
    elif complexity >= 6:
        algorithm = "decompose-and-verify"
    elif task_type in {"debugging", "software_change"}:
        algorithm = "test-driven-loop"
    elif task_type == "browser_work":
        algorithm = "observe-act-verify"
    else:
        algorithm = "direct-verify"
    reasons.append(f"selected:{algorithm}")
    return asdict(TaskSignals(task_type, complexity, uncertainty, algorithm, tuple(reasons)))

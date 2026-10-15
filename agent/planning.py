"""Task planning, persona guidance, and bounded recovery prompts."""
from __future__ import annotations

import re

_COMPLEX_TASK = re.compile(
    r"\b(implement|debug|diagnose|compare|evaluate|plan|multi[- ]step|"
    r"architecture|refactor|investigate|design|analy[sz]e|review|"
    r"step[- ]by[- ]step|several files|whole project)\b",
    re.IGNORECASE,
)


def needs_planning(prompt: str) -> bool:
    """Return whether a request likely benefits from a compact internal plan."""
    return len(prompt.split()) >= 45 or bool(_COMPLEX_TASK.search(prompt))


def planning_instruction(prompt: str, enabled: bool = True) -> str:
    """Ask the model to plan privately and return useful user-facing output."""
    if not enabled or not needs_planning(prompt):
        return ""
    return (
        "For this complex request, first make a concise internal task plan. "
        "Check assumptions, dependencies, edge cases, and how success will be "
        "verified. Keep private reasoning/scratch work internal; do not reveal "
        "hidden chain-of-thought. In the final answer, provide the conclusion, "
        "key rationale, actionable steps, and verification results only."
    )


def persona_instruction(persona: str = "helpful", *, language: str = "match_user") -> str:
    """Return bounded conversational style guidance without changing permissions."""
    profiles = {
        "helpful": "Be helpful, direct, respectful, and context-aware.",
        "technical": "Use precise technical language, state assumptions, and include testable steps.",
        "coach": "Be encouraging and practical; break complex work into manageable steps.",
        "concise": "Prefer concise answers, but retain important safety and correctness details.",
        "creative": "Use an imaginative, natural voice while distinguishing facts from invention.",
        "roleplay": (
            "Maintain the user's fictional character, setting, and scene continuity. "
            "Clearly keep fictional events distinct from real-world facts; do not claim "
            "to be a real person or assert a fictional identity is real."
        ),
    }
    style = profiles.get(str(persona).lower(), profiles["helpful"])
    language_hint = (
        "Reply in the user's language unless they request another language."
        if language == "match_user" else f"Prefer {language} unless the user requests another language."
    )
    return (
        f"Conversation style: {style} {language_hint} Use relevant recent conversation "
        "context and explicitly saved memory when available. Do not invent memories. "
        "Ask a focused clarification only when essential information is missing."
    )


def recovery_instruction(error: BaseException, attempt: int, max_attempts: int) -> str:
    """Build a safe retry hint without echoing exception text or possible secrets."""
    category = type(error).__name__
    return (
        f"The previous model attempt failed with {category}. This is recovery "
        f"attempt {attempt} of {max_attempts}. Re-evaluate the request and try "
        "again once using a simpler approach. Do not repeat any failed tool call "
        "without changing the cause. Do not claim success unless the result is verified."
    )

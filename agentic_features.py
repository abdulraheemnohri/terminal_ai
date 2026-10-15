"""Small, dependency-free helpers for reliable agentic turns.

This module deliberately stores no private chain-of-thought. It provides a
short task plan, structured tool-call validation, persona/context guidance,
and bounded error-recovery prompts.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ToolCallValidation:
    accepted: list[dict[str, Any]]
    rejected: list[str]


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
    """Ask the model to plan privately and return only useful user-facing output."""
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


def validate_tool_calls(
    calls: Iterable[dict[str, Any]],
    schema: list[dict[str, Any]],
    *,
    allowed_names: set[str] | None = None,
) -> ToolCallValidation:
    """Validate names, argument shape, and declared argument types before dispatch."""
    by_name = {str(item.get("name", "")): item for item in schema if item.get("name")}
    accepted: list[dict[str, Any]] = []
    rejected: list[str] = []
    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            rejected.append(f"call {index + 1}: expected an object")
            continue
        name = call.get("name")
        args = call.get("args", {})
        if not isinstance(name, str) or name not in by_name:
            rejected.append(f"call {index + 1}: unknown tool")
            continue
        if allowed_names is not None and name not in allowed_names:
            rejected.append(f"call {index + 1}: tool is not permitted in this execution mode")
            continue
        if not isinstance(args, dict):
            rejected.append(f"{name}: args must be an object")
            continue
        declared = by_name[name].get("args", {})
        if not isinstance(declared, dict):
            declared = {}
        unknown = sorted(set(args) - set(declared))
        if unknown:
            rejected.append(f"{name}: unsupported argument(s): {', '.join(unknown[:5])}")
            continue
        type_map = {
            "string": lambda value: isinstance(value, str),
            "str": lambda value: isinstance(value, str),
            "int": lambda value: isinstance(value, int) and not isinstance(value, bool),
            "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
            "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
            "float": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
            "bool": lambda value: isinstance(value, bool),
            "boolean": lambda value: isinstance(value, bool),
            "list": lambda value: isinstance(value, list),
            "dict": lambda value: isinstance(value, dict),
            "object": lambda value: isinstance(value, dict),
        }
        bad_type = next(
            (key for key, value in args.items()
             if isinstance(declared.get(key), str)
             and declared[key].lower() in type_map
             and not type_map[declared[key].lower()](value)),
            None,
        )
        if bad_type:
            rejected.append(f"{name}: invalid type for argument '{bad_type}'")
            continue
        accepted.append({"name": name, "args": args})
    return ToolCallValidation(accepted=accepted, rejected=rejected)


def recovery_instruction(error: BaseException, attempt: int, max_attempts: int) -> str:
    """Build a safe retry hint that avoids echoing exception text/secrets."""
    category = type(error).__name__
    return (
        f"The previous model attempt failed with {category}. This is recovery "
        f"attempt {attempt} of {max_attempts}. Re-evaluate the request and try "
        "again once using a simpler approach. Do not repeat any failed tool call "
        "without changing the cause. Do not claim success unless the result is verified."
    )


def parse_json_tool_payload(payload: str) -> dict[str, Any] | None:
    """Strictly parse a standalone JSON tool payload."""
    try:
        value = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None

"""Safe declarative skill documents. Skills never contain executable Python or shell code."""
from __future__ import annotations
import json, re
from pathlib import Path
from typing import Any

_NAME = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_ALLOWED_STEP_TYPES = {"tool", "ask_user", "condition", "summarize"}

def validate_skill(document: Any, *, allowed_tools: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(document, dict): raise ValueError("skill must be a JSON object")
    if not isinstance(document.get("name"), str) or not _NAME.fullmatch(document["name"]):
        raise ValueError("name must be 2-64 lowercase letters, digits, _ or -")
    if not isinstance(document.get("description"), str) or not document["description"].strip():
        raise ValueError("description is required")
    steps = document.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
        raise ValueError("steps must contain 1..100 items")
    cleaned = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or step.get("type") not in _ALLOWED_STEP_TYPES:
            raise ValueError(f"step {index+1}: unsupported type")
        kind = step["type"]
        if kind == "tool":
            tool = step.get("tool")
            if not isinstance(tool, str) or not tool.strip(): raise ValueError(f"step {index+1}: tool required")
            if allowed_tools is not None and tool not in allowed_tools:
                raise ValueError(f"step {index+1}: tool is not in the active allowlist")
            args = step.get("arguments", {})
            if not isinstance(args, dict): raise ValueError(f"step {index+1}: arguments must be an object")
            cleaned.append({"type": kind, "tool": tool, "arguments": args})
        else:
            text = step.get("text", "")
            if not isinstance(text, str) or len(text) > 2000: raise ValueError(f"step {index+1}: invalid text")
            cleaned.append({"type": kind, "text": text})
    return {"version": 1, "name": document["name"], "description": document["description"][:500],
            "steps": cleaned, "trust": "untrusted"}

def load_skill(path: str | Path, *, allowed_tools: set[str] | None = None) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_skill(raw, allowed_tools=allowed_tools)

def save_skill(path: str | Path, document: Any, *, allowed_tools: set[str] | None = None) -> Path:
    skill = validate_skill(document, allowed_tools=allowed_tools)
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(skill, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    return target

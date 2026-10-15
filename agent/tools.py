"""Typed structured-tool validation and strict JSON payload parsing."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ToolCallValidation:
    accepted: list[dict[str, Any]]
    rejected: list[str]


def validate_tool_calls(
    calls: Iterable[dict[str, Any]],
    schema: list[dict[str, Any]],
    *,
    allowed_names: set[str] | None = None,
) -> ToolCallValidation:
    """Validate tool names, argument shape, and declared types before dispatch."""
    by_name = {str(item.get("name", "")): item for item in schema if item.get("name")}
    accepted: list[dict[str, Any]] = []
    rejected: list[str] = []
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


def parse_json_tool_payload(payload: str) -> dict[str, Any] | None:
    """Strictly parse a standalone JSON tool payload."""
    try:
        value = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None

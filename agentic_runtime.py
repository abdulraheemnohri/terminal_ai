"""Safe, provider-agnostic agent runtime primitives for Terminal AI.

This module supplies structured tool calling, bounded recovery, and explicit
conversation history without exposing private reasoning traces. Model-specific
adapters can use these primitives without coupling the core to one provider.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


class AgentRuntimeError(RuntimeError):
    """Base error for agent runtime operations."""


class ToolValidationError(AgentRuntimeError):
    """Raised when a tool call fails schema validation."""


class ToolApprovalRequired(AgentRuntimeError):
    """Raised when a tool requires user approval before execution."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    parameters: Mapping[str, Any] = field(default_factory=lambda: {
        "type": "object", "properties": {}, "additionalProperties": False
    })
    requires_approval: bool = False
    enabled: bool = True
    timeout_seconds: float = 15.0


@dataclass
class ToolResult:
    tool_name: str
    ok: bool
    output: Any = None
    error: str | None = None
    duration_ms: int = 0
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class ToolRegistry:
    """Explicit allowlist of callable tools; never executes arbitrary model code."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.-]{0,63}", spec.name):
            raise ValueError("Tool name must be a simple identifier (max 64 chars).")
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        if spec.timeout_seconds <= 0 or spec.timeout_seconds > 300:
            raise ValueError("timeout_seconds must be between 0 and 300.")
        if spec.parameters.get("type") != "object":
            raise ValueError("Tool parameters must be an object schema.")
        self._tools[spec.name] = spec

    def describe(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description,
             "parameters": dict(t.parameters), "requires_approval": t.requires_approval}
            for t in self._tools.values() if t.enabled
        ]

    def execute(
        self, name: str, arguments: Mapping[str, Any], *,
        approved: bool = False, max_output_chars: int = 12000
    ) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None or not spec.enabled:
            return ToolResult(name, False, error="Unknown or disabled tool.")
        if not isinstance(arguments, Mapping):
            return ToolResult(name, False, error="Arguments must be a JSON object.")
        try:
            _validate_schema(arguments, spec.parameters, "$")
        except ToolValidationError as exc:
            return ToolResult(name, False, error=str(exc))
        if spec.requires_approval and not approved:
            return ToolResult(name, False, error="Approval required; tool was not executed.")
        started = time.monotonic()
        try:
            # Python cannot safely interrupt an arbitrary synchronous handler.
            # Handlers must enforce their own I/O timeout; this value is metadata.
            output = spec.handler(**dict(arguments))
            rendered = output if isinstance(output, str) else json.dumps(
                output, ensure_ascii=False, default=str
            )
            if len(rendered) > max_output_chars:
                rendered = rendered[:max_output_chars] + "\n[output truncated]"
            return ToolResult(name, True, output=rendered,
                              duration_ms=int((time.monotonic() - started) * 1000))
        except Exception as exc:  # Return bounded diagnostic, not a traceback or secret.
            return ToolResult(name, False, error=f"{type(exc).__name__}: {str(exc)[:500]}",
                              duration_ms=int((time.monotonic() - started) * 1000))


def _validate_schema(value: Any, schema: Mapping[str, Any], path: str) -> None:
    """Small strict JSON Schema subset (types, required, properties, enums, bounds)."""
    expected = schema.get("type")
    types = {
        "object": lambda v: isinstance(v, Mapping),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
    }
    if expected in types and not types[expected](value):
        raise ToolValidationError(f"{path}: expected {expected}.")
    if "enum" in schema and value not in schema["enum"]:
        raise ToolValidationError(f"{path}: value is not an allowed enum member.")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ToolValidationError(f"{path}: string is too short.")
        if len(value) > schema.get("maxLength", 100000):
            raise ToolValidationError(f"{path}: string is too long.")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise ToolValidationError(f"{path}: string does not match required pattern.")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get("minimum", float("-inf")) or value > schema.get("maximum", float("inf")):
            raise ToolValidationError(f"{path}: number is outside permitted bounds.")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 10000):
            raise ToolValidationError(f"{path}: array length is outside permitted bounds.")
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                _validate_schema(item, item_schema, f"{path}[{i}]")
    if isinstance(value, Mapping):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise ToolValidationError(f"{path}: missing required field(s): {', '.join(missing)}.")
        if schema.get("additionalProperties", True) is False:
            extras = [key for key in value if key not in properties]
            if extras:
                raise ToolValidationError(f"{path}: unexpected field(s): {', '.join(map(str, extras))}.")
        for key, item in value.items():
            if key in properties:
                _validate_schema(item, properties[key], f"{path}.{key}")


def parse_tool_call(payload: str | Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    """Parse a provider-neutral tool call; reject malformed or non-object arguments."""
    try:
        data = json.loads(payload) if isinstance(payload, str) else dict(payload)
    except (ValueError, TypeError) as exc:
        raise ToolValidationError("Tool call must be valid JSON.") from exc
    if not isinstance(data, dict) or set(data) - {"name", "arguments", "id"}:
        raise ToolValidationError("Tool call must contain only name, arguments, and optional id.")
    name, arguments = data.get("name"), data.get("arguments", {})
    if not isinstance(name, str) or not name:
        raise ToolValidationError("Tool call requires a non-empty name.")
    if not isinstance(arguments, dict):
        raise ToolValidationError("Tool call arguments must be a JSON object.")
    return name, arguments


@dataclass
class Message:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationBuffer:
    """Bounded, multi-turn context buffer; private reasoning is not a supported role."""

    ALLOWED_ROLES = {"system", "user", "assistant", "tool"}

    def __init__(self, max_messages: int = 80, max_chars: int = 40000) -> None:
        if max_messages < 2 or max_chars < 100:
            raise ValueError("Conversation limits are too small.")
        self._messages: deque[Message] = deque(maxlen=max_messages)
        self.max_chars = max_chars

    def add(self, role: str, content: str, metadata: Mapping[str, Any] | None = None) -> None:
        if role not in self.ALLOWED_ROLES:
            raise ValueError(f"Unsupported message role: {role}")
        if not isinstance(content, str):
            raise TypeError("Message content must be text.")
        self._messages.append(Message(role, content, metadata=dict(metadata or {})))
        self._trim_chars()

    def _trim_chars(self) -> None:
        while self._messages and sum(len(m.content) for m in self._messages) > self.max_chars:
            # Preserve the newest message even if it alone exceeds the budget.
            if len(self._messages) <= 1:
                break
            self._messages.popleft()

    def messages(self) -> list[dict[str, Any]]:
        return [{"role": m.role, "content": m.content, "timestamp": m.timestamp,
                 "metadata": dict(m.metadata)} for m in self._messages]

    def clear(self) -> None:
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)


@dataclass
class RecoveryReport:
    attempts: int
    success: bool
    output: Any = None
    errors: list[str] = field(default_factory=list)


def run_with_recovery(
    operation: Callable[[], Any],
    *,
    validate: Callable[[Any], bool] | None = None,
    repair: Callable[[Any, str, int], Any] | None = None,
    max_attempts: int = 3,
) -> RecoveryReport:
    """Run a bounded retry/repair loop. No unbounded autonomous execution."""
    if not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be between 1 and 5.")
    errors: list[str] = []
    candidate: Any = None
    for attempt in range(1, max_attempts + 1):
        try:
            candidate = operation() if attempt == 1 or repair is None else repair(
                candidate, errors[-1], attempt
            )
            if validate is None or validate(candidate):
                return RecoveryReport(attempt, True, candidate, errors)
            error = "Output did not pass validation."
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:500]}"
        errors.append(error)
        if repair is None and attempt < max_attempts:
            continue
    return RecoveryReport(min(max_attempts, len(errors)), False, candidate, errors)

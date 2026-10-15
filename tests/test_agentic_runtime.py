import json
import pytest

from agentic_runtime import (
    ConversationBuffer, ToolRegistry, ToolSpec, ToolValidationError,
    parse_tool_call, run_with_recovery,
)


def test_structured_tool_call_and_schema_validation():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="greet", description="Return a greeting",
        handler=lambda name: "Hello " + name,
        parameters={"type": "object", "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 30}
        }, "required": ["name"], "additionalProperties": False},
    ))
    name, args = parse_tool_call('{"name":"greet","arguments":{"name":"Ada"}}')
    result = registry.execute(name, args)
    assert result.ok and result.output == "Hello Ada"
    assert not registry.execute("greet", {"name": ""}).ok
    assert not registry.execute("missing", {}).ok


def test_approval_gate_prevents_execution():
    called = []
    registry = ToolRegistry()
    registry.register(ToolSpec("danger", "needs approval",
                               lambda: called.append(True), requires_approval=True))
    result = registry.execute("danger", {})
    assert not result.ok
    assert called == []
    assert registry.execute("danger", {}, approved=True).ok
    assert called == [True]


def test_parser_rejects_invalid_payload():
    with pytest.raises(ToolValidationError):
        parse_tool_call("not-json")
    with pytest.raises(ToolValidationError):
        parse_tool_call('{"name":"x","arguments":[]}')


def test_conversation_buffer_is_bounded_and_rejects_private_role():
    buffer = ConversationBuffer(max_messages=3, max_chars=100)
    for i in range(5):
        buffer.add("user", f"message {i}")
    assert len(buffer) == 3
    assert buffer.messages()[-1]["content"] == "message 4"
    with pytest.raises(ValueError):
        buffer.add("chain_of_thought", "private reasoning")


def test_recovery_loop_is_bounded_and_repairs():
    calls = {"n": 0}
    def operation():
        calls["n"] += 1
        return {"valid": False}
    def repair(previous, error, attempt):
        calls["n"] += 1
        return {"valid": True}
    report = run_with_recovery(operation, validate=lambda x: x["valid"],
                               repair=repair, max_attempts=3)
    assert report.success and report.attempts == 2
    assert calls["n"] == 2


def test_recovery_rejects_unbounded_attempts():
    with pytest.raises(ValueError):
        run_with_recovery(lambda: None, max_attempts=99)

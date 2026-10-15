"""Tests for bounded Hermes-style agent runtime primitives."""
import pytest

from agentic_runtime import AgenticRuntime, ToolSpec, ToolValidationError


def test_plan_classifies_coding_and_complexity():
    runtime = AgenticRuntime()
    plan = runtime.plan("Please debug this Python function and then write tests")
    assert plan.task_type == "coding"
    assert plan.complexity == "normal"
    assert len(plan.steps) >= 3


def test_system_guidance_has_plan_and_does_not_request_hidden_reasoning():
    runtime = AgenticRuntime()
    guidance = runtime.system_guidance(runtime.plan("Plan a project"), "technical")
    assert "Suggested checklist" in guidance
    assert "Do not reveal private hidden chain-of-thought" in guidance
    assert "technical detail" in guidance


def test_parse_hermes_style_calls_without_execution():
    runtime = AgenticRuntime()
    calls = runtime.parse_tool_calls(
        'before <tool_call>{"name":"lookup","args":{"query":"hello"}}</tool_call> after')
    assert calls == [{"name": "lookup", "args": {"query": "hello"}}]


def test_parse_json_object_and_ignore_invalid_payloads():
    runtime = AgenticRuntime()
    assert runtime.parse_tool_calls('{"name":"lookup","arguments":{"query":"x"}}')[0]["args"] == {"query": "x"}
    assert runtime.parse_tool_calls('<tool_call>{broken}</tool_call>') == []


def test_tool_validation_rejects_unregistered_unknown_and_missing_args():
    runtime = AgenticRuntime()
    specs = {"lookup": ToolSpec("lookup", "Search", {"query": str}, ("query",), False)}
    with pytest.raises(ToolValidationError, match="Unknown argument"):
        runtime.validate_tool_call({"name": "lookup", "args": {"query": "x", "extra": 1}}, specs)
    with pytest.raises(ToolValidationError, match="Missing required"):
        runtime.validate_tool_call({"name": "lookup", "args": {}}, specs)
    with pytest.raises(ToolValidationError, match="not registered"):
        runtime.validate_tool_call({"name": "shell", "args": {}}, specs)


def test_tool_validation_requires_approval_and_checks_types():
    runtime = AgenticRuntime()
    specs = {"write": ToolSpec("write", "Write", {"count": int}, ("count",), True)}
    with pytest.raises(ToolValidationError, match="approval"):
        runtime.validate_tool_call({"name": "write", "args": {"count": 1}}, specs)
    with pytest.raises(ToolValidationError, match="must be int"):
        runtime.validate_tool_call({"name": "write", "args": {"count": True}}, specs, approved=True)


def test_tool_execution_uses_only_registered_handler():
    runtime = AgenticRuntime()
    specs = {"lookup": ToolSpec("lookup", "Search", {"query": str}, ("query",), False)}
    result = runtime.execute_tool_call(
        {"name": "lookup", "args": {"query": "abc"}}, specs,
        {"lookup": lambda query: "found:" + query})
    assert result.ok and result.output == "found:abc"
    denied = runtime.execute_tool_call(
        {"name": "lookup", "args": {"query": "abc"}}, specs, {})
    assert not denied.ok and "no execution handler" in denied.error


def test_retry_never_replays_non_idempotent_operations():
    runtime = AgenticRuntime()
    calls = []
    def fail():
        calls.append(1)
        raise TimeoutError("timeout")
    with pytest.raises(TimeoutError):
        runtime.bounded_retry(fail, attempts=3, is_idempotent=False)
    assert len(calls) == 1


def test_retry_retries_transient_idempotent_operation():
    runtime = AgenticRuntime()
    calls = []
    def sometimes_fails():
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError("timeout")
        return "ok"
    assert runtime.bounded_retry(sometimes_fails, attempts=2, is_idempotent=True) == "ok"
    assert len(calls) == 2

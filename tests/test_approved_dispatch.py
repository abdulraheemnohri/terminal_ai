import pytest

from agentic_runtime import ToolRegistry, ToolSpec
from agent.approved_dispatch import execute_approved_operation
from command_control import CommandControl


def make_registry(handler):
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="browser.read_page", description="test", handler=handler,
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
            "additionalProperties": False,
        },
        requires_approval=True,
    ))
    return registry


def test_approved_operation_executes_once_with_exact_arguments(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    seen = []
    registry = make_registry(lambda **kwargs: seen.append(kwargs) or {"ok": True})
    operation = control.queue(
        "browser.read_page", "browser.read_page", {"url": "https://example.com"}
    )
    control.review(operation["id"], True, note="reviewed")
    result = execute_approved_operation(control, registry, operation["id"])

    assert result["status"] == "executed"
    assert len(seen) == 1
    assert control.get_operation(operation["id"])["status"] == "executed"
    with pytest.raises(ValueError):
        execute_approved_operation(control, registry, operation["id"])
    assert len(seen) == 1


def test_rejected_operation_never_executes(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    seen = []
    registry = make_registry(lambda **kwargs: seen.append(kwargs))
    operation = control.queue("browser.read_page", "browser.read_page", {"url": "https://example.com"})
    control.review(operation["id"], False, note="no")
    with pytest.raises(ValueError):
        execute_approved_operation(control, registry, operation["id"])
    assert seen == []


def test_failed_tool_consumes_approval(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    registry = make_registry(lambda **kwargs: (_ for _ in ()).throw(RuntimeError("test failure")))
    operation = control.queue("browser.read_page", "browser.read_page", {"url": "https://example.com"})
    control.review(operation["id"], True)
    result = execute_approved_operation(control, registry, operation["id"])
    assert result["status"] == "failed"
    assert control.get_operation(operation["id"])["status"] == "failed"

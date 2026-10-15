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



def test_claim_rejects_argument_mismatch(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    operation = control.queue(
        "browser.read_page", "browser.read_page", {"url": "https://example.com"}
    )
    control.review(operation["id"], True)
    with pytest.raises(ValueError, match="arguments do not match"):
        control.claim_approved(
            operation["id"], "browser.read_page", "browser.read_page",
            {"url": "https://attacker.invalid"},
        )
    # A mismatched claim cannot consume or rewrite the original approval.
    assert control.get_operation(operation["id"])["status"] == "approved"


def test_claim_rejects_replay_after_first_claim(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    operation = control.queue(
        "browser.read_page", "browser.read_page", {"url": "https://example.com"}
    )
    control.review(operation["id"], True)
    control.claim_approved(
        operation["id"], "browser.read_page", "browser.read_page",
        {"url": "https://example.com"},
    )
    with pytest.raises(ValueError, match="unused approval"):
        control.claim_approved(
            operation["id"], "browser.read_page", "browser.read_page",
            {"url": "https://example.com"},
        )

import pytest

from agentic_runtime import ToolRegistry, ToolSpec
from application.browser_dispatch import execute_approved_browser_operation
from command_control import CommandControl


class FakeRuntime:
    def __init__(self):
        self.closed = False
        self.registry = ToolRegistry()
        self.registry.register(ToolSpec(
            name="browser.read_page",
            description="test read page",
            handler=lambda url: {"visited": url},
            parameters={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
                "additionalProperties": False,
            },
            requires_approval=True,
        ))

    def close(self):
        self.closed = True


def queue_approved(control, tool="browser.read_page"):
    item = control.queue(tool, tool, {"url": "https://example.com"})
    control.review(item["id"], True, note="reviewed by operator")
    return item["id"]


def test_local_browser_dispatch_requires_explicit_confirmation(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    operation_id = queue_approved(control)
    created = []

    def factory(domains):
        created.append(domains)
        return FakeRuntime()

    with pytest.raises(ValueError, match="Explicit confirmation"):
        execute_approved_browser_operation(
            control, {"browser_allowed_domains": ["example.com"]}, operation_id,
            confirmed=False, runtime_factory=factory,
        )
    assert created == []
    assert control.get_operation(operation_id)["status"] == "approved"


def test_local_browser_dispatch_only_accepts_approved_browser_tools(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    operation_id = queue_approved(control, "workspace.read_file")
    created = []

    with pytest.raises(ValueError, match="browser tools only"):
        execute_approved_browser_operation(
            control, {"browser_allowed_domains": ["example.com"]}, operation_id,
            confirmed=True, runtime_factory=lambda domains: created.append(domains),
        )
    assert created == []
    assert control.get_operation(operation_id)["status"] == "approved"


def test_local_browser_dispatch_requires_allowlist(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    operation_id = queue_approved(control)
    created = []

    with pytest.raises(ValueError, match="domain allowlist"):
        execute_approved_browser_operation(
            control, {"browser_allowed_domains": []}, operation_id,
            confirmed=True, runtime_factory=lambda domains: created.append(domains),
        )
    assert created == []
    assert control.get_operation(operation_id)["status"] == "approved"


def test_local_browser_dispatch_executes_and_closes_runtime_once(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    operation_id = queue_approved(control)
    runtimes = []
    seen_domains = []

    def factory(domains):
        seen_domains.extend(domains)
        runtime = FakeRuntime()
        runtimes.append(runtime)
        return runtime

    result = execute_approved_browser_operation(
        control, {"browser_allowed_domains": ["example.com"]}, operation_id,
        confirmed=True, runtime_factory=factory,
    )
    assert result["status"] == "executed"
    assert result["tool"] == "browser.read_page"
    assert "https://example.com" in result["output"]
    assert seen_domains == ["example.com"]
    assert len(runtimes) == 1 and runtimes[0].closed is True
    assert control.get_operation(operation_id)["status"] == "executed"
    with pytest.raises(ValueError, match="unused approval"):
        execute_approved_browser_operation(
            control, {"browser_allowed_domains": ["example.com"]}, operation_id,
            confirmed=True, runtime_factory=factory,
        )
    assert len(runtimes) == 1


def test_local_browser_dispatch_requires_human_approval(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    item = control.queue("browser.read_page", "browser.read_page", {"url": "https://example.com"})
    created = []

    with pytest.raises(ValueError, match="unused human approval"):
        execute_approved_browser_operation(
            control, {"browser_allowed_domains": ["example.com"]}, item["id"],
            confirmed=True, runtime_factory=lambda domains: created.append(domains),
        )
    assert created == []

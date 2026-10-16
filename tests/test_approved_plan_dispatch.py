import pytest

from application.approved_plan_dispatch import prepare_plan_operation, validate_argv
from application.task_lifecycle import TaskLifecycleStore
from command_control import CommandControl
from workspace_tools import WorkspaceTools


def _task(lifecycle):
    return lifecycle.create(
        goal="Run tests and inspect the result",
        task_type="software_change",
        algorithm="test-driven-loop",
        risk="low",
        steps=["Run the project's test suite", "Review the test result"],
    )


def test_prepare_plan_operation_queues_and_links_without_execution(tmp_path):
    workspace = WorkspaceTools(tmp_path / "workspace")
    control = CommandControl(tmp_path / "control.sqlite3")
    lifecycle = TaskLifecycleStore(tmp_path / "tasks.sqlite3")
    task = _task(lifecycle)

    result = prepare_plan_operation(
        task_id=task["id"],
        argv=["pytest", "-q"],
        cwd=".",
        timeout=45,
        control=control,
        workspace=workspace,
        task_lifecycle=lifecycle,
    )

    assert result["execution_started"] is False
    assert result["operation"]["status"] == "pending"
    assert result["operation"]["arguments"] == {"argv": ["pytest", "-q"], "cwd": ".", "timeout": 45}
    assert result["task"]["status"] == "awaiting_approval"
    assert result["task"]["operation_id"] == result["operation"]["id"]
    assert control.get_operation(result["operation"]["id"])["status"] == "pending"
    assert control.verify_audit()["valid"] is True


def test_prepare_plan_operation_rejects_shell_syntax_and_blocked_commands(tmp_path):
    workspace = WorkspaceTools(tmp_path / "workspace")
    control = CommandControl(tmp_path / "control.sqlite3")
    lifecycle = TaskLifecycleStore(tmp_path / "tasks.sqlite3")
    task = _task(lifecycle)

    with pytest.raises(ValueError, match="Shell operators"):
        validate_argv(["python", "-c", "print(1)"])

    with pytest.raises(PermissionError, match="not permitted"):
        prepare_plan_operation(
            task_id=task["id"], argv=["rm", "-rf", "."], cwd=".", timeout=10,
            control=control, workspace=workspace, task_lifecycle=lifecycle,
        )
    assert control.list_pending("pending") == []


def test_prepare_plan_operation_rejects_workspace_escape_and_nonplanned_task(tmp_path):
    workspace = WorkspaceTools(tmp_path / "workspace")
    control = CommandControl(tmp_path / "control.sqlite3")
    lifecycle = TaskLifecycleStore(tmp_path / "tasks.sqlite3")
    task = _task(lifecycle)

    with pytest.raises(ValueError, match="escapes the configured workspace"):
        prepare_plan_operation(
            task_id=task["id"], argv=["pytest"], cwd="../", timeout=10,
            control=control, workspace=workspace, task_lifecycle=lifecycle,
        )

    queued = control.queue("terminal", "execute", {"argv": ["pytest"], "cwd": ".", "timeout": 10})
    lifecycle.link_operation(task["id"], queued)
    with pytest.raises(ValueError, match="unlinked planned task"):
        prepare_plan_operation(
            task_id=task["id"], argv=["pytest"], cwd=".", timeout=10,
            control=control, workspace=workspace, task_lifecycle=lifecycle,
        )


def test_learning_review_is_blocked_until_operation_is_executed_and_verified(tmp_path):
    workspace = WorkspaceTools(tmp_path / "workspace")
    control = CommandControl(tmp_path / "control.sqlite3")
    lifecycle = TaskLifecycleStore(tmp_path / "tasks.sqlite3")
    task = _task(lifecycle)
    prepared = prepare_plan_operation(
        task_id=task["id"], argv=["pytest", "-q"], cwd=".", timeout=45,
        control=control, workspace=workspace, task_lifecycle=lifecycle,
    )
    operation = prepared["operation"]

    with pytest.raises(ValueError, match="only independently verified"):
        lifecycle.review(task["id"], outcome="success", rating=5, reviewer="operator")

    control.review(operation["id"], True, "user", "Approved exact test command")
    claimed = control.claim_approved(
        operation["id"], "terminal", "execute", operation["arguments"]
    )
    assert claimed["status"] == "executing"
    control.finish_operation(operation["id"], success=True, note="exit=0")
    lifecycle.sync_operation(task["id"], control.get_operation(operation["id"]))

    with pytest.raises(ValueError, match="only independently verified"):
        lifecycle.review(task["id"], outcome="success", rating=5, reviewer="operator")

    lifecycle.verify(task["id"], passed=True, evidence="Test command returned exit code 0", verifier="operator")
    reviewed = lifecycle.review(task["id"], outcome="success", rating=5, reviewer="operator")
    assert reviewed["status"] == "reviewed"
    assert reviewed["review"]["verified"] is True

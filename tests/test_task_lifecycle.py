from application.task_lifecycle import TaskLifecycleStore


def test_lifecycle_requires_executed_operation_and_passing_verification(tmp_path):
    store = TaskLifecycleStore(tmp_path / "tasks.sqlite3")
    task = store.create(goal="Check service health", task_type="debugging",
                        algorithm="evidence-first", risk="read",
                        steps=["Inspect health", "Verify result"])
    assert task["status"] == "planned"

    pending = {"id": "op-1", "status": "pending", "tool": "workspace", "operation": "inspect"}
    task = store.link_operation(task["id"], pending)
    assert task["status"] == "awaiting_approval"
    try:
        store.verify(task["id"], passed=True, evidence="Health endpoint returned 200", verifier="operator")
    except ValueError as exc:
        assert "requires a linked operation recorded as executed" in str(exc)
    else:
        raise AssertionError("unexecuted task must not be verified")

    executed = {**pending, "status": "executed"}
    task = store.sync_operation(task["id"], executed)
    assert task["status"] == "executed"
    task = store.verify(task["id"], passed=True, evidence="Independent health check returned 200", verifier="operator")
    assert task["status"] == "verified"
    assert task["verification"]["passed"] is True
    task = store.review(task["id"], outcome="success", rating=5, reviewer="operator")
    assert task["status"] == "reviewed"
    assert task["review"]["verified"] is True


def test_failed_verification_cannot_be_reviewed_or_reset_by_operation_sync(tmp_path):
    store = TaskLifecycleStore(tmp_path / "tasks.sqlite3")
    task = store.create(goal="Check a regression", task_type="software_change",
                        algorithm="test-driven-loop", risk="low", steps=["Run regression test"])
    operation = {"id": "op-2", "status": "executed"}
    task = store.link_operation(task["id"], operation)
    task = store.verify(task["id"], passed=False, evidence="Regression test failed", verifier="operator")
    assert task["status"] == "failed"
    task = store.sync_operation(task["id"], operation)
    assert task["status"] == "failed"
    try:
        store.review(task["id"], outcome="failure", rating=1, reviewer="operator")
    except ValueError as exc:
        assert "only independently verified tasks" in str(exc)
    else:
        raise AssertionError("failed verification must not enter learning review")


def test_operation_can_only_be_linked_once(tmp_path):
    store = TaskLifecycleStore(tmp_path / "tasks.sqlite3")
    task = store.create(goal="Inspect config", task_type="research",
                        algorithm="direct-verify", risk="read", steps=["Read config"])
    store.link_operation(task["id"], {"id": "op-3", "status": "pending"})
    try:
        store.link_operation(task["id"], {"id": "op-4", "status": "approved"})
    except ValueError as exc:
        assert "linked once" in str(exc)
    else:
        raise AssertionError("task must not be rebound to a different operation")

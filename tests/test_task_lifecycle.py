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



def test_recovery_proposals_are_bounded_and_never_execute(tmp_path):
    from application.recovery_proposals import RecoveryProposalStore

    store = RecoveryProposalStore(tmp_path / "recovery.sqlite3")
    proposal = store.propose(task_id="task-a", failure_category="timeout",
                             error_summary="Connection timed out")
    assert proposal["attempt"] == 1
    assert proposal["status"] == "proposed"
    assert proposal["may_retry_after_review"] is True
    assert proposal["execution_started"] is False
    approved = store.review(task_id="task-a", proposal_id=proposal["id"],
                            decision="approve", reviewer="operator", note="Checked idempotency")
    assert approved["status"] == "approved_for_replanning"
    assert approved["execution_started"] is False
    for _ in range(2):
        store.propose(task_id="task-a", failure_category="transient_network",
                      error_summary="Temporary network failure")
    try:
        store.propose(task_id="task-a", failure_category="timeout", error_summary="Fourth attempt")
    except ValueError as exc:
        assert "maximum 3" in str(exc)
    else:
        raise AssertionError("proposal count must be capped at three")


def test_recovery_policy_blocks_unsafe_retry_approval(tmp_path):
    from application.recovery_proposals import RecoveryProposalStore

    store = RecoveryProposalStore(tmp_path / "recovery.sqlite3")
    unsafe = store.propose(task_id="task-b", failure_category="permission",
                           error_summary="Access denied")
    assert unsafe["retry_policy"] == "no_retry_recommended"
    try:
        store.review(task_id="task-b", proposal_id=unsafe["id"],
                     decision="approve", reviewer="operator")
    except ValueError as exc:
        assert "not eligible for retry approval" in str(exc)
    else:
        raise AssertionError("permission failures must not be approved as retries")
    rejected = store.review(task_id="task-b", proposal_id=unsafe["id"],
                            decision="reject", reviewer="operator")
    assert rejected["status"] == "rejected"
    assert rejected["execution_started"] is False


def test_recovery_proposal_validation_and_single_review(tmp_path):
    from application.recovery_proposals import RecoveryProposalStore

    store = RecoveryProposalStore(tmp_path / "recovery.sqlite3")
    try:
        store.propose(task_id="task-c", failure_category="made_up",
                      error_summary="Bad category")
    except ValueError as exc:
        assert "failure_category" in str(exc)
    else:
        raise AssertionError("unknown categories must be rejected")
    proposal = store.propose(task_id="task-c", failure_category="validation",
                             error_summary="Input schema mismatch")
    approved = store.review(task_id="task-c", proposal_id=proposal["id"],
                            decision="approve", reviewer="operator")
    assert approved["retry_policy"] == "requires_change_and_fresh_approval"
    try:
        store.review(task_id="task-c", proposal_id=proposal["id"],
                     decision="reject", reviewer="operator")
    except ValueError as exc:
        assert "already been reviewed" in str(exc)
    else:
        raise AssertionError("proposal review must be single-use")



def test_approved_recovery_proposal_queues_once_for_fresh_operation(tmp_path):
    from application.recovery_proposals import RecoveryProposalStore

    store = RecoveryProposalStore(tmp_path / "recovery.sqlite3")
    proposal = store.propose(task_id="task-q", failure_category="timeout",
                             error_summary="Timed out")
    approved = store.review(task_id="task-q", proposal_id=proposal["id"],
                            decision="approve", reviewer="operator")
    assert approved["status"] == "approved_for_replanning"

    reserved = store.prepare_operation_queue(task_id="task-q", proposal_id=proposal["id"])
    assert reserved["status"] == "queueing"
    assert reserved["execution_started"] is False
    queued = store.attach_new_operation(task_id="task-q", proposal_id=proposal["id"],
                                        operation_id="new-operation-123")
    assert queued["status"] == "operation_queued"
    assert queued["new_operation_id"] == "new-operation-123"
    assert queued["execution_started"] is False

    try:
        store.prepare_operation_queue(task_id="task-q", proposal_id=proposal["id"])
    except ValueError as exc:
        assert "approved for replanning" in str(exc)
    else:
        raise AssertionError("an operation must not be queued twice from one proposal")


def test_recovery_operation_queue_reservation_can_be_released_on_queue_failure(tmp_path):
    from application.recovery_proposals import RecoveryProposalStore

    store = RecoveryProposalStore(tmp_path / "recovery.sqlite3")
    proposal = store.propose(task_id="task-r", failure_category="transient_network",
                             error_summary="Network reset")
    store.review(task_id="task-r", proposal_id=proposal["id"],
                 decision="approve", reviewer="operator")
    store.prepare_operation_queue(task_id="task-r", proposal_id=proposal["id"])
    store.release_operation_queue(task_id="task-r", proposal_id=proposal["id"])
    retried = store.prepare_operation_queue(task_id="task-r", proposal_id=proposal["id"])
    assert retried["status"] == "queueing"



def test_failed_recovery_verification_cannot_be_reviewed_for_learning(tmp_path):
    from application.recovery_proposals import RecoveryProposalStore

    store = RecoveryProposalStore(tmp_path / "recovery.sqlite3")
    proposal = store.propose(task_id="task-failed-verify", failure_category="timeout",
                             error_summary="Request timed out")
    store.review(task_id="task-failed-verify", proposal_id=proposal["id"],
                 decision="approve", reviewer="operator")
    store.prepare_operation_queue(task_id="task-failed-verify", proposal_id=proposal["id"])
    store.attach_new_operation(task_id="task-failed-verify", proposal_id=proposal["id"],
                               operation_id="operation-new")
    failed = store.record_verification(task_id="task-failed-verify", proposal_id=proposal["id"],
                                       passed=False, evidence="Independent check failed",
                                       verifier="operator")
    assert failed["status"] == "verification_failed"
    try:
        store.review_verified_outcome(task_id="task-failed-verify", proposal_id=proposal["id"],
                                      outcome="failure", rating=1, reviewer="operator",
                                      note="Failed verification", learning_record_id=1)
    except ValueError as exc:
        assert "passing verified recovery" in str(exc)
    else:
        raise AssertionError("failed recovery verification must not enter learning")

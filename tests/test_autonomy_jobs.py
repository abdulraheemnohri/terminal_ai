import asyncio

from application.autonomy_jobs import AutonomyJobQueue, AutonomyJobWorker


def test_queue_validates_allowlisted_actions_and_bounds(tmp_path):
    queue = AutonomyJobQueue(tmp_path / "jobs.sqlite3")
    try:
        queue.submit({"goal": "inspect workspace", "action": "shell"})
    except ValueError as exc:
        assert "registered safe actions" in str(exc)
    else:
        raise AssertionError("unregistered action should be rejected")

    try:
        queue.submit({"goal": "x", "complexity": True})
    except ValueError as exc:
        assert "complexity" in str(exc)
    else:
        raise AssertionError("boolean complexity should be rejected")


def test_queue_claim_finish_and_cancel(tmp_path):
    queue = AutonomyJobQueue(tmp_path / "jobs.sqlite3")
    queued = queue.submit({"goal": "summarize known facts", "action": "world_model_summary"})
    claimed = queue.claim()
    assert claimed["id"] == queued["id"]
    assert claimed["status"] == "running"
    assert claimed["attempts"] == 1

    queue.update_progress(claimed["id"], "Reading safe local evidence")
    assert queue.finish(claimed["id"], {"run": {"status": "completed"}})
    assert queue.get(claimed["id"])["status"] == "completed"

    next_job = queue.submit({"goal": "inspect workspace"})
    cancelled = queue.cancel(next_job["id"])
    assert cancelled["status"] == "cancelled"
    assert queue.claim() is None


def test_queue_retries_once_then_fails(tmp_path):
    queue = AutonomyJobQueue(tmp_path / "jobs.sqlite3")
    job = queue.submit({"goal": "inspect workspace"})
    first = queue.claim()
    assert first["id"] == job["id"]
    assert queue.fail(job["id"], "temporary") == "queued"
    second = queue.claim()
    assert second["attempts"] == 2
    assert queue.fail(job["id"], "still broken") == "failed"
    assert queue.get(job["id"])["status"] == "failed"


def test_worker_processes_only_bounded_decision_callable(tmp_path):
    queue = AutonomyJobQueue(tmp_path / "jobs.sqlite3")
    audits = []
    queue.submit({"goal": "inspect workspace", "action": "workspace_overview"})
    worker = AutonomyJobWorker(
        queue,
        lambda **payload: {"run": {"status": "completed", "goal": payload["goal"]}},
        lambda *args: audits.append(args),
        poll_seconds=0.2,
    )

    async def run_once():
        await worker.start()
        for _ in range(30):
            job = queue.list()[0]
            if job["status"] == "completed":
                break
            await asyncio.sleep(0.05)
        await worker.stop()
        return queue.list()[0]

    result = asyncio.run(run_once())
    assert result["status"] == "completed"
    assert result["result"]["run"]["goal"] == "inspect workspace"
    assert audits

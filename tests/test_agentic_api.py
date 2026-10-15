from routers.agentic import PersistentWorldModel
from terminal_ai_runtime import AdaptivePlanner


def test_world_model_persists_evidence(tmp_path):
    path = tmp_path / "world_model.json"
    first = PersistentWorldModel(path)
    saved = first.observe("service", "health", {"state": "healthy"},
                          "diagnostics", 0.9, None)
    assert saved["confidence"] == 0.9

    second = PersistentWorldModel(path)
    facts = second.model.query("service")
    assert len(facts) == 1
    assert facts[0].predicate == "health"
    assert facts[0].value == {"state": "healthy"}
    assert facts[0].source == "diagnostics"


def test_planner_marks_external_side_effects_for_review():
    plan = AdaptivePlanner().plan(
        "submit a form", complexity=2, risk="low",
        has_external_side_effects=True,
    )
    assert plan.needs_approval is True
    assert plan.strategy == "plan-review-execute"


def test_world_model_recovers_from_invalid_json(tmp_path):
    path = tmp_path / "world_model.json"
    path.write_text("{not-json", encoding="utf-8")
    model = PersistentWorldModel(path)
    assert model.model.query() == []


def test_world_model_does_not_extend_expiry_after_restart(tmp_path):
    import time
    import json

    path = tmp_path / "world_model.json"
    first = PersistentWorldModel(path)
    first.observe("cache", "freshness", "temporary", "test", 0.8, 1)
    # Force the persisted absolute expiry into the past, as if the app was offline.
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[0]["expires_at"] = time.time() - 10
    path.write_text(json.dumps(payload), encoding="utf-8")

    second = PersistentWorldModel(path)
    assert second.model.query("cache") == []



def test_plan_exposes_adaptive_signals_without_starting_execution():
    from litestar.testing import TestClient
    from app import app

    with TestClient(app=app) as client:
        response = client.post("/api/agentic/plan", json={
            "goal": "Research the latest browser automation tools",
            "risk": "low",
            "complexity": 3,
            "evidence_available": False,
        })
    assert response.status_code == 201
    payload = response.json()
    assert payload["execution_started"] is False
    assert payload["plan"]["adaptive_signals"]["algorithm"] == "evidence-first"
    assert payload["plan"]["adaptive_signals"]["task_type"] == "research"


def test_plan_rejects_non_boolean_evidence_flag():
    from litestar.testing import TestClient
    from app import app

    with TestClient(app=app) as client:
        response = client.post("/api/agentic/plan", json={
            "goal": "Inspect the project",
            "evidence_available": "yes",
        })
    assert response.status_code == 400



def test_learning_api_requires_verified_outcome_and_returns_summary():
    from litestar.testing import TestClient
    from app import app

    with TestClient(app=app) as client:
        rejected = client.post("/api/agentic/learning/outcome", json={
            "task_type": "writing", "algorithm": "direct-verify",
            "outcome": "success", "rating": 5, "verified": False,
        })
        assert rejected.status_code == 400
        accepted = client.post("/api/agentic/learning/outcome", json={
            "task_type": "writing", "algorithm": "direct-verify",
            "outcome": "success", "rating": 5, "verified": True,
        })
        assert accepted.status_code == 201
        assert accepted.json()["permissions_changed"] is False
        summary = client.get("/api/agentic/learning/summary")
    assert summary.status_code == 200
    assert summary.json()["count"] >= 1



def test_skill_evolution_api_requires_validate_then_approval():
    from litestar.testing import TestClient
    from app import app

    with TestClient(app=app) as client:
        created = client.post("/api/agentic/skills/proposals", json={
            "name": "Review API test skill",
            "task_type": "debugging",
            "rationale": "A repeatable test workflow helps diagnose regressions.",
            "steps": ["Reproduce the failure", "Add a regression test", "Run the focused test"],
            "evidence_summary": "Test-only proposal; evidence is a concise operator summary.",
        })
        assert created.status_code == 201
        proposal_id = created.json()["proposal"]["id"]
        assert created.json()["permissions_changed"] is False
        assert created.json()["proposal"]["status"] == "proposed"

        premature = client.post(f"/api/agentic/skills/proposals/{proposal_id}/approve", json={"note": "not yet"})
        assert premature.status_code == 409

        validated = client.post(f"/api/agentic/skills/proposals/{proposal_id}/validate")
        assert validated.status_code == 201
        assert validated.json()["static_validation_only"] is True

        approved = client.post(f"/api/agentic/skills/proposals/{proposal_id}/approve", json={"note": "Human reviewed"})
        assert approved.status_code == 201
        assert approved.json()["approved_by_human"] is True
        assert approved.json()["execution_started"] is False

        promoted = client.post(f"/api/agentic/skills/proposals/{proposal_id}/promote", json={"note": "Approved catalog"})
        assert promoted.status_code == 201
        assert promoted.json()["proposal"]["status"] == "promoted"
        assert promoted.json()["permissions_changed"] is False

        listed = client.get("/api/agentic/skills/proposals?status=promoted")
        assert listed.status_code == 200
        assert any(item["id"] == proposal_id for item in listed.json()["proposals"])


def test_skill_evolution_api_rejects_executable_skill_text():
    from litestar.testing import TestClient
    from app import app

    with TestClient(app=app) as client:
        response = client.post("/api/agentic/skills/proposals", json={
            "name": "Unsafe API test",
            "task_type": "debugging",
            "rationale": "Unsafe content should never be accepted.",
            "steps": ["Use eval(user_input) to execute the workflow"],
            "evidence_summary": "No evidence",
        })
    assert response.status_code == 400

def test_reviewed_learning_generates_only_an_unapproved_skill_draft():
    from litestar.testing import TestClient
    from app import app

    with TestClient(app=app) as client:
        for _ in range(3):
            outcome = client.post("/api/agentic/learning/outcome", json={
                "task_type": "browser_work",
                "algorithm": "observe-act-verify",
                "outcome": "success",
                "rating": 5,
                "verified": True,
            })
            assert outcome.status_code == 201

        response = client.post("/api/agentic/skills/proposals/from-learning", json={})

    assert response.status_code == 201
    payload = response.json()
    proposal = payload["proposal"]
    assert payload["generated_from_reviewed_outcomes"] is True
    assert payload["execution_started"] is False
    assert payload["permissions_changed"] is False
    assert proposal["status"] == "proposed"
    assert proposal["executable"] is False
    assert any("human approval" in step.lower() for step in proposal["steps"])

def test_recurring_reviewed_failures_generate_recovery_draft_not_execution():
    from litestar.testing import TestClient
    from app import app

    with TestClient(app=app) as client:
        for _ in range(3):
            outcome = client.post("/api/agentic/learning/outcome", json={
                "task_type": "software_change",
                "algorithm": "test-driven-loop",
                "outcome": "failure",
                "rating": 1,
                "verified": True,
            })
            assert outcome.status_code == 201

        response = client.post("/api/agentic/skills/proposals/from-learning", json={})

    assert response.status_code == 201
    payload = response.json()
    assert payload["pattern"] == "recurring_failure"
    assert payload["proposal"]["name"].startswith("Recovery workflow for ")
    assert payload["proposal"]["status"] == "proposed"
    assert payload["proposal"]["executable"] is False
    assert payload["execution_started"] is False
    assert payload["permissions_changed"] is False



def test_agentic_console_status_and_world_observation_api():
    from litestar.testing import TestClient
    from app import app

    with TestClient(app=app) as client:
        status = client.get("/api/agentic/status")
        assert status.status_code == 200
        payload = status.json()
        assert payload["global_auto_execution"] is False
        assert payload["self_consciousness"].startswith("operational introspection")
        summary = client.get("/api/agentic/learning/summary")
        assert summary.status_code == 200
        assert "groups" in summary.json()
        observed = client.post("/api/agentic/world-model/observe", json={
            "subject": "console-test-service",
            "predicate": "health",
            "value": {"state": "test-only"},
            "source": "automated-test",
            "confidence": 0.75,
            "ttl_seconds": 60,
        })
        assert observed.status_code == 201
        assert observed.json()["stored"] is True
        facts = client.get("/api/agentic/world-model?subject=console-test-service")
        assert facts.status_code == 200
        assert facts.json()["count"] >= 1
        assert any(f["predicate"] == "health" for f in facts.json()["facts"])
        pending = client.get("/api/control/pending?status=pending&limit=100")
        assert pending.status_code == 200
        assert isinstance(pending.json()["operations"], list)


def test_task_lifecycle_api_links_existing_approval_without_execution():
    from litestar.testing import TestClient
    from app import app

    with TestClient(app=app) as client:
        planned = client.post("/api/agentic/tasks", json={
            "goal": "Inspect application health and verify it",
            "risk": "read",
            "complexity": 2,
            "has_external_side_effects": False,
            "evidence_available": False,
        })
        assert planned.status_code == 201
        task = planned.json()["task"]
        assert task["status"] == "planned"
        assert planned.json()["execution_started"] is False

        queued = client.post("/api/control/pending", json={
            "tool": "workspace", "operation": "inspect", "arguments": {"path": "README.md"}
        })
        assert queued.status_code == 201
        operation_id = queued.json()["operation"]["id"]

        linked = client.post(f"/api/agentic/tasks/{task['id']}/operation", json={
            "operation_id": operation_id
        })
        assert linked.status_code == 201
        assert linked.json()["task"]["status"] == "awaiting_approval"
        assert linked.json()["execution_started"] is False

        blocked = client.post(f"/api/agentic/tasks/{task['id']}/verify", json={
            "passed": True, "evidence": "A check was performed", "verifier": "operator"
        })
        assert blocked.status_code == 409

        task_status = client.get(f"/api/agentic/tasks/{task['id']}")
        assert task_status.status_code == 200
        assert task_status.json()["task"]["operation_id"] == operation_id

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

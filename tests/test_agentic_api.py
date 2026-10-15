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

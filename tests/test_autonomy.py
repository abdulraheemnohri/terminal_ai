from types import SimpleNamespace

import pytest

from application.autonomy import AutonomyEngine, AutonomyStore
from application.learning import LearningStore
from application.task_intelligence import analyze_task
from application.task_lifecycle import TaskLifecycleStore


class FakeWorkspace:
    def list_files(self, relative="."):
        return [{"name": "README.md", "directory": False, "size": 100}]


class FakeWorldModel:
    class Model:
        def query(self):
            return [SimpleNamespace(subject="service", predicate="status", value="healthy")]

    model = Model()


class FakePlanner:
    def plan(self, goal, *, complexity, risk, has_external_side_effects):
        return SimpleNamespace(
            strategy="bounded-test-plan",
            steps=["Inspect available evidence", "Verify the outcome"],
            risk=risk,
            needs_approval=has_external_side_effects or risk in {"medium", "high", "critical"},
            rationale="Test plan",
        )


@pytest.fixture
def engine(tmp_path):
    learning = LearningStore(tmp_path / "learning.sqlite3")
    lifecycle = TaskLifecycleStore(tmp_path / "tasks.sqlite3")
    store = AutonomyStore(tmp_path / "autonomy.sqlite3")
    audits = []
    return AutonomyEngine(
        store=store,
        workspace=FakeWorkspace(),
        learning=learning,
        world_model=FakeWorldModel(),
        planner=FakePlanner(),
        analyze=analyze_task,
        task_lifecycle=lifecycle,
        audit=lambda *args: audits.append(args),
    ), store, lifecycle, audits


def test_autonomy_runs_registered_read_only_action_without_review(engine):
    agent, store, _, audits = engine
    result = agent.run(goal="Inspect workspace", action="workspace_overview")
    assert result["run"]["status"] == "completed"
    assert result["run"]["decision"] == "auto_execute_allowlisted_read_only"
    assert result["run"]["result"]["files"][0]["name"] == "README.md"
    assert result["autonomy"]["permissions_changed"] is False
    assert store.summary()["count"] == 1
    assert audits


def test_autonomy_plans_mutating_work_but_does_not_execute(engine):
    agent, _, lifecycle, _ = engine
    result = agent.run(goal="Write a new configuration file", action="workspace_overview")
    assert result["run"]["action"] == "plan_task"
    assert result["run"]["status"] == "awaiting_approval"
    assert result["run"]["result"]["execution_started"] is False
    assert result["run"]["decision"] == "plan_and_defer_side_effects"
    assert lifecycle.get(result["run"]["result"]["task"]["id"])["status"] == "planned"


def test_autonomy_rejects_unregistered_actions(engine):
    agent, _, _, _ = engine
    with pytest.raises(ValueError, match="registered safe actions"):
        agent.run(goal="do something", action="run_shell_command")


def test_autonomy_validates_bounds(engine):
    agent, _, _, _ = engine
    with pytest.raises(ValueError, match="non-empty"):
        agent.run(goal=" ")
    with pytest.raises(ValueError, match="complexity"):
        agent.run(goal="Inspect workspace", complexity=True)


def test_autonomy_creates_plan_for_general_goal_without_claiming_execution(engine):
    agent, _, _, _ = engine
    result = agent.run(goal="Research a solution to the task")
    assert result["run"]["action"] == "plan_task"
    assert result["run"]["result"]["execution_started"] is False
    assert result["run"]["status"] in {"planned", "awaiting_approval"}

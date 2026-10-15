from pathlib import Path

from litestar.testing import TestClient

import app as web_app


def test_session_create_select_delete_round_trip(monkeypatch, tmp_path):
    original_manager = web_app.core.SessionManager
    monkeypatch.setattr(web_app.core, "SessionManager", lambda: original_manager(tmp_path / "sessions"))
    monkeypatch.setattr(web_app, "_ACTIVE_SESSION", "web-session")
    with TestClient(app=web_app.app) as client:
        created = client.post("/api/sessions/new", json={"name": "regression-test"})
        listed = client.get("/api/sessions")
        selected = client.post("/api/sessions/select", json={"name": "regression-test"})
        deleted = client.post("/api/sessions/delete", json={"name": "regression-test"})
    assert created.status_code == 201
    assert created.json()["active_session"] == "regression-test"
    assert listed.status_code == 200
    assert "regression-test" in listed.json()["sessions"]
    assert selected.status_code == 201
    assert selected.json()["history"] == []
    assert deleted.status_code == 201
    assert "regression-test" not in original_manager(tmp_path / "sessions").list_sessions()


def test_session_rejects_path_separators():
    with TestClient(app=web_app.app) as client:
        created = client.post("/api/sessions/new", json={"name": "../outside"})
        selected = client.post("/api/sessions/select", json={"name": "../outside"})
    assert created.status_code == 400
    assert selected.status_code == 400


def test_ai_settings_assistant_requires_a_request():
    with TestClient(app=web_app.app) as client:
        response = client.post("/api/ai/settings/propose", json={"request": " "})
    assert response.status_code == 400


def test_ai_skill_generator_validates_task_before_model_call():
    with TestClient(app=web_app.app) as client:
        response = client.post("/api/skills/generate", json={"task": ""})
    assert response.status_code == 400


def test_ui_exposes_session_and_ai_controls():
    with TestClient(app=web_app.app) as client:
        html = client.get("/")
        js = client.get("/static/app.js")
    assert html.status_code == 200
    assert "session-new-form" in html.text
    assert "skill-generate-form" in html.text
    assert "ai-settings-form" in html.text
    assert js.status_code == 200
    assert "/api/sessions/select" in js.text
    assert "/api/ai/settings/propose" in js.text


def test_session_rejects_single_backslash():
    with TestClient(app=web_app.app) as client:
        response = client.post("/api/sessions/select", json={"name": "folder\\\\session"})
    assert response.status_code == 400


def test_ai_settings_proposal_clamps_numeric_values(monkeypatch):
    class FakeBackend:
        def stream(self, *args, **kwargs):
            yield '{"changes":{"max_ctx_chars":999999,"self_checkpoint_retention":999,"self_evaluation_interval_hours":9999},"explanation":"test"}'

    class FakeAgent:
        backend = FakeBackend()

    monkeypatch.setattr(web_app, "_get_agent", lambda: FakeAgent())
    with TestClient(app=web_app.app) as client:
        response = client.post("/api/ai/settings/propose", json={"request": "Use larger limits"})
    assert response.status_code == 201
    changes = response.json()["changes"]
    assert changes["max_ctx_chars"] == 50000
    assert changes["self_checkpoint_retention"] == 30
    assert changes["self_evaluation_interval_hours"] == 168


def test_selfx_event_is_persisted(tmp_path):
    from selfx_engine import SelfXEngine

    engine = SelfXEngine(tmp_path / "state", tmp_path / "models", tmp_path)
    event = engine.record_event("test", "bounded maintenance event")
    assert event["kind"] == "test"
    assert engine.status()["events"][0]["summary"] == "bounded maintenance event"


def test_checkpoint_retention_removes_stale_manifests_and_directories(tmp_path):
    from selfx_engine import SelfXEngine

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "memory.json").write_text("{}", encoding="utf-8")
    engine = SelfXEngine(state_dir, tmp_path / "models", tmp_path)
    for _ in range(3):
        engine.create_checkpoint()
    result = engine.prune_checkpoints(2)
    state = engine.status()
    checkpoint_dirs = [p for p in engine.backup_dir.iterdir() if p.is_dir()]
    assert result["retained"] == 2
    assert len(checkpoint_dirs) == 2
    assert len(state["checkpoints"]) == 2


def test_settings_api_rejects_wrong_boolean_types_and_unknown_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(web_app, "WEB_SETTINGS", tmp_path / "settings.json")
    with TestClient(app=web_app.app) as client:
        wrong_type = client.patch("/api/settings", json={"self_autonomous_enabled": "false"})
        unknown = client.patch("/api/settings", json={"run_any_command": True})
    assert wrong_type.status_code == 400
    assert unknown.status_code == 400


def test_settings_api_persists_bounded_autonomy_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(web_app, "WEB_SETTINGS", tmp_path / "settings.json")
    with TestClient(app=web_app.app) as client:
        response = client.patch("/api/settings", json={
            "self_autonomy_profile": "goal-driven",
            "self_autonomous_enabled": True,
            "self_goal_generation_enabled": True,
            "self_max_goals_per_cycle": 99,
            "self_checkpoint_interval_hours": 8,
            "self_auto_checkpoint": False,
            "tool_approval_required": True,
        })
    assert response.status_code == 200
    settings = response.json()
    assert settings["self_autonomy_profile"] == "goal-driven"
    assert settings["self_max_goals_per_cycle"] == 20
    assert settings["self_checkpoint_interval_hours"] == 8
    assert settings["tool_approval_required"] is True


def test_settings_ui_has_autonomy_profiles_and_safe_reset():
    with TestClient(app=web_app.app) as client:
        html = client.get("/")
        js = client.get("/static/app.js")
        css = client.get("/static/app.css")
    assert html.status_code == 200
    assert 'id="setting-autonomy-profile"' in html.text
    assert 'id="setting-goal-generation"' in html.text
    assert 'id="reset-autonomy-settings"' in html.text
    assert "settings-section" in css.text
    assert "Reset autonomy to safe defaults" in js.text


def test_manual_maintenance_respects_disabled_maintenance(monkeypatch):
    monkeypatch.setattr(web_app, "_read_settings", lambda: {"self_maintenance_enabled": False})
    with TestClient(app=web_app.app) as client:
        response = client.post("/api/selfx/maintenance/run")
    assert response.status_code == 400


def test_manual_maintenance_is_exposed_in_settings_ui():
    with TestClient(app=web_app.app) as client:
        html = client.get("/")
        js = client.get("/static/app.js")
    assert 'id="run-maintenance-now"' in html.text
    assert "/api/selfx/maintenance/run" in js.text


def test_settings_loader_recovers_from_malformed_persisted_values(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        '{"self_autonomous_enabled":"false","self_checkpoint_interval_hours":9999,'
        '"self_autonomy_profile":"unrestricted","tool_approval_required":null}',
        encoding="utf-8",
    )
    monkeypatch.setattr(web_app, "WEB_SETTINGS", settings_path)
    settings = web_app._read_settings()
    assert settings["self_autonomous_enabled"] is False
    assert settings["self_checkpoint_interval_hours"] == 168
    assert settings["self_autonomy_profile"] == "maintain"
    assert settings["tool_approval_required"] is True

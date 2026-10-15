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

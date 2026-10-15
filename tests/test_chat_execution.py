from litestar.testing import TestClient

import app as web_app
import terminal_ai as core


class FakeBackend:
    label = "fake-local-backend"


class FakeAgent:
    def __init__(self):
        self.backend = FakeBackend()
        self.history = []
        self.session_mgr = None

    def turn(self, message):
        self.history.extend([core.Msg("user", message), core.Msg("assistant", "A focused test answer.")])
        return "A focused test answer."


def test_chat_response_includes_execution_trace_and_request_metadata(monkeypatch):
    agent = FakeAgent()
    monkeypatch.setattr(web_app, "_get_agent", lambda: agent)
    with TestClient(app=web_app.app) as client:
        response = client.post("/api/chat", json={"message": "Say hello"})
        runs_response = client.get("/api/chat/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "A focused test answer."
    assert payload["request_id"]
    assert payload["backend"] == "fake-local-backend"
    assert payload["session"]
    assert payload["persistence"] == "not_configured"
    assert payload["plan"]["task_type"] == "conversation"
    assert payload["agent_capabilities"]["planning"] is True
    assert payload["agent_capabilities"]["structured_tool_calling"] is False
    assert [step["name"] for step in payload["execution"]] == [
        "request_received",
        "request_serialized",
        "backend_resolved",
        "task_planning",
        "inference",
        "long_term_archive",
        "history_persistence",
        "response_ready",
    ]
    assert all("elapsed_ms" in step for step in payload["execution"])
    assert runs_response.status_code == 200
    runs = runs_response.json()["runs"]
    matching = next(run for run in runs if run["request_id"] == payload["request_id"])
    assert matching["status"] == "completed"
    assert "prompt" not in matching
    assert "answer" not in matching


def test_chat_rejects_empty_and_oversized_messages():
    with TestClient(app=web_app.app) as client:
        empty = client.post("/api/chat", json={"message": "   "})
        oversized = client.post("/api/chat", json={"message": "x" * 20001})

    assert empty.status_code == 400
    assert oversized.status_code == 413


def test_chat_run_history_endpoint_is_available_without_model():
    with TestClient(app=web_app.app) as client:
        response = client.get("/api/chat/runs")

    assert response.status_code == 200
    assert isinstance(response.json()["runs"], list)
    assert response.json()["retention_limit"] == 50


def test_advanced_chat_controls_and_script_are_served():
    with TestClient(app=web_app.app) as client:
        page = client.get("/chat")
        script = client.get("/static/chat-enhancements.js")

    assert page.status_code == 200
    assert "chat-export-md" in page.text
    assert "chat-setting-font" in page.text
    assert "chat-execution-trace" in page.text
    assert script.status_code == 200
    assert "sendMessage" in script.text
    assert "localStorage" in script.text



def test_safe_web_tool_registry_rejects_unlisted_tools():
    registry = web_app.SafeWebToolRegistry(object())
    assert registry.call("shell", {"cmd": "echo unsafe"}).startswith("error:")
    assert registry.call("write_file", {"path": "x", "content": "bad"}).startswith("error:")


def test_agent_settings_validate_styles_and_boolean_types(monkeypatch, tmp_path):
    monkeypatch.setattr(web_app, "WEB_SETTINGS", tmp_path / "web_settings.json")
    with TestClient(app=web_app.app) as client:
        good = client.patch("/api/settings", json={
            "agentic_planning_enabled": True,
            "agent_self_correction_enabled": False,
            "agent_tool_calling_enabled": True,
            "agent_response_style": "technical",
        })
        bad_style = client.patch("/api/settings", json={"agent_response_style": "mind-reader"})
        bad_type = client.patch("/api/settings", json={"agent_tool_calling_enabled": "yes"})
    assert good.status_code == 200
    assert good.json()["agent_response_style"] == "technical"
    assert good.json()["agent_tool_calling_enabled"] is True
    assert bad_style.status_code == 400
    assert bad_type.status_code == 400

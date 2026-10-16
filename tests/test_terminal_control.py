from litestar.testing import TestClient

from app import app


def test_terminal_status_exposes_approval_and_policy():
    with TestClient(app=app) as client:
        response = client.get("/api/terminal/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["approval_required"] is True
    assert payload["auto_execute"] is False
    assert payload["execution_mode"] == "argv-only; shell disabled"
    assert "python3" in payload["allowlist"]


def test_terminal_queue_rejects_shell_chaining():
    with TestClient(app=app) as client:
        response = client.post("/api/terminal/queue", json={
            "argv": ["python3", "&&", "whoami"],
            "cwd": ".",
            "timeout": 5,
        })
    assert response.status_code == 400


def test_terminal_queue_rejects_commands_outside_allowlist():
    with TestClient(app=app) as client:
        response = client.post("/api/terminal/queue", json={
            "argv": ["not-an-allowed-command"],
            "cwd": ".",
            "timeout": 5,
        })
    assert response.status_code == 403


def test_terminal_queue_rejects_workspace_escape():
    with TestClient(app=app) as client:
        response = client.post("/api/terminal/queue", json={
            "argv": ["pwd"],
            "cwd": "../",
            "timeout": 5,
        })
    assert response.status_code == 400

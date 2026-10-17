from litestar.testing import TestClient
from app import app


def test_modular_command_control_router_is_registered():
    with TestClient(app=app) as client:
        policy = client.get("/api/control/policy")
        queue = client.post("/api/control/pending", json={
            "tool": "workspace", "operation": "inspect", "arguments": {"path": "README.md"}
        })
    assert policy.status_code == 200
    assert policy.json()["execution_enabled"] is False
    assert queue.status_code == 201 or queue.status_code == 200
    operation = queue.json()["operation"]
    assert operation["status"] == "pending"


def test_command_control_router_rejects_invalid_structured_payloads():
    with TestClient(app=app) as client:
        invalid_policy = client.patch("/api/control/policy", json={"allowlist": ["ls; rm -rf /"]})
        invalid_queue = client.post("/api/control/pending", json={
            "tool": "shell && rm", "operation": "run", "arguments": {}
        })
    assert invalid_policy.status_code in {400, 422}
    assert invalid_queue.status_code in {400, 422}


def test_command_control_websocket_route_is_modularized():
    with TestClient(app=app) as client:
        with client.websocket_connect("/api/control/events") as socket:
            event = socket.receive_json()
    assert event["type"] == "connected"


def test_command_control_websocket_replays_audit_summary_without_arguments():
    with TestClient(app=app) as client:
        queued = client.post("/api/control/pending", json={
            "tool": "workspace",
            "operation": "inspect",
            "arguments": {"path": "README.md", "private_note": "must-not-be-streamed"},
        })
        assert queued.status_code in {200, 201}
        operation_id = queued.json()["operation"]["id"]

        with client.websocket_connect("/api/control/events") as socket:
            connected = socket.receive_json()
            assert connected["type"] == "connected"
            replayed = None
            # The endpoint replays at most the most recent 100 audit summaries.
            for _ in range(100):
                event = socket.receive_json()
                if event.get("type") == "action_event" and event.get("target") == operation_id:
                    replayed = event
                    break

    assert replayed is not None
    assert replayed["action"] == "operation.queued"
    assert replayed["details"] == {"tool": "workspace", "operation": "inspect"}
    assert "private_note" not in str(replayed)
    assert "README.md" not in str(replayed)

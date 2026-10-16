from litestar.testing import TestClient

from app import app


def test_whatsapp_agent_status_endpoint_never_exposes_api_key():
    with TestClient(app=app) as client:
        response = client.get("/api/whatsapp-agent/status")
        assert response.status_code == 200
        body = response.json()
        assert "api_key" not in body
        assert "configured" in body
        assert body["mode"] == "text-only"


def test_whatsapp_agent_requires_key_before_enable():
    with TestClient(app=app) as client:
        response = client.post("/api/whatsapp-agent/config", json={"enabled": True})
        assert response.status_code == 400
        assert "API key is required" in response.json()["detail"]

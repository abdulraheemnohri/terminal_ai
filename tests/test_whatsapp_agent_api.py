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


def test_whatsapp_dashboard_page_and_assets_are_served_and_wired_to_api():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "web/pages/whatsapp-agent.html").read_text(encoding="utf-8")
    script = (root / "web/js/whatsapp-agent.js").read_text(encoding="utf-8")

    # The visible page must load its real assets and expose controls for each
    # backend operation rather than being a disconnected mockup.
    assert "/static/css/whatsapp-agent.css" in html
    assert "/static/js/whatsapp-agent.js" in html
    for element_id in ("refresh-status", "config-form", "test-connection", "remove-key", "send-form"):
        assert f'id="{element_id}"' in html
    for endpoint in (
        "/api/whatsapp-agent/status",
        "/api/whatsapp-agent/config",
        "/api/whatsapp-agent/test",
        "/api/whatsapp-agent/send",
    ):
        assert endpoint in script
    assert "api_key" in script and "clear_key" in script

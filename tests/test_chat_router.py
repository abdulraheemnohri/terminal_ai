from litestar.testing import TestClient

from app import app


def test_chat_run_metadata_route_is_modularized():
    with TestClient(app=app) as client:
        response = client.get("/api/chat/runs")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"runs", "count", "retention_limit"}
    assert isinstance(payload["runs"], list)
    assert payload["retention_limit"] == 50

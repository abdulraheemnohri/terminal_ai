from litestar.testing import TestClient

from app import app


def test_health_and_readiness_endpoints():
    with TestClient(app=app) as client:
        live = client.get("/healthz")
        ready = client.get("/readyz")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert all(ready.json()["checks"].values())

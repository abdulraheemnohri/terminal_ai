from litestar.testing import TestClient

from app import app


def test_dashboard_returns_html():
    with TestClient(app=app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Terminal AI" in response.text
    assert "AI Chat" in response.text


def test_status_endpoint_is_available_without_model():
    with TestClient(app=app) as client:
        response = client.get("/api/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["interface"] == "Litestar Web UI"
    assert "gemini_configured" in payload


def test_settings_reject_invalid_mode():
    with TestClient(app=app) as client:
        response = client.patch("/api/settings", json={"mode": "not-a-mode"})
    assert response.status_code == 400



def test_models_endpoint_does_not_require_backend():
    with TestClient(app=app) as client:
        response = client.get("/api/models")
    assert response.status_code == 200
    payload = response.json()
    assert "models" in payload
    assert "models_dir" in payload
    assert "installed_count" in payload


def test_diagnostics_endpoint_is_local_and_structured():
    with TestClient(app=app) as client:
        response = client.get("/api/diagnostics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["application"]["interface"] == "Litestar Web UI"
    assert "storage" in payload
    assert "runtime" in payload


def test_provider_discovery_is_dynamic_and_local():
    with TestClient(app=app) as client:
        response = client.get("/api/providers")
    assert response.status_code == 200
    payload = response.json()
    assert {item["id"] for item in payload["providers"]} >= {"gemini", "litert-lm", "huggingface-hub"}


def test_download_requires_explicit_confirmation():
    with TestClient(app=app) as client:
        response = client.post("/api/models/download", json={"model_id": "gemma-3-1b-it"})
    assert response.status_code == 400


def test_download_rejects_non_litert_registry_entry():
    with TestClient(app=app) as client:
        response = client.post("/api/models/download", json={"model_id": "qwen3-1b", "confirm": True})
    assert response.status_code == 400


def test_download_jobs_endpoint_is_available():
    with TestClient(app=app) as client:
        response = client.get("/api/downloads")
    assert response.status_code == 200
    assert "downloads" in response.json()


def test_model_detail_endpoint_returns_registered_model():
    with TestClient(app=app) as client:
        response = client.get("/api/models/gemma-3-1b-it")
        missing = client.get("/api/models/not-registered")
    assert response.status_code == 200
    assert response.json()["name"] == "gemma-3-1b-it"
    assert "installed" in response.json()
    assert missing.status_code == 404

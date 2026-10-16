from __future__ import annotations

from litestar.testing import TestClient

from app import app


def _clear_auth(monkeypatch):
    monkeypatch.delenv("TERMINAL_AI_AUTH_USER", raising=False)
    monkeypatch.delenv("TERMINAL_AI_AUTH_PASSWORD", raising=False)


def test_local_app_remains_usable_without_optional_auth(monkeypatch):
    _clear_auth(monkeypatch)
    with TestClient(app=app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/").status_code == 200


def test_configured_basic_auth_protects_dashboard_and_api(monkeypatch):
    monkeypatch.setenv("TERMINAL_AI_AUTH_USER", "operator")
    monkeypatch.setenv("TERMINAL_AI_AUTH_PASSWORD", "test-only-password")
    with TestClient(app=app) as client:
        denied = client.get("/")
        allowed = client.get("/", auth=("operator", "test-only-password"))
        health = client.get("/healthz")
    assert denied.status_code == 401
    assert denied.headers.get("www-authenticate", "").startswith("Basic ")
    assert allowed.status_code == 200
    assert health.status_code == 200


def test_partial_auth_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("TERMINAL_AI_AUTH_USER", "operator")
    monkeypatch.delenv("TERMINAL_AI_AUTH_PASSWORD", raising=False)
    with TestClient(app=app) as client:
        response = client.get("/")
    assert response.status_code == 503
    assert "misconfigured" in response.text.lower()

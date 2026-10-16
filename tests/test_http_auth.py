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


def test_remote_bind_without_credentials_fails_closed(monkeypatch, tmp_path):
    import asyncio

    from application.security import BasicAuthMiddleware

    _clear_auth(monkeypatch)
    events = []

    async def downstream(scope, receive, send):
        events.append({"type": "downstream"})

    async def send(event):
        events.append(event)

    middleware = BasicAuthMiddleware(downstream, root=tmp_path)
    scope = {
        "type": "http",
        "path": "/",
        "headers": [],
        "server": ("0.0.0.0", 8000),
    }
    asyncio.run(middleware(scope, lambda: None, send))
    assert not any(event.get("type") == "downstream" for event in events)
    assert any(event.get("status") == 503 for event in events if event.get("type") == "http.response.start")


def test_placeholder_credentials_do_not_enable_auth(monkeypatch, tmp_path):
    from application.security import BasicAuthMiddleware

    monkeypatch.setenv("TERMINAL_AI_AUTH_USER", "replace_with_your_username")
    monkeypatch.setenv("TERMINAL_AI_AUTH_PASSWORD", "replace_with_a_long_random_password")
    middleware = BasicAuthMiddleware(lambda *args: None, root=tmp_path)
    assert middleware._credentials() == (None, None)

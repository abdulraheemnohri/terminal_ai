from __future__ import annotations

import asyncio
import base64

from application.security import BasicAuthMiddleware, OriginGuardMiddleware


def invoke(scope, root, monkeypatch):
    calls = []
    messages = []

    async def endpoint(received_scope, receive, send):
        calls.append(received_scope["type"])
        if received_scope["type"] == "http":
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    # Mirrors app.py: OriginGuardMiddleware is the outer browser-request guard,
    # with BasicAuthMiddleware enforcing credentials for the inner application.
    app = OriginGuardMiddleware(BasicAuthMiddleware(endpoint, root=root))
    asyncio.run(app(scope, receive, send))
    return calls, messages


def make_scope(*, method="POST", kind="http", origin=b"http://localhost", authorization=None):
    headers = [(b"host", b"localhost")]
    if origin is not None:
        headers.append((b"origin", origin))
    if authorization is not None:
        headers.append((b"authorization", authorization))
    return {
        "type": kind,
        "method": method,
        "scheme": "http" if kind == "http" else "ws",
        "path": "/api/settings",
        "headers": headers,
        "server": ("127.0.0.1", 8000),
    }


def _credentials(monkeypatch, password="safe-test-password"):
    monkeypatch.setenv("TERMINAL_AI_AUTH_USER", "operator")
    monkeypatch.setenv("TERMINAL_AI_AUTH_PASSWORD", password)
    return b"Basic " + base64.b64encode(f"operator:{password}".encode())


def test_cross_origin_mutation_is_blocked_before_auth(tmp_path, monkeypatch):
    _credentials(monkeypatch)
    calls, messages = invoke(
        make_scope(origin=b"https://attacker.example"),
        tmp_path,
        monkeypatch,
    )
    assert calls == []
    assert messages[0]["status"] == 403
    assert b"Cross-origin" in messages[1]["body"]


def test_same_origin_mutation_still_requires_authentication(tmp_path, monkeypatch):
    _credentials(monkeypatch)
    calls, messages = invoke(
        make_scope(authorization=None),
        tmp_path,
        monkeypatch,
    )
    assert calls == []
    assert messages[0]["status"] == 401


def test_same_origin_mutation_with_valid_credentials_is_allowed(tmp_path, monkeypatch):
    token = _credentials(monkeypatch)
    calls, messages = invoke(
        make_scope(authorization=token),
        tmp_path,
        monkeypatch,
    )
    assert calls == ["http"]
    assert messages[0]["status"] == 204


def test_cross_origin_websocket_is_blocked_even_with_valid_credentials(tmp_path, monkeypatch):
    token = _credentials(monkeypatch)
    calls, messages = invoke(
        make_scope(
            kind="websocket",
            origin=b"https://attacker.example",
            authorization=token,
        ),
        tmp_path,
        monkeypatch,
    )
    assert calls == []
    assert messages == [{
        "type": "websocket.close",
        "code": 4403,
        "reason": "Cross-origin WebSocket rejected",
    }]


def test_non_browser_request_without_origin_still_uses_auth(tmp_path, monkeypatch):
    token = _credentials(monkeypatch)
    calls, messages = invoke(
        make_scope(origin=None, authorization=token),
        tmp_path,
        monkeypatch,
    )
    assert calls == ["http"]
    assert messages[0]["status"] == 204

from __future__ import annotations

import asyncio
import base64

from application.security import BasicAuthMiddleware


def invoke(scope, root, monkeypatch):
    calls = []
    messages = []

    async def inner(received_scope, receive, send):
        calls.append(received_scope["type"])
        if received_scope["type"] == "http":
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(BasicAuthMiddleware(inner, root=root)(scope, receive, send))
    return calls, messages


def scope(*, kind="http", host="127.0.0.1", path="/api/status", authorization=None):
    headers = []
    if authorization is not None:
        headers.append((b"authorization", authorization))
    return {
        "type": kind,
        "method": "GET",
        "scheme": "http" if kind == "http" else "ws",
        "path": path,
        "headers": headers,
        "server": (host, 8000),
    }


def test_remote_bind_without_credentials_fails_closed_for_http(tmp_path, monkeypatch):
    monkeypatch.delenv("TERMINAL_AI_AUTH_USER", raising=False)
    monkeypatch.delenv("TERMINAL_AI_AUTH_PASSWORD", raising=False)
    calls, messages = invoke(scope(host="0.0.0.0"), tmp_path, monkeypatch)
    assert calls == []
    assert messages[0]["status"] == 503
    assert b"requires" in messages[1]["body"]


def test_remote_bind_without_credentials_rejects_websocket(tmp_path, monkeypatch):
    monkeypatch.delenv("TERMINAL_AI_AUTH_USER", raising=False)
    monkeypatch.delenv("TERMINAL_AI_AUTH_PASSWORD", raising=False)
    calls, messages = invoke(scope(kind="websocket", host="0.0.0.0"), tmp_path, monkeypatch)
    assert calls == []
    assert messages == [{
        "type": "websocket.close",
        "code": 4403,
        "reason": "Remote binding requires authentication",
    }]


def test_partial_credentials_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("TERMINAL_AI_AUTH_USER", "operator")
    monkeypatch.delenv("TERMINAL_AI_AUTH_PASSWORD", raising=False)
    calls, messages = invoke(scope(), tmp_path, monkeypatch)
    assert calls == []
    assert messages[0]["status"] == 503
    assert b"misconfigured" in messages[1]["body"]


def test_valid_basic_credentials_allow_request(tmp_path, monkeypatch):
    monkeypatch.setenv("TERMINAL_AI_AUTH_USER", "operator")
    monkeypatch.setenv("TERMINAL_AI_AUTH_PASSWORD", "correct horse battery staple")
    token = base64.b64encode(b"operator:correct horse battery staple")
    calls, messages = invoke(scope(authorization=b"Basic " + token), tmp_path, monkeypatch)
    assert calls == ["http"]
    assert messages[0]["status"] == 204


def test_invalid_and_malformed_basic_credentials_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("TERMINAL_AI_AUTH_USER", "operator")
    monkeypatch.setenv("TERMINAL_AI_AUTH_PASSWORD", "private-password")
    for authorization in (b"Basic !!!not-base64!!!", b"Bearer token", b"Basic " + base64.b64encode(b"operator:wrong")):
        calls, messages = invoke(scope(authorization=authorization), tmp_path, monkeypatch)
        assert calls == []
        assert messages[0]["status"] == 401
        assert b"private-password" not in messages[1]["body"]


def test_auth_exemption_is_limited_to_exact_health_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("TERMINAL_AI_AUTH_USER", "operator")
    monkeypatch.setenv("TERMINAL_AI_AUTH_PASSWORD", "private-password")
    calls, messages = invoke(scope(path="/healthz"), tmp_path, monkeypatch)
    assert calls == ["http"]
    assert messages[0]["status"] == 204
    calls, messages = invoke(scope(path="/healthz/extra"), tmp_path, monkeypatch)
    assert calls == []
    assert messages[0]["status"] == 401

from __future__ import annotations

import asyncio

from application.security import OriginGuardMiddleware


def invoke(scope):
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

    asyncio.run(OriginGuardMiddleware(inner)(scope, receive, send))
    return calls, messages


def http_scope(method: str, origin: bytes | None, host: bytes = b"localhost"):
    headers = [(b"host", host)]
    if origin is not None:
        headers.append((b"origin", origin))
    return {"type": "http", "method": method, "scheme": "http", "path": "/api/test", "headers": headers}


def test_origin_guard_rejects_cross_origin_mutation():
    calls, messages = invoke(http_scope("POST", b"https://attacker.example"))
    assert calls == []
    assert messages[0]["status"] == 403
    assert b"Cross-origin" in messages[1]["body"]


def test_origin_guard_allows_same_origin_mutation_and_default_port_equivalence():
    calls, messages = invoke(http_scope("PATCH", b"http://localhost:80"))
    assert calls == ["http"]
    assert messages[0]["status"] == 204


def test_origin_guard_does_not_block_safe_cross_origin_get():
    calls, messages = invoke(http_scope("GET", b"https://attacker.example"))
    assert calls == ["http"]
    assert messages[0]["status"] == 204


def test_origin_guard_rejects_cross_origin_websocket():
    calls, messages = invoke({
        "type": "websocket", "scheme": "ws", "path": "/api/control/events",
        "headers": [(b"host", b"localhost"), (b"origin", b"https://attacker.example")],
    })
    assert calls == []
    assert messages == [{"type": "websocket.close", "code": 4403, "reason": "Cross-origin WebSocket rejected"}]


def test_origin_guard_allows_non_browser_client_without_origin():
    calls, messages = invoke(http_scope("POST", None))
    assert calls == ["http"]
    assert messages[0]["status"] == 204

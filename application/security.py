"""Optional HTTP Basic authentication and fail-closed remote-bind protection.

Credentials may be supplied through the process environment or the private .env
file. The middleware never logs credentials or Authorization headers.
"""
from __future__ import annotations

import base64
import hmac
import ipaddress
import os
from pathlib import Path
from typing import Any


def _usable_credential(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value or value.lower().startswith(("replace_", "your_", "change_me", "placeholder")):
        return None
    return value


def _env_value(root: Path, key: str) -> str | None:
    value = _usable_credential(os.environ.get(key))
    if value:
        return value
    env_file = root / ".env"
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        if candidate.startswith("export "):
            candidate = candidate[7:].lstrip()
        name, separator, raw = candidate.partition("=")
        if not separator or name.strip() != key:
            continue
        raw = raw.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
            raw = raw[1:-1]
        raw = raw.strip()
        return _usable_credential(raw)
    return None


def _is_remote_bind(scope: dict[str, Any]) -> bool:
    server = scope.get("server")
    if not isinstance(server, (tuple, list)) or not server:
        return False
    host = str(server[0]).strip().strip("[]")
    try:
        return not ipaddress.ip_address(host).is_loopback
    except ValueError:
        # ASGI test clients and unresolved labels are not evidence of a remote bind.
        return host in {"0.0.0.0", "::", "::0", "*"} or host.casefold() in {"0.0.0.0", "::"}


class BasicAuthMiddleware:
    """Protect all routes except health probes when credentials are configured.

    If the socket is bound to a non-loopback IP, requests are denied unless both
    username and password are configured. A remote-bind opt-in alone is not auth.
    """

    def __init__(self, app: Any, *, root: str | Path, exempt_paths: tuple[str, ...] = ("/healthz", "/readyz")):
        self.app = app
        self.root = Path(root)
        self.exempt_paths = frozenset(exempt_paths)

    @staticmethod
    async def _respond(send: Any, status: int, body: str, *, challenge: bool = False) -> None:
        payload = body.encode("utf-8")
        headers = [
            (b"content-type", b"text/plain; charset=utf-8"),
            (b"content-length", str(len(payload)).encode("ascii")),
            (b"cache-control", b"no-store"),
        ]
        if challenge:
            headers.append((b"www-authenticate", b'Basic realm="Terminal AI", charset="UTF-8"'))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": payload})

    def _credentials(self) -> tuple[str | None, str | None]:
        return (
            _env_value(self.root, "TERMINAL_AI_AUTH_USER"),
            _env_value(self.root, "TERMINAL_AI_AUTH_PASSWORD"),
        )

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", "/"))
        if path in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        username, password = self._credentials()
        if bool(username) != bool(password):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 4403, "reason": "Authentication is misconfigured"})
            else:
                await self._respond(send, 503, "Terminal AI authentication is misconfigured; set both auth variables.")
            return

        if not username or not password:
            if _is_remote_bind(scope):
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 4403, "reason": "Remote binding requires authentication"})
                else:
                    await self._respond(send, 503, "Remote binding requires TERMINAL_AI_AUTH_USER and TERMINAL_AI_AUTH_PASSWORD.")
                return
            await self.app(scope, receive, send)
            return

        auth_header = next(
            (value for name, value in scope.get("headers", []) if name.lower() == b"authorization"),
            b"",
        )
        valid = False
        try:
            scheme, encoded = auth_header.decode("ascii").split(" ", 1)
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
            supplied_user, separator, supplied_password = decoded.partition(":")
            valid = (
                scheme.casefold() == "basic"
                and bool(separator)
                and hmac.compare_digest(supplied_user, username)
                and hmac.compare_digest(supplied_password, password)
            )
        except (ValueError, UnicodeError):
            valid = False

        if not valid:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 4401, "reason": "Authentication required"})
            else:
                await self._respond(send, 401, "Authentication required.", challenge=True)
            return
        await self.app(scope, receive, send)

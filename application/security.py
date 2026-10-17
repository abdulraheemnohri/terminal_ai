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
from urllib.parse import urlsplit
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



def security_status(root: str | Path) -> dict[str, Any]:
    """Return a redacted security configuration summary without credential values."""
    root_path = Path(root)
    username = _env_value(root_path, "TERMINAL_AI_AUTH_USER")
    password = _env_value(root_path, "TERMINAL_AI_AUTH_PASSWORD")
    complete = bool(username and password)
    partial = bool(username) != bool(password)
    env_user = _usable_credential(os.environ.get("TERMINAL_AI_AUTH_USER"))
    env_password = _usable_credential(os.environ.get("TERMINAL_AI_AUTH_PASSWORD"))
    env_complete = bool(env_user and env_password)
    env_partial = bool(env_user) != bool(env_password)
    if partial:
        state = "misconfigured"
        message = "Only one authentication credential is configured. Requests fail closed until both are set."
    elif complete:
        state = "protected"
        message = "HTTP Basic authentication is configured. Use HTTPS or a trusted local tunnel before remote exposure."
    else:
        state = "local-only"
        message = "Authentication is not configured. Remote-bound requests are rejected by the fail-closed middleware."
    return {
        "state": state,
        "authentication_configured": complete,
        "credential_pair_complete": not partial,
        "configuration_error": partial,
        "credential_source": "environment" if env_complete else ("private .env or mixed" if complete or partial else "none"),
        "remote_bind_requires_auth": True,
        "credentials_exposed": False,
        "message": message,
        "required_environment_names": ["TERMINAL_AI_AUTH_USER", "TERMINAL_AI_AUTH_PASSWORD"],
    }


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
                and hmac.compare_digest(supplied_user.encode("utf-8"), username.encode("utf-8"))
                and hmac.compare_digest(supplied_password.encode("utf-8"), password.encode("utf-8"))
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


class OriginGuardMiddleware:
    """Reject cross-origin browser mutations and WebSocket upgrades.

    Requests without an Origin header remain supported for CLI and server-to-server
    clients. This is a browser CSRF defense-in-depth measure, not a replacement for
    authentication, TLS, or network isolation.
    """

    _MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

    def __init__(self, app: Any):
        self.app = app

    @staticmethod
    def _normalized_authority(value: str, *, scheme: str) -> tuple[str, int] | None:
        try:
            parsed = urlsplit(value if "://" in value else f"{scheme}://{value}")
            if not parsed.hostname or parsed.username is not None or parsed.password is not None:
                return None
            port = parsed.port
            if port is None:
                port = 443 if scheme in {"https", "wss"} else 80
            return parsed.hostname.casefold().rstrip("."), port
        except (ValueError, UnicodeError):
            return None

    @classmethod
    def _same_origin(cls, origin: bytes, host: bytes, request_scheme: str) -> bool:
        try:
            raw_origin = origin.decode("ascii").strip()
            raw_host = host.decode("ascii").strip()
            parsed = urlsplit(raw_origin)
        except (UnicodeError, ValueError):
            return False
        expected_scheme = {"ws": "http", "wss": "https"}.get(request_scheme, request_scheme)
        if (
            parsed.scheme.casefold() != expected_scheme.casefold()
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or not parsed.netloc
            or raw_origin.casefold() == "null"
        ):
            return False
        origin_authority = cls._normalized_authority(parsed.netloc, scheme=parsed.scheme.casefold())
        host_authority = cls._normalized_authority(raw_host, scheme=expected_scheme.casefold())
        return origin_authority is not None and origin_authority == host_authority

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        scope_type = scope.get("type")
        if scope_type not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method", "")).upper()
        if scope_type == "http" and method not in self._MUTATING_METHODS:
            await self.app(scope, receive, send)
            return
        origin = next((value for name, value in scope.get("headers", []) if name.lower() == b"origin"), None)
        if origin is None:
            await self.app(scope, receive, send)
            return
        host = next((value for name, value in scope.get("headers", []) if name.lower() == b"host"), None)
        if host is None or not self._same_origin(origin, host, str(scope.get("scheme", "http")).lower()):
            if scope_type == "websocket":
                await send({"type": "websocket.close", "code": 4403, "reason": "Cross-origin WebSocket rejected"})
                return
            payload = b"Cross-origin request rejected."
            await send({"type": "http.response.start", "status": 403, "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", str(len(payload)).encode("ascii")),
                (b"cache-control", b"no-store"),
            ]})
            await send({"type": "http.response.body", "body": payload})
            return
        await self.app(scope, receive, send)

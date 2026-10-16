"""WhatsApp Agent Platform integration (text-only v1).

Uses Meta's Agent Platform API, not WhatsApp Web QR pairing or the Business Cloud API.
Secrets and polling state are stored locally with restrictive file permissions.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from litestar import Router, get, post
from litestar.exceptions import HTTPException

logger = logging.getLogger(__name__)

API_BASE = "https://api.whatsapp.com/agent/v1"
MAX_TEXT_LENGTH = 4000
POLL_TIMEOUT = 20
POLL_LIMIT = 50
SEEN_LIMIT = 500


class WhatsAppAgentPlatform:
    """Single-key long-poll client for the creator-only WhatsApp Agent Platform."""

    def __init__(
        self,
        state_dir: Path,
        reply_handler: Callable[[str], Awaitable[str]],
        *,
        base_url: str = API_BASE,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._state_dir = Path(state_dir)
        self._path = self._state_dir / "whatsapp_agent_platform.json"
        self._reply_handler = reply_handler
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._http: httpx.AsyncClient | None = None
        self._state = self._load()
        self._state.setdefault("enabled", False)
        self._state.setdefault("api_key", "")
        self._state.setdefault("creator_id", "")
        self._state.setdefault("next_offset", None)
        self._state.setdefault("seen_ids", [])
        self._state.setdefault("connected", False)
        self._state.setdefault("last_error", "")
        self._state.setdefault("last_poll_at", None)
        self._state.setdefault("last_message_at", None)
        self._state.setdefault("received_count", 0)
        self._state.setdefault("sent_count", 0)

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(self._path.name + ".tmp")
        try:
            temporary.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            os.replace(temporary, self._path)
            try:
                self._path.chmod(0o600)
            except OSError:
                pass
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def status(self) -> dict[str, Any]:
        return {
            "enabled": bool(self._state.get("enabled")),
            "configured": bool(self._state.get("api_key")),
            "connected": bool(self._state.get("connected")),
            "creator_id": self._state.get("creator_id") or "",
            "last_error": self._state.get("last_error") or "",
            "last_poll_at": self._state.get("last_poll_at"),
            "last_message_at": self._state.get("last_message_at"),
            "received_count": int(self._state.get("received_count", 0)),
            "sent_count": int(self._state.get("sent_count", 0)),
            "mode": "text-only",
            "api_base": self._base_url,
            "privacy_notice": (
                "WhatsApp Agent Platform chats are not end-to-end encrypted. "
                "Messages are sent to Meta's Agent Platform and then to the configured AI backend."
            ),
            "limits": {"max_connected_agents_in_whatsapp": 5, "text_only": True},
        }

    async def _client(self) -> httpx.AsyncClient:
        if not self._state.get("api_key"):
            raise ValueError("Add the Agent API key from WhatsApp → Settings → Agents → Chat info → API key.")
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self._state['api_key']}"},
                timeout=httpx.Timeout(35.0, connect=10.0),
                follow_redirects=False,
                transport=self._transport,
            )
        return self._http

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        client = await self._client()
        try:
            response = await client.request(method, f"{self._base_url}{path}", **kwargs)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"WhatsApp Agent Platform network error: {type(exc).__name__}") from None
        if response.status_code == 401:
            raise PermissionError("Meta rejected the Agent API key. Check the key in WhatsApp agent chat info.")
        if response.status_code == 403:
            raise PermissionError("Meta refused this action. The sender or recipient may not be the agent creator.")
        if response.status_code == 429:
            raise RuntimeError("WhatsApp Agent Platform rate limit reached; retry after a short delay.")
        if response.status_code >= 500:
            raise RuntimeError(f"WhatsApp Agent Platform is temporarily unavailable (HTTP {response.status_code}).")
        if response.status_code >= 400:
            # Do not include raw response bodies: they may contain message content or identifiers.
            raise ValueError(f"WhatsApp Agent Platform rejected the request (HTTP {response.status_code}).")
        return response

    async def _get_updates(self, *, timeout: int, limit: int = POLL_LIMIT) -> dict[str, Any] | None:
        params: dict[str, int] = {"timeout": max(0, min(25, timeout)), "limit": max(1, min(50, limit))}
        offset = self._state.get("next_offset")
        if isinstance(offset, int):
            params["offset"] = offset
        response = await self._request("GET", "/updates", params=params,
                                       timeout=httpx.Timeout(params["timeout"] + 15, connect=10))
        if response.status_code == 204:
            return None
        try:
            payload = response.json()
        except ValueError:
            raise ValueError("Meta returned an invalid updates response.") from None
        if not isinstance(payload, dict) or payload.get("object") != "whatsapp_agent_platform":
            raise ValueError("Meta returned an unexpected updates response.")
        next_offset = payload.get("next_offset")
        if type(next_offset) is not int:
            raise ValueError("Meta updates response is missing next_offset.")
        self._state["next_offset"] = next_offset
        return payload

    @staticmethod
    def _messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for entry in payload.get("entry", []):
            if not isinstance(entry, dict):
                continue
            for change in entry.get("changes", []):
                if not isinstance(change, dict) or change.get("field") != "messages":
                    continue
                value = change.get("value")
                if isinstance(value, dict) and isinstance(value.get("messages"), list):
                    found.extend(m for m in value["messages"] if isinstance(m, dict))
        return found

    async def _mark_read(self, message_id: str) -> bool:
        try:
            response = await self._request("POST", "/statuses", json={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            })
        except PermissionError:
            return False
        try:
            return response.json().get("success") is True
        except (ValueError, AttributeError):
            return False

    async def _send_text(self, recipient: str, body: str, *, reply_to: str | None = None) -> str:
        text = body.strip()
        if not text:
            return ""
        sent_ids: list[str] = []
        # Keep each API request comfortably below the documented message limit.
        while text:
            chunk, text = text[:MAX_TEXT_LENGTH], text[MAX_TEXT_LENGTH:]
            payload: dict[str, Any] = {
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "text",
                "text": {"body": chunk},
            }
            if reply_to and not sent_ids:
                payload["context"] = {"message_id": reply_to}
            response = await self._request("POST", "/messages", json=payload)
            try:
                message_id = response.json()["messages"][0]["id"]
            except (ValueError, KeyError, IndexError, TypeError):
                raise ValueError("Meta accepted the request without returning a message ID.") from None
            sent_ids.append(str(message_id))
            self._state["sent_count"] = int(self._state.get("sent_count", 0)) + 1
        self._save()
        return sent_ids[-1] if sent_ids else ""

    async def test_connection(self) -> dict[str, Any]:
        # Do not compete with the long-poll worker; it is already an authenticated connection.
        if self._task is not None and not self._task.done():
            connected = bool(self._state.get("connected"))
            return {
                "ok": connected,
                "message": "The WhatsApp Agent Platform poller is connected." if connected
                else "The background poller is connecting; refresh status in a few seconds.",
                "status": self.status(),
            }
        try:
            await self._get_updates(timeout=0, limit=1)
            self._state["last_error"] = ""
            self._state["last_poll_at"] = int(time.time())
            self._save()
            return {"ok": True, "message": "Agent API key accepted by Meta.", "status": self.status()}
        except Exception as exc:
            self._state["last_error"] = str(exc)[:300]
            self._save()
            raise

    async def configure(self, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {"enabled", "api_key", "clear_key"}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError("Unknown WhatsApp setting(s): " + ", ".join(unknown[:8]))
        enabled = data.get("enabled", self._state.get("enabled", False))
        if type(enabled) is not bool:
            raise ValueError("enabled must be a boolean.")
        key = data.get("api_key", "")
        if not isinstance(key, str) or len(key) > 4096:
            raise ValueError("api_key must be text up to 4096 characters.")
        if key.strip():
            self._state["api_key"] = key.strip()
            # A changed key must not reuse a cursor or creator pinned to another agent.
            self._state["creator_id"] = ""
            self._state["next_offset"] = None
            self._state["seen_ids"] = []
        if data.get("clear_key") is True:
            self._state["api_key"] = ""
            self._state["creator_id"] = ""
            self._state["next_offset"] = None
            self._state["seen_ids"] = []
            enabled = False
        if enabled and not self._state.get("api_key"):
            raise ValueError("An Agent API key is required before enabling the integration.")
        self._state["enabled"] = enabled
        self._state["connected"] = False
        self._state["last_error"] = ""
        self._save()
        await self._restart_worker()
        return self.status()

    async def send_manual(self, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {"message", "recipient"}
        if set(data) - allowed:
            raise ValueError("Unknown send field(s).")
        message = data.get("message")
        recipient = str(data.get("recipient") or self._state.get("creator_id") or "").strip()
        if not isinstance(message, str) or not message.strip() or len(message) > 20000:
            raise ValueError("Message must contain 1–20,000 characters.")
        if not recipient or len(recipient) > 128 or any(ch.isspace() for ch in recipient):
            raise ValueError("A valid WhatsApp user ID is required. The creator ID is learned from the first verified inbound message.")
        if recipient != self._state.get("creator_id"):
            raise PermissionError("Outbound messages are restricted to the creator ID verified by Meta.")
        await self._send_text(recipient, message)
        return {"sent": True, "status": self.status()}

    async def _process_payload(self, payload: dict[str, Any]) -> None:
        seen_list = list(self._state.get("seen_ids", []))
        seen = set(seen_list)
        for message in self._messages(payload):
            message_id = message.get("id")
            sender = message.get("from")
            if not isinstance(message_id, str) or not message_id or not isinstance(sender, str):
                continue
            if message_id in seen:
                continue
            # Meta's read-receipt endpoint is the authoritative creator check.
            if not await self._mark_read(message_id):
                seen.add(message_id)
                continue
            creator = self._state.get("creator_id")
            if creator and creator != sender:
                seen.add(message_id)
                continue
            self._state["creator_id"] = sender
            message_type = message.get("type")
            if message_type != "text":
                answer = "This Terminal AI WhatsApp integration currently supports text messages only. Media support is not enabled yet."
            else:
                text_data = message.get("text")
                text = text_data.get("body", "") if isinstance(text_data, dict) else ""
                if not isinstance(text, str) or not text.strip():
                    seen.add(message_id)
                    continue
                self._state["received_count"] = int(self._state.get("received_count", 0)) + 1
                self._state["last_message_at"] = int(time.time())
                try:
                    answer = await self._reply_handler(text[:20000])
                except Exception as exc:
                    logger.warning("WhatsApp reply generation failed (%s)", type(exc).__name__)
                    answer = "I couldn't complete that request because the AI backend is unavailable. Please try again."
            try:
                await self._send_text(sender, str(answer or "I couldn't generate a response."), reply_to=message_id)
            except Exception:
                # Do not log or persist the message body or API key. A retry may happen on the next poll.
                logger.warning("WhatsApp reply delivery failed; check connection status.")
                raise
            seen.add(message_id)
        self._state["seen_ids"] = (seen_list + [mid for mid in seen if mid not in set(seen_list)])[-SEEN_LIMIT:]
        self._state["last_poll_at"] = int(time.time())
        self._state["last_error"] = ""
        self._save()

    async def _poll_loop(self) -> None:
        backoff = 2.0
        while self._state.get("enabled") and self._state.get("api_key"):
            try:
                payload = await self._get_updates(timeout=POLL_TIMEOUT)
                if payload is not None:
                    await self._process_payload(payload)
                else:
                    self._state["last_poll_at"] = int(time.time())
                    self._save()
                self._state["connected"] = True
                self._state["last_error"] = ""
                backoff = 2.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._state["connected"] = False
                self._state["last_error"] = str(exc)[:300]
                self._save()
                logger.warning("WhatsApp Agent Platform poll failed (%s)", type(exc).__name__)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def _restart_worker(self) -> None:
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._state["connected"] = False
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        if self._state.get("enabled") and self._state.get("api_key"):
            self._task = asyncio.create_task(self._poll_loop(), name="whatsapp-agent-platform-poller")

    async def start(self) -> None:
        if self._state.get("enabled") and self._state.get("api_key"):
            await self._restart_worker()

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        self._state["connected"] = False
        self._save()


def create_whatsapp_agent_router(service: WhatsAppAgentPlatform) -> Router:
    @get("/api/whatsapp-agent/status")
    async def get_whatsapp_agent_status() -> dict[str, Any]:
        return service.status()

    @post("/api/whatsapp-agent/config")
    async def configure_whatsapp_agent(data: dict[str, Any]) -> dict[str, Any]:
        try:
            return await service.configure(data)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @post("/api/whatsapp-agent/test")
    async def test_whatsapp_agent() -> dict[str, Any]:
        try:
            return await service.test_connection()
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @post("/api/whatsapp-agent/send")
    async def send_whatsapp_agent_message(data: dict[str, Any]) -> dict[str, Any]:
        try:
            return await service.send_manual(data)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Router(path="", route_handlers=[
        get_whatsapp_agent_status, configure_whatsapp_agent, test_whatsapp_agent, send_whatsapp_agent_message,
    ])

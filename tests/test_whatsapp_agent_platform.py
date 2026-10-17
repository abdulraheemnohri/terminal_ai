from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from application.whatsapp_agent_platform import WhatsAppAgentPlatform


def _response(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/updates") and request.method == "GET":
        return httpx.Response(200, json={
            "object": "whatsapp_agent_platform",
            "next_offset": 42,
            "entry": [],
        })
    if request.url.path.endswith("/statuses") and request.method == "POST":
        return httpx.Response(200, json={"success": True})
    if request.url.path.endswith("/messages") and request.method == "POST":
        return httpx.Response(200, json={"messages": [{"id": "wamid.outbound-test"}]})
    return httpx.Response(404, json={"error": {"message": "not found"}})


def _service(tmp_path: Path, reply_handler=None) -> WhatsAppAgentPlatform:
    async def default_reply(message: str) -> str:
        return "AI reply: " + message

    return WhatsAppAgentPlatform(
        tmp_path,
        reply_handler or default_reply,
        base_url="https://api.whatsapp.test/agent/v1",
        transport=httpx.MockTransport(_response),
    )


def test_config_secret_is_local_private_and_never_returned(tmp_path):
    async def run():
        service = _service(tmp_path)
        status = await service.configure({"api_key": "test-agent-secret", "enabled": False})
        assert status["configured"] is True
        assert "api_key" not in status
        stored = json.loads((tmp_path / "whatsapp_agent_platform.json").read_text())
        assert stored["api_key"] == "test-agent-secret"
        if hasattr(Path, "chmod"):
            assert (tmp_path / "whatsapp_agent_platform.json").stat().st_mode & 0o077 == 0
        await service.stop()

    asyncio.run(run())


def test_cannot_enable_without_api_key(tmp_path):
    async def run():
        service = _service(tmp_path)
        with pytest.raises(ValueError, match="API key is required"):
            await service.configure({"enabled": True})
        await service.stop()

    asyncio.run(run())


def test_test_connection_uses_meta_updates_endpoint(tmp_path):
    async def run():
        service = _service(tmp_path)
        await service.configure({"api_key": "test-agent-secret", "enabled": False})
        result = await service.test_connection()
        assert result["ok"] is True
        assert result["status"]["configured"] is True
        assert result["status"]["last_error"] == ""
        assert result["status"]["api_base"] == "https://api.whatsapp.test/agent/v1"
        await service.stop()

    asyncio.run(run())


def test_connection_probe_does_not_advance_update_cursor(tmp_path):
    async def run():
        service = _service(tmp_path)
        await service.configure({"api_key": "test-agent-secret", "enabled": False})
        service._state["next_offset"] = 7
        result = await service.test_connection()
        assert result["ok"] is True
        assert result["status"]["last_error"] == ""
        assert service._state["next_offset"] == 7
        persisted = json.loads((tmp_path / "whatsapp_agent_platform.json").read_text())
        assert persisted["next_offset"] == 7
        await service.stop()

    asyncio.run(run())


def test_creator_message_is_verified_then_replied_to(tmp_path):
    seen = []

    async def reply_handler(message: str) -> str:
        seen.append(message)
        return "Reply for " + message

    async def run():
        service = _service(tmp_path, reply_handler)
        await service.configure({"api_key": "test-agent-secret", "enabled": False})
        payload = {
            "object": "whatsapp_agent_platform",
            "next_offset": 43,
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {"messages": [{
                        "id": "wamid.inbound-test",
                        "from": "user:creator-123",
                        "type": "text",
                        "text": {"body": "Hello Terminal AI"},
                    }]},
                }],
            }],
        }
        await service._process_payload(payload)
        status = service.status()
        assert seen == ["Hello Terminal AI"]
        assert status["creator_id"] == "user:creator-123"
        assert status["received_count"] == 1
        assert status["sent_count"] == 1
        assert "test-agent-secret" not in json.dumps(status)
        assert "wamid.inbound-test" in json.loads(
            (tmp_path / "whatsapp_agent_platform.json").read_text()
        )["seen_ids"]
        await service.stop()

    asyncio.run(run())


def test_non_creator_message_is_never_forwarded(tmp_path):
    seen = []

    async def reply_handler(message: str) -> str:
        seen.append(message)
        return "must not be sent"

    async def run():
        service = _service(tmp_path, reply_handler)
        await service.configure({"api_key": "test-agent-secret", "enabled": False})
        service._state["creator_id"] = "user:verified-creator"
        payload = {
            "object": "whatsapp_agent_platform",
            "next_offset": 44,
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {"messages": [{
                        "id": "wamid.other-sender",
                        "from": "user:other-person",
                        "type": "text",
                        "text": {"body": "private message"},
                    }]},
                }],
            }],
        }
        await service._process_payload(payload)
        assert seen == []
        assert service.status()["creator_id"] == "user:verified-creator"
        assert service.status()["sent_count"] == 0
        await service.stop()

    asyncio.run(run())


def test_manual_send_is_limited_to_verified_creator(tmp_path):
    async def run():
        service = _service(tmp_path)
        await service.configure({"api_key": "test-agent-secret", "enabled": False})
        service._state["creator_id"] = "user:verified-creator"
        service._state["enabled"] = True
        with pytest.raises(PermissionError, match="restricted to the creator"):
            await service.send_manual({"recipient": "user:other-person", "message": "hello"})
        result = await service.send_manual({"message": "hello"})
        assert result["sent"] is True
        assert result["status"]["sent_count"] == 1
        await service.stop()

    asyncio.run(run())

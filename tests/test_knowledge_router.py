from __future__ import annotations

from litestar import Litestar
from litestar.testing import TestClient

from agent.memory import MemoryStore
from routers.knowledge import create_knowledge_router


def _client(tmp_path, *, enabled: bool = True):
    store = MemoryStore(tmp_path / "knowledge.sqlite3")
    app = Litestar(
        route_handlers=[create_knowledge_router(store, lambda: {"long_term_memory_enabled": enabled})]
    )
    return TestClient(app=app), store


def test_knowledge_api_create_list_search_and_delete(tmp_path):
    client, store = _client(tmp_path)
    with client:
        created = client.post(
            "/api/knowledge/",
            json={
                "title": "Offline deployment",
                "content": "Use local SQLite and keep model inference offline",
                "tags": ["offline", "sqlite"],
                "pinned": True,
            },
        )
        assert created.status_code == 201
        item = created.json()["item"]
        assert item["title"] == "Offline deployment"
        assert item["pinned"] is True

        listed = client.get("/api/knowledge/")
        assert listed.status_code == 200
        assert listed.json()["count"] == 1

        searched = client.post("/api/knowledge/search", json={"query": "offline sqlite", "limit": 5})
        assert searched.status_code == 201
        assert searched.json()["offline"] is True
        assert searched.json()["knowledge"][0]["id"] == item["id"]

        deleted = client.post(f"/api/knowledge/{item['id']}/delete")
        assert deleted.status_code == 201
        assert store.get(item["id"]) is None

        missing = client.post(f"/api/knowledge/{item['id']}/delete")
        assert missing.status_code == 404


def test_knowledge_api_rejects_invalid_payloads(tmp_path):
    client, _ = _client(tmp_path)
    with client:
        missing_title = client.post(
            "/api/knowledge/",
            json={"title": " ", "content": "some content"},
        )
        oversized_tag = client.post(
            "/api/knowledge/",
            json={"title": "Title", "content": "Body", "tags": ["x" * 81]},
        )
        unknown_field = client.post(
            "/api/knowledge/",
            json={"title": "Title", "content": "Body", "unexpected": True},
        )
    assert missing_title.status_code == 400
    assert oversized_tag.status_code == 400
    assert unknown_field.status_code == 400


def test_knowledge_api_respects_disabled_memory_setting(tmp_path):
    client, _ = _client(tmp_path, enabled=False)
    with client:
        assert client.get("/api/knowledge/").status_code == 403
        assert client.post(
            "/api/knowledge/",
            json={"title": "Title", "content": "Body"},
        ).status_code == 403
        assert client.post(
            "/api/knowledge/search",
            json={"query": "Body"},
        ).status_code == 403

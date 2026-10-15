"""Typed, modular routes for local knowledge and conversation search."""
from __future__ import annotations

from typing import Any, Callable

from litestar import Router, get, post
from litestar.exceptions import HTTPException

from agent.memory import MemoryStore
from api_schemas import KnowledgeCreateRequest, KnowledgeSearchRequest


def create_knowledge_router(
    store: MemoryStore,
    settings_reader: Callable[[], dict[str, Any]],
) -> Router:
    def ensure_enabled() -> None:
        if not settings_reader().get("long_term_memory_enabled", True):
            raise HTTPException(status_code=403, detail="Long-term memory is disabled in Settings.")

    @get("/")
    async def list_knowledge(q: str = "", limit: int = 100) -> dict[str, Any]:
        """List/search durable local knowledge without calling a remote provider."""
        ensure_enabled()
        items = store.search(q, limit) if q.strip() else store.list(limit)
        return {"items": items, "count": len(items), "storage": "sqlite", "offline": True}

    @post("/")
    async def add_knowledge(data: KnowledgeCreateRequest) -> dict[str, Any]:
        ensure_enabled()
        try:
            item = store.add(
                data.title, data.content, kind=data.kind, tags=data.tags,
                source="web-ui", pinned=data.pinned,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "saved", "item": item}

    @post("/search")
    async def search_knowledge(data: KnowledgeSearchRequest) -> dict[str, Any]:
        ensure_enabled()
        query = data.query.strip()
        return {
            "knowledge": store.search(query, data.limit),
            "conversations": store.archive_search(query, data.limit),
            "offline": True,
        }

    @post("/{item_id:str}/delete")
    async def delete_knowledge(item_id: str) -> dict[str, Any]:
        ensure_enabled()
        if not store.delete(item_id):
            raise HTTPException(status_code=404, detail="Knowledge item not found.")
        return {"status": "deleted", "id": item_id}

    return Router(path="/api/knowledge", route_handlers=[
        list_knowledge, add_knowledge, search_knowledge, delete_knowledge,
    ])

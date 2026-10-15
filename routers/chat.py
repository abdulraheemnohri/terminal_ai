"""Chat-related read-only routes extracted from the legacy application module."""
from __future__ import annotations

from typing import Any, Callable

from litestar import Router, get


def create_chat_router(list_runs: Callable[[], dict[str, Any]]) -> Router:
    """Build chat observability routes around an injected metadata provider."""

    @get("/runs")
    async def chat_runs() -> dict[str, Any]:
        """Return recent execution metadata; the provider must omit prompts and answers."""
        return list_runs()

    return Router(path="/api/chat", route_handlers=[chat_runs])

"""Liveness and readiness endpoints for process supervisors and reverse proxies."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from litestar import Router, get
from litestar.exceptions import HTTPException


def create_health_router(root_dir: Path, state_dir: Path) -> Router:
    root = Path(root_dir)
    state = Path(state_dir)

    @get("/healthz", include_in_schema=True)
    async def healthz() -> dict[str, str]:
        """Liveness: the HTTP process can answer requests."""
        return {"status": "ok", "service": "terminal-ai"}

    @get("/readyz", include_in_schema=True)
    async def readyz() -> dict[str, Any]:
        """Readiness: required source/UI files exist and the state directory is writable."""
        checks: dict[str, bool] = {
            "application": (root / "app.py").is_file(),
            "agent_engine": (root / "terminal_ai.py").is_file(),
            "web_ui": (root / "web" / "index.html").is_file(),
        }
        try:
            state.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix=".ready-", dir=state, delete=True):
                pass
            checks["state_writable"] = True
        except OSError:
            checks["state_writable"] = False
        if not all(checks.values()):
            failed = ", ".join(name for name, passed in checks.items() if not passed)
            raise HTTPException(status_code=503, detail=f"Readiness checks failed: {failed}")
        return {"status": "ready", "checks": checks}

    return Router(path="", route_handlers=[healthz, readyz])

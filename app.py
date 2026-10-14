"""Terminal AI web application powered by Litestar.

The web server is the primary interface. The legacy engine module is imported as
a library; its interactive terminal entry point is intentionally not used.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from litestar import Litestar, get, post, patch
from litestar.exceptions import HTTPException
from litestar.response import Response
from litestar.static_files import create_static_files_router

import terminal_ai as core

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
WEB_SETTINGS = core.STATE_DIR / "web_settings.json"
_AGENT: core.Agent | None = None
_BACKEND: core.Backend | None = None
_ENGINE_ERROR: str | None = None
_LOCK = asyncio.Lock()
_STARTED_AT = time.time()


def _load_env() -> None:
    env_path = ROOT / ".env"
    manager = core.EnvManager(env_file=env_path, workspace=ROOT) if env_path.is_file() else core.EnvManager(workspace=ROOT)
    manager.load(apply=True)


def _read_settings() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "mode": os.environ.get("TERMINAL_AI_MODE", "auto"),
        "autonomy": 0,
        "self_critique": False,
        "proactive": False,
        "max_ctx_chars": 12000,
    }
    try:
        saved = json.loads(WEB_SETTINGS.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            defaults.update(saved)
    except (OSError, json.JSONDecodeError):
        pass
    if defaults.get("mode") not in {"auto", "cloud", "local", "hybrid"}:
        defaults["mode"] = "auto"
    defaults["autonomy"] = 0  # Web default stays tool-disabled until explicitly enabled in a future guarded UI.
    return defaults


def _write_settings(settings: dict[str, Any]) -> None:
    WEB_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    WEB_SETTINGS.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def _build_agent() -> core.Agent:
    global _BACKEND, _ENGINE_ERROR
    _ENGINE_ERROR = None
    settings_data = _read_settings()
    _load_env()
    env_mgr = core.EnvManager(env_file=ROOT / ".env", workspace=ROOT) if (ROOT / ".env").is_file() else core.EnvManager(workspace=ROOT)
    env_mgr.load(apply=True)

    registry = core.ModelRegistry()
    downloader = core.AutoDownloader(registry)
    router = core.TaskRouter(registry)
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    local_path = downloader.find_local_model()
    cloud: core.Backend | None = None
    local: core.Backend | None = None
    mode = settings_data["mode"]

    if key and mode in {"auto", "cloud", "hybrid"}:
        try:
            cloud = core.GeminiBackend(
                model=os.environ.get("TERMINAL_AI_GEMINI_MODEL", "gemini-3.8-flash"),
                api_key=key,
            )
        except Exception as exc:
            _ENGINE_ERROR = f"Cloud backend unavailable: {exc}"

    if local_path and mode in {"auto", "local", "hybrid"}:
        try:
            local = core.LiteRTBackend(local_path)
        except Exception as exc:
            if not _ENGINE_ERROR:
                _ENGINE_ERROR = f"Local backend unavailable: {exc}"

    if mode == "cloud":
        backend = cloud
    elif mode == "local":
        backend = local
    elif mode == "hybrid":
        backend = core.HybridBackend(cloud, local, router) if cloud or local else None
    else:
        backend = core.HybridBackend(cloud, local, router) if cloud and local else (cloud or local)

    if backend is None:
        _BACKEND = None
        detail = _ENGINE_ERROR or (
            "No model backend is available. Configure GEMINI_API_KEY in .env, "
            "or install LiteRT-LM and place a compatible .litertlm model in the models directory."
        )
        raise RuntimeError(detail)

    memory = core.Memory.load()
    graph = core.KnowledgeGraph.load()
    goals = core.GoalPlanner.load()
    journal = core.Journal()
    skills = core.SkillLibrary.load()
    meta = core.MetaLearner.load()
    forge = core.ToolForge()
    patterns = core.PatternLearner.load()
    stats = core.StatsTracker()
    sessions = core.SessionManager()
    backup = core.AutoBackup()
    dreamer = core.Dreamer(backend, memory, journal)
    tools = core.ToolRegistry(
        memory, graph, goals, journal, skills, forge, ROOT,
        confirm_shell=True, shell_timeout=30, dreamer=dreamer,
        env=env_mgr, ask_delete=True,
    )
    agent = core.Agent(
        backend, memory, graph, goals, journal, skills, meta, tools, forge,
        router, patterns, os.environ.get(
            "TERMINAL_AI_SYSTEM",
            "You are Terminal AI, a helpful assistant. Be accurate, concise, and transparent about uncertainty."
        ),
        autonomy=0,  # tools are disabled by default in the browser interface
        self_critique=bool(settings_data.get("self_critique", False)),
        proactive=bool(settings_data.get("proactive", False)),
        max_ctx_chars=int(settings_data.get("max_ctx_chars", 12000)),
        stats=stats, session_mgr=sessions, backup=backup,
    )
    _BACKEND = backend
    _ENGINE_ERROR = None
    agent.mode = mode
    return agent


def _get_agent() -> core.Agent:
    global _AGENT, _ENGINE_ERROR
    if _AGENT is None:
        try:
            _AGENT = _build_agent()
        except Exception as exc:
            _ENGINE_ERROR = str(exc)
            raise HTTPException(status_code=503, detail=_ENGINE_ERROR) from exc
    return _AGENT


@get("/")
async def index() -> Response:
    page = WEB_DIR / "index.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="Web UI file is missing.")
    return Response(content=page.read_text(encoding="utf-8"), media_type="text/html")


@get("/api/status")
async def status() -> dict[str, Any]:
    _load_env()
    settings = _read_settings()
    agent = _AGENT
    return {
        "name": "Terminal AI",
        "version": core.__version__,
        "interface": "Litestar Web UI",
        "ready": agent is not None and _BACKEND is not None,
        "backend": getattr(_BACKEND, "label", None),
        "mode": settings["mode"],
        "gemini_configured": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        "local_models": [p.name for p in core.MODELS_DIR.glob("*.litertlm")],
        "memory_facts": len(agent.memory.facts) if agent else len(core.Memory.load().facts),
        "active_goals": len(agent.goals.active()) if agent else len(core.GoalPlanner.load().active()),
        "uptime_seconds": int(time.time() - _STARTED_AT),
        "error": _ENGINE_ERROR,
        "state_dir": str(core.STATE_DIR),
    }


@post("/api/chat")
async def chat(data: dict[str, Any]) -> dict[str, Any]:
    message = str(data.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(message) > 20000:
        raise HTTPException(status_code=413, detail="Message is too long (20,000 characters max).")
    async with _LOCK:
        agent = _get_agent()
        try:
            answer = await asyncio.to_thread(agent.turn, message)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Model request failed: {exc}") from exc
        try:
            if agent.session_mgr:
                agent.session_mgr.save("web-session", agent.history)
        except Exception:
            pass
        return {
            "answer": answer,
            "backend": getattr(agent.backend, "label", "unknown"),
            "history_count": len(agent.history),
            "elapsed_seconds": round(time.time() - _STARTED_AT, 2),
        }


@post("/api/chat/clear")
async def clear_chat() -> dict[str, str]:
    async with _LOCK:
        agent = _get_agent()
        agent.reset()
    return {"status": "cleared"}


@get("/api/memory")
async def memory() -> dict[str, Any]:
    agent = _get_agent()
    return {
        "facts": agent.memory.facts[-100:],
        "corrections": agent.memory.corrections[-50:],
        "preferences": agent.memory.preferences,
        "episodes": agent.memory.episodes[-30:],
    }


@post("/api/memory")
async def remember(data: dict[str, Any]) -> dict[str, str]:
    key, value = str(data.get("key", "")).strip(), str(data.get("value", "")).strip()
    if not key or not value:
        raise HTTPException(status_code=400, detail="Both key and value are required.")
    if len(key) > 200 or len(value) > 4000:
        raise HTTPException(status_code=400, detail="Key or value exceeds the allowed length.")
    agent = _get_agent()
    agent.memory.add_fact(key, value, source="web-ui")
    return {"status": "saved", "key": key}


@post("/api/memory/forget")
async def forget_memory(data: dict[str, Any]) -> dict[str, Any]:
    key = str(data.get("key", "")).strip()
    if not key:
        raise HTTPException(status_code=400, detail="A key is required.")
    agent = _get_agent()
    return {"deleted": agent.memory.forget(key)}


@get("/api/goals")
async def goals() -> dict[str, Any]:
    agent = _get_agent()
    return {"goals": [g.to_dict() for g in agent.goals.goals]}


@post("/api/goals")
async def add_goal(data: dict[str, Any]) -> dict[str, Any]:
    text = str(data.get("text", "")).strip()
    if not text or len(text) > 2000:
        raise HTTPException(status_code=400, detail="Goal must be 1–2000 characters.")
    agent = _get_agent()
    goal = agent.goals.add(text)
    return {"goal": goal.to_dict()}


@post("/api/goals/{goal_id:str}/complete")
async def complete_goal(goal_id: str) -> dict[str, str]:
    agent = _get_agent()
    if not any(g.id == goal_id for g in agent.goals.goals):
        raise HTTPException(status_code=404, detail="Goal not found.")
    agent.goals.complete(goal_id)
    return {"status": "completed", "id": goal_id}


@get("/api/sessions")
async def sessions() -> dict[str, Any]:
    agent = _get_agent()
    return {"sessions": agent.session_mgr.list_sessions() if agent.session_mgr else []}


@get("/api/settings")
async def get_settings() -> dict[str, Any]:
    _load_env()
    settings = _read_settings()
    return {
        **settings,
        "gemini_configured": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        "state_dir": str(core.STATE_DIR),
        "models_dir": str(core.MODELS_DIR),
    }


@patch("/api/settings")
async def update_settings(data: dict[str, Any]) -> dict[str, Any]:
    current = _read_settings()
    if "mode" in data:
        mode = str(data["mode"]).lower()
        if mode not in {"auto", "cloud", "local", "hybrid"}:
            raise HTTPException(status_code=400, detail="Mode must be auto, cloud, local, or hybrid.")
        current["mode"] = mode
    if "self_critique" in data:
        current["self_critique"] = bool(data["self_critique"])
    if "proactive" in data:
        current["proactive"] = bool(data["proactive"])
    if "max_ctx_chars" in data:
        try:
            current["max_ctx_chars"] = max(2000, min(50000, int(data["max_ctx_chars"])))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="max_ctx_chars must be an integer.")
    _write_settings(current)
    # Settings that affect the backend take effect after the next chat initialization.
    global _AGENT
    if current["mode"] != getattr(_AGENT, "mode", None):
        if _AGENT is not None:
            try:
                _AGENT.backend.close()
            except Exception:
                pass
        _AGENT = None
    elif _AGENT is not None:
        _AGENT.self_critique = bool(current.get("self_critique", False))
        _AGENT.critic.enabled = _AGENT.self_critique and _AGENT.autonomy >= 3
        _AGENT.proactive = bool(current.get("proactive", False))
        _AGENT.max_ctx_chars = int(current.get("max_ctx_chars", 12000))
    return await get_settings()


app = Litestar(
    route_handlers=[
        index, status, chat, clear_chat, memory, remember, forget_memory,
        goals, add_goal, complete_goal, sessions, get_settings, update_settings,
        create_static_files_router(path="/static", directories=[str(WEB_DIR)], include_in_schema=False),
    ],
    debug=os.environ.get("TERMINAL_AI_DEBUG") == "1",
)

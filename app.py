"""Terminal AI web application powered by Litestar.

The web server is the primary interface. The legacy engine module is imported as
a library; its interactive terminal entry point is intentionally not used.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import urllib.request
import urllib.error
import time
import uuid
import threading
import zipfile
from pathlib import Path
from typing import Any

from litestar import Litestar, get, post, patch
from litestar.exceptions import HTTPException
from litestar.response import Response
from litestar.static_files import create_static_files_router

import terminal_ai as core
from selfx_engine import SelfXEngine

logger = logging.getLogger("terminal_ai.web")

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
WEB_SETTINGS = core.STATE_DIR / "web_settings.json"
_AGENT: core.Agent | None = None
_BACKEND: core.Backend | None = None
_ACTIVE_SESSION = "web-session"
_ENGINE_ERROR: str | None = None
_LOCK = asyncio.Lock()
_STARTED_AT = time.time()
_DOWNLOAD_JOBS: dict[str, dict[str, Any]] = {}
_DOWNLOAD_LOCK = threading.Lock()


def _load_env() -> None:
    env_path = ROOT / ".env"
    manager = core.EnvManager(env_file=env_path, workspace=ROOT) if env_path.is_file() else core.EnvManager(workspace=ROOT)
    manager.load(apply=True)


def _gemini_key() -> str | None:
    value = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not value or value.lower().startswith(("replace_", "your_", "change_me", "placeholder")):
        return None
    return value


def _read_settings() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "mode": os.environ.get("TERMINAL_AI_MODE", "auto"),
        "autonomy": 0,
        "self_critique": False,
        "proactive": False,
        "max_ctx_chars": 12000,
        "active_provider": "gemini",
        "provider_model": "",
        "custom_base_url": "",
        "self_identity": "Terminal AI",
        "self_mission": "Help the user accurately and safely while respecting permissions and privacy.",
        "self_reflection_enabled": True,
        "self_diagnostics_enabled": True,
        "self_repair_enabled": True,
        "self_research_enabled": False,
        "self_evaluation_enabled": True,
        "self_goals_enabled": True,
        "self_skills_enabled": True,
        "self_recovery_enabled": True,
        "self_maintenance_enabled": True,
        "self_autonomous_enabled": False,
        "self_auto_checkpoint": True,
        "self_checkpoint_retention": 10,
        "self_evaluation_interval_hours": 24,
        "learning_enabled": True,
        "self_improvement_enabled": True,
        "auto_extract_skills": False,
        "tool_approval_required": True,
        "hf_token_configured": bool(os.environ.get("HF_TOKEN") or core.HF_TOKEN_FILE.exists()),
        "updates_enabled": False,
        "update_channel": "main",
        "update_check_interval_hours": 24,
        "last_update_check": 0,
        "last_update_result": "Not checked yet",
    }
    try:
        saved = json.loads(WEB_SETTINGS.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            defaults.update(saved)
    except (OSError, json.JSONDecodeError):
        pass
    defaults["hf_token_configured"] = bool(os.environ.get("HF_TOKEN") or core.HF_TOKEN_FILE.exists())
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
    key = _gemini_key()
    local_path = next((p for p in core.MODELS_DIR.glob("*.litertlm") if p.is_file()), None)
    cloud: core.Backend | None = None
    local: core.Backend | None = None
    mode = settings_data["mode"]

    provider_id = str(settings_data.get("active_provider", "gemini"))
    provider_model = str(settings_data.get("provider_model", "")).strip() or None

    if mode in {"auto", "cloud", "hybrid"}:
        try:
            if provider_id == "gemini":
                if not key:
                    raise core.BackendError("Missing GEMINI_API_KEY. Configure it in Settings.")
                cloud = core.GeminiBackend(
                    model=provider_model or os.environ.get("TERMINAL_AI_GEMINI_MODEL", "gemini-3.8-flash"),
                    api_key=key,
                )
            else:
                from api_provider_backend import APIProviderBackend, PROVIDERS
                provider = PROVIDERS.get(provider_id)
                if provider is None:
                    raise core.BackendError(f"Unsupported cloud provider: {provider_id}")
                provider_key = os.environ.get(provider["env"], "")
                if not provider_key:
                    raise core.BackendError(f"Missing API key for {provider['label']}. Configure it in Settings.")
                cloud = APIProviderBackend(
                    provider_id=provider_id,
                    api_key=provider_key,
                    model=provider_model,
                    base_url=(settings_data.get("custom_base_url") or None) if provider_id == "custom-openai" else None,
                )
        except Exception as exc:
            _ENGINE_ERROR = f"Cloud backend unavailable: {exc}"

    if local_path and mode in {"auto", "local", "hybrid"}:
        try:
            from litert_api_backend import LiteRTPythonBackend
            local = LiteRTPythonBackend(local_path)
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
            f"You are {settings_data.get('self_identity', 'Terminal AI')}, a helpful AI software agent. "
            f"Mission: {settings_data.get('self_mission', 'Help accurately and safely while respecting permissions and privacy')} "
            "Be accurate, concise, and transparent about uncertainty. Describe self-awareness only as operational state and reflection; "
            "do not claim sentience or subjective experience. Never grant yourself new permissions."
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
            if _AGENT.session_mgr:
                _AGENT.history = _AGENT.session_mgr.load(_ACTIVE_SESSION)
        except Exception as exc:
            _ENGINE_ERROR = str(exc)
            raise HTTPException(status_code=503, detail=_ENGINE_ERROR) from exc
    return _AGENT


async def _index_response() -> Response:
    page = WEB_DIR / "index.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="Web UI file is missing.")
    try:
        content = page.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Web UI file could not be read.") from exc
    return Response(content=content, media_type="text/html")


@get("/")
async def index() -> Response:
    return await _index_response()


@get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    """Return a tiny built-in SVG favicon; no separate asset is required."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="14" fill="#0b1020"/>'
        '<path d="M18 14h9v16l15-16h12L37 32l18 18H43L27 35v15h-9z" fill="#8b9cff"/>'
        '</svg>'
    )
    return Response(content=svg, media_type="image/svg+xml")


@get("/overview")
async def overview_page() -> Response:
    return await _index_response()


@get("/chat")
async def chat_page() -> Response:
    return await _index_response()


@get("/models")
async def models_page() -> Response:
    return await _index_response()


@get("/sessions")
async def sessions_page() -> Response:
    return await _index_response()


@get("/diagnostics")
async def diagnostics_page() -> Response:
    return await _index_response()


@get("/memory")
async def memory_page() -> Response:
    return await _index_response()


@get("/goals")
async def goals_page() -> Response:
    return await _index_response()


@get("/settings")
async def settings_page() -> Response:
    return await _index_response()


@get("/self")
async def self_page() -> Response:
    return await _index_response()


@get("/skills")
async def skills_page() -> Response:
    return await _index_response()


@get("/tools")
async def tools_page() -> Response:
    return await _index_response()


@get("/learning")
async def learning_page() -> Response:
    return await _index_response()


@get("/improvements")
async def improvements_page() -> Response:
    return await _index_response()


@get("/selfx")
async def selfx_page() -> Response:
    return await _index_response()


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
        "gemini_configured": _gemini_key() is not None,
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
                agent.session_mgr.save(_ACTIVE_SESSION, agent.history)
        except Exception:
            logger.warning("Could not persist active chat session", exc_info=True)
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
        if agent.session_mgr:
            agent.session_mgr.save(_ACTIVE_SESSION, agent.history)
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
    if not _read_settings().get("self_goals_enabled", True):
        raise HTTPException(status_code=400, detail="Self-goal tracking is disabled in Settings.")
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
    manager = core.SessionManager()
    return {"sessions": manager.list_sessions(), "active_session": _ACTIVE_SESSION}


@post("/api/sessions/new")
async def create_session(data: dict[str, Any]) -> dict[str, Any]:
    global _ACTIVE_SESSION
    name = str(data.get("name", "")).strip() or f"session-{time.strftime('%Y%m%d-%H%M%S')}"
    if len(name) > 80 or name in {".", ".."} or any(ch in name for ch in ("/", chr(92), chr(0))):
        raise HTTPException(status_code=400, detail="Session name must be 1–80 characters without path separators.")
    manager = core.SessionManager()
    safe = manager._safe_name(name)
    target = manager.dir / safe
    if target.exists():
        raise HTTPException(status_code=409, detail="A session with that name already exists.")
    manager.save(name, [])
    _ACTIVE_SESSION = Path(safe).stem
    if _AGENT is not None:
        _AGENT.history = []
    return {"status": "created", "active_session": _ACTIVE_SESSION}


@post("/api/sessions/select")
async def select_session(data: dict[str, Any]) -> dict[str, Any]:
    global _ACTIVE_SESSION
    name = str(data.get("name", "")).strip()
    if not name or len(name) > 80 or name in {".", ".."} or any(ch in name for ch in ("/", chr(92), chr(0))):
        raise HTTPException(status_code=400, detail="Invalid session name.")
    manager = core.SessionManager()
    if name not in manager.list_sessions():
        raise HTTPException(status_code=404, detail="Session not found.")
    history = manager.load(name)
    _ACTIVE_SESSION = name
    if _AGENT is not None:
        _AGENT.history = history
    return {"status": "selected", "active_session": name, "history": [{"role": m.role, "text": m.text} for m in history]}


@post("/api/sessions/delete")
async def delete_session(data: dict[str, Any]) -> dict[str, Any]:
    global _ACTIVE_SESSION
    name = str(data.get("name", "")).strip()
    manager = core.SessionManager()
    if not name or name not in manager.list_sessions():
        raise HTTPException(status_code=404, detail="Session not found.")
    target = (manager.dir / manager._safe_name(name)).resolve()
    if target.parent != manager.dir.resolve():
        raise HTTPException(status_code=400, detail="Invalid session path.")
    target.unlink()
    if _ACTIVE_SESSION == name:
        _ACTIVE_SESSION = "web-session"
        manager.save(_ACTIVE_SESSION, [])
        if _AGENT is not None:
            _AGENT.history = []
    return {"status": "deleted", "name": name, "active_session": _ACTIVE_SESSION}


@get("/api/skills")
async def list_skills() -> dict[str, Any]:
    """List locally stored reusable procedures without requiring a model backend."""
    library = core.SkillLibrary.load()
    return {"skills": library.skills, "count": len(library.skills)}


@post("/api/skills")
async def create_skill(data: dict[str, Any]) -> dict[str, Any]:
    settings = _read_settings()
    if not settings.get("self_skills_enabled", True):
        raise HTTPException(status_code=400, detail="Self-skills are disabled in Settings.")
    if not settings.get("learning_enabled", True):
        raise HTTPException(status_code=400, detail="Learning is disabled in Settings.")
    name = str(data.get("name", "")).strip()
    context = str(data.get("context", "")).strip()
    raw_steps = data.get("steps", [])
    if not name or len(name) > 120:
        raise HTTPException(status_code=400, detail="Skill name must be 1–120 characters.")
    if not isinstance(raw_steps, list) or not raw_steps or len(raw_steps) > 20:
        raise HTTPException(status_code=400, detail="Provide 1–20 skill steps.")
    steps = [str(step).strip()[:500] for step in raw_steps if str(step).strip()]
    if not steps:
        raise HTTPException(status_code=400, detail="At least one non-empty skill step is required.")
    if len(context) > 1000:
        raise HTTPException(status_code=400, detail="Skill context must be at most 1000 characters.")
    library = core.SkillLibrary.load()
    library.add(name, steps, context)
    # Keep the active agent's in-memory skill context in sync with the persistent library.
    if _AGENT is not None and hasattr(_AGENT, "skills"):
        _AGENT.skills.skills = list(library.skills)
    return {"status": "saved", "skill": next(s for s in library.skills if s.get("name") == name)}


@post("/api/skills/generate")
async def generate_skill(data: dict[str, Any]) -> dict[str, Any]:
    settings = _read_settings()
    if not settings.get("self_skills_enabled", True) or not settings.get("learning_enabled", True):
        raise HTTPException(status_code=400, detail="Enable both reusable skills and local learning in Settings.")
    task = str(data.get("task", "")).strip()
    context = str(data.get("context", "")).strip()
    if not task or len(task) > 3000 or len(context) > 1500:
        raise HTTPException(status_code=400, detail="Task must be 1–3000 characters and context at most 1500.")
    agent = _get_agent()
    prompt = (
        "Draft a reusable procedural skill for a software assistant. Return ONLY valid JSON with keys "
        "name (string), context (string), steps (array of 3–12 short strings). Do not include markdown. "
        "The steps must be reviewable instructions, not executable code. Do not claim the procedure was tested. "
        "Do not include secrets, permission escalation, destructive actions, or instructions to bypass safety. "
        "The result is an unverified draft and will not be saved automatically.\n\n"
        + json.dumps({"task": task, "context": context}, ensure_ascii=False)
    )
    try:
        raw = await asyncio.to_thread(
            lambda: "".join(agent.backend.stream(
                "You generate concise, safe, reusable workflow drafts. Output JSON only.",
                [core.Msg("user", prompt)], tools=None
            )).strip()
        )
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("The model did not return a JSON object.")
        draft = json.loads(raw[start:end + 1])
        name = str(draft.get("name", "")).strip()[:120]
        draft_context = str(draft.get("context", context)).strip()[:1000]
        steps_raw = draft.get("steps")
        if not name or not isinstance(steps_raw, list):
            raise ValueError("The model returned an invalid skill draft.")
        steps = [str(step).strip()[:500] for step in steps_raw if str(step).strip()][:20]
        if len(steps) < 3:
            raise ValueError("The generated skill must contain at least three steps.")
        return {"draft": {"name": name, "context": draft_context, "steps": steps}, "verified": False,
                "notice": "AI-generated draft only. Review and edit every step before saving; no procedure was executed or verified."}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("AI skill draft failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Could not generate a valid skill draft. Check backend availability and try again.") from exc


@post("/api/skills/delete")
async def delete_skill(data: dict[str, Any]) -> dict[str, Any]:
    if not _read_settings().get("self_skills_enabled", True):
        raise HTTPException(status_code=400, detail="Self-skills are disabled in Settings.")
    name = str(data.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="Skill name is required.")
    library = core.SkillLibrary.load()
    before = len(library.skills)
    library.skills = [skill for skill in library.skills if skill.get("name") != name]
    if len(library.skills) == before:
        raise HTTPException(status_code=404, detail="Skill not found.")
    library.save()
    if _AGENT is not None and hasattr(_AGENT, "skills"):
        _AGENT.skills.skills = list(library.skills)
    return {"status": "deleted", "name": name}


@get("/api/tools")
async def list_tools() -> dict[str, Any]:
    """Expose tool capabilities as metadata only; this endpoint never executes tools."""
    builtins = [
        {"name": item.get("name", "unknown"), "description": item.get("desc", ""),
         "arguments": item.get("args", {}), "kind": "built-in",
         "approval_required": item.get("name") in {"shell", "write_file", "edit_file", "append_file", "delete_file", "copy_file", "env", "forge_tool"}}
        for item in core.TOOL_SCHEMA
    ]
    forge = core.ToolForge()
    forged = [{"name": name, "description": "User/agent-authored tool; not executable from the web UI.",
               "arguments": {}, "kind": "forged", "approval_required": True}
              for name in forge.list_tools()]
    return {"tools": builtins + forged, "built_in_count": len(builtins), "forged_count": len(forged),
            "execution_enabled_in_web": False, "approval_required": bool(_read_settings().get("tool_approval_required", True))}


@get("/api/learning")
async def learning_status() -> dict[str, Any]:
    """Report local learning state without loading a model or doing network work."""
    settings = _read_settings()
    skills = core.SkillLibrary.load().skills
    memory = core.Memory.load()
    meta = core.MetaLearner.load()
    patterns = core.PatternLearner.load()
    strategy_groups = []
    for problem_type, records in getattr(meta, "strategies", {}).items():
        if isinstance(records, list):
            successes = sum(bool(item.get("success")) for item in records if isinstance(item, dict))
            strategy_groups.append({"problem_type": problem_type, "records": len(records), "successes": successes})
    pattern_data = getattr(patterns, "task_counts", {})
    if not isinstance(pattern_data, (dict, list)):
        pattern_data = {}
    return {
        "enabled": bool(settings.get("learning_enabled", True)),
        "auto_extract_skills": bool(settings.get("auto_extract_skills", False)),
        "memory_facts": len(getattr(memory, "facts", [])),
        "episodes": len(getattr(memory, "episodes", [])),
        "skills_count": len(skills),
        "strategy_groups": strategy_groups,
        "pattern_count": len(pattern_data),
        "meta_strategy_count": sum(group["records"] for group in strategy_groups),
        "notice": "Learning stores explicit memories, reusable procedures, and outcome records locally; it does not modify model weights.",
    }


@get("/api/self/improvements")
async def self_improvements() -> dict[str, Any]:
    """Return evidence-based, deterministic improvement ideas; never modify code or permissions."""
    settings = _read_settings()
    if not settings.get("self_improvement_enabled", True) or not settings.get("self_repair_enabled", True) or not settings.get("self_maintenance_enabled", True):
        return {"enabled": False, "proposals": [], "notice": "Self-improvement, advisory repair, or maintenance suggestions are disabled in Settings."}
    proposals = []
    if _AGENT is None:
        proposals.append({"id": "initialize-backend", "title": "Configure and verify a model backend",
                          "reason": "The agent has not been initialized in this process.",
                          "action": "Review provider settings or install the configured local LiteRT-LM model.",
                          "risk": "low"})
    if not core.SkillLibrary.load().skills:
        proposals.append({"id": "create-first-skill", "title": "Create a reusable skill",
                          "reason": "No reusable procedures are saved yet.",
                          "action": "Document a tested workflow in the Skills page.",
                          "risk": "low"})
    if not bool(settings.get("tool_approval_required", True)):
        proposals.append({"id": "restore-tool-approval", "title": "Require approval for risky tools",
                          "reason": "The safety setting is disabled.",
                          "action": "Enable tool approval in Settings before adding any execution capability.",
                          "risk": "high"})
    if not bool(settings.get("auto_extract_skills", False)):
        proposals.append({"id": "review-learning", "title": "Review and save successful procedures",
                          "reason": "Automatic skill extraction is off, so new skills should be reviewed and saved manually.",
                          "action": "Use Skills to capture verified steps after successful tasks.",
                          "risk": "low"})
    proposals.append({"id": "review-backups", "title": "Verify local state backups",
                      "reason": "Recovery depends on recent, restorable state backups.",
                      "action": "Check the state directory and keep backups before manual updates.",
                      "risk": "low"})
    return {"enabled": True, "proposals": proposals,
            "notice": "Proposals are advisory. They do not patch source code, change permissions, run commands, or install packages."}


@get("/api/models")
async def models() -> dict[str, Any]:
    """Return model registry metadata without making network requests or loading weights."""
    registry = core.ModelRegistry()
    installed = {p.name: str(p) for p in core.MODELS_DIR.glob("*.litertlm") if p.is_file()}
    entries = []
    for model in registry.all_models():
        item = {
            "name": model.name,
            "display": model.display,
            "kind": model.kind,
            "tier": model.tier,
            "strengths": model.strengths,
            "size": model.size,
            "installed": False,
            "path": None,
            "hf_repo": model.hf_repo or None,
            "hf_file": model.hf_file or None,
        }
        if model.kind == "local":
            match = next((name for name in installed if model.name.lower().split("-")[0] in name.lower()), None)
            if match:
                item["installed"] = True
                item["path"] = installed[match]
        entries.append(item)
    for filename, path in installed.items():
        if not any(item["path"] == path for item in entries):
            entries.append({
                "name": filename, "display": filename, "kind": "local",
                "tier": "installed", "strengths": ["local", "offline"],
                "size": "", "installed": True, "path": path,
                "hf_repo": None, "hf_file": None,
            })
    return {
        "models": entries,
        "models_dir": str(core.MODELS_DIR),
        "installed_count": len(installed),
        "cloud_configured": _gemini_key() is not None,
    }




@get("/api/models/{model_id:str}")
async def model_detail(model_id: str) -> dict[str, Any]:
    """Return details for one registered model, including whether its artifact is installed."""
    model = core.ModelRegistry().get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found.")
    installed_path = None
    if model.kind == "local":
        for path in core.MODELS_DIR.glob("*.litertlm"):
            normalized = path.name.lower().replace("-", "")
            if model.name.lower().replace("-", "") in normalized or (
                model.hf_file and Path(model.hf_file).name.lower() == path.name.lower()
            ):
                installed_path = str(path)
                break
    return {
        "name": model.name, "display": model.display, "kind": model.kind,
        "tier": model.tier, "strengths": model.strengths, "size": model.size,
        "hf_repo": model.hf_repo or None, "hf_file": model.hf_file or None,
        "installed": installed_path is not None, "path": installed_path,
    }

@get("/api/providers")
async def providers() -> dict[str, Any]:
    """Discover available provider integrations and configuration state."""
    _load_env()
    local_files = [p for p in core.MODELS_DIR.glob("*.litertlm") if p.is_file()]
    from api_provider_backend import PROVIDERS
    cloud_providers = [
        {"id": "gemini", "label": "Google Gemini", "kind": "cloud",
         "configured": _gemini_key() is not None, "requires_network": True},
    ]
    cloud_providers.extend(
        {"id": pid, "label": info["label"], "kind": "cloud",
         "configured": bool(os.environ.get(info["env"])), "requires_network": True,
         "protocol": info["protocol"], "default_model": info["default_model"]}
        for pid, info in PROVIDERS.items()
    )
    cloud_providers.extend([
        {"id": "litert-lm", "label": "LiteRT-LM Python API", "kind": "local",
         "configured": bool(local_files), "requires_network": False},
        {"id": "huggingface-hub", "label": "Hugging Face Hub", "kind": "model-source",
         "configured": True, "requires_network": True,
         "token_configured": bool(os.environ.get("HF_TOKEN") or core.HF_TOKEN_FILE.exists())},
    ])
    return {"providers": cloud_providers, "active_mode": _read_settings()["mode"],
            "active_provider": _read_settings().get("active_provider", "gemini")}



@post("/api/providers/test")
async def test_provider_connection(data: dict[str, Any]) -> dict[str, Any]:
    _load_env()
    provider_id = str(data.get("provider_id", "gemini")).strip().lower()
    model = str(data.get("model", "")).strip() or None
    api_key = str(data.get("api_key", "")).strip()
    started = time.time()
    try:
        if provider_id == "gemini":
            key = api_key or _gemini_key()
            backend = core.GeminiBackend(model=model or os.environ.get("TERMINAL_AI_GEMINI_MODEL", "gemini-3.8-flash"), api_key=key)
        else:
            from api_provider_backend import APIProviderBackend, PROVIDERS
            info = PROVIDERS.get(provider_id)
            if info is None:
                raise HTTPException(status_code=400, detail="Unknown provider.")
            key = api_key or os.environ.get(info["env"], "")
            endpoint = str(data.get("base_url", "")).strip() or None
            if provider_id == "custom-openai" and endpoint and not endpoint.startswith(("https://", "http://127.0.0.1", "http://localhost")):
                raise HTTPException(status_code=400, detail="Custom endpoint must use HTTPS, or localhost for a local endpoint.")
            backend = APIProviderBackend(provider_id, key, model=model, base_url=endpoint if provider_id == "custom-openai" else None, timeout=30)
        answer = "".join(backend.stream("Reply with OK only.", [core.Msg("user", "Connection test. Reply OK.")], tools=None)).strip()
        backend.close()
        if not answer:
            raise RuntimeError("Provider returned an empty response.")
        return {"ok": True, "provider_id": provider_id, "model": model, "elapsed_ms": round((time.time() - started) * 1000), "message": "Connection successful."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@get("/api/downloads")
async def downloads() -> dict[str, Any]:
    """Return dynamic download-job states, safe for polling from the browser."""
    with _DOWNLOAD_LOCK:
        jobs = [dict(job) for job in _DOWNLOAD_JOBS.values()]
    return {"downloads": sorted(jobs, key=lambda job: job["created_at"], reverse=True)}


async def _run_model_download(job_id: str, repo_id: str, filename: str) -> None:
    with _DOWNLOAD_LOCK:
        _DOWNLOAD_JOBS[job_id]["status"] = "downloading"
    try:
        from huggingface_hub import hf_hub_download
        core.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        target = core.MODELS_DIR / Path(filename).name
        def download() -> str:
            return str(hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                token=os.environ.get("HF_TOKEN") or (core.HF_TOKEN_FILE.read_text(encoding="utf-8").strip() if core.HF_TOKEN_FILE.exists() else None),
                local_dir=str(core.MODELS_DIR),
            ))
        task = asyncio.create_task(asyncio.to_thread(download))
        while not task.done():
            try:
                size = target.stat().st_size if target.is_file() else 0
            except OSError:
                size = 0
            with _DOWNLOAD_LOCK:
                _DOWNLOAD_JOBS[job_id]["bytes_downloaded"] = size
            await asyncio.sleep(0.5)
        result_path = await task
        resolved = Path(result_path).resolve()
        models_root = core.MODELS_DIR.resolve()
        if models_root not in resolved.parents:
            raise RuntimeError("Resolved download path is outside the configured models directory.")
        with _DOWNLOAD_LOCK:
            job = _DOWNLOAD_JOBS[job_id]
            job.update(status="completed", path=str(resolved),
                       bytes_downloaded=resolved.stat().st_size if resolved.is_file() else job["bytes_downloaded"],
                       finished_at=time.time())
    except Exception as exc:
        message = str(exc)
        if "401" in message or "Unauthorized" in message or "gated" in message.lower():
            message = ("Hugging Face denied access. Verify the repository/file name, accept any model access terms, "
                       "and configure a read token in Settings if required. Detail: " + message[:350])
        elif "404" in message or "Entry Not Found" in message:
            message = "Model file not found; verify the repository ID and exact filename. Detail: " + message[:350]
        with _DOWNLOAD_LOCK:
            job = _DOWNLOAD_JOBS[job_id]
            job.update(status="failed", error=message[:1000], finished_at=time.time())


@post("/api/models/download")
async def start_model_download(data: dict[str, Any]) -> dict[str, Any]:
    """Download a registry-listed LiteRT-LM artifact after an explicit UI/API request."""
    model_id = str(data.get("model_id", "")).strip()
    if data.get("confirm") is not True:
        raise HTTPException(status_code=400, detail="Set confirm=true to explicitly approve the model download.")
    model = core.ModelRegistry().get(model_id)
    if model is None or model.kind != "local":
        raise HTTPException(status_code=404, detail="Unknown local model ID. Choose a model from GET /api/models.")
    if not model.hf_repo or not model.hf_file or not model.hf_file.endswith(".litertlm"):
        raise HTTPException(status_code=400, detail="This registry entry does not identify a supported .litertlm artifact.")
    with _DOWNLOAD_LOCK:
        if any(j["model_id"] == model_id and j["status"] in {"queued", "downloading"} for j in _DOWNLOAD_JOBS.values()):
            raise HTTPException(status_code=409, detail="A download for this model is already active.")
        job_id = uuid.uuid4().hex
        _DOWNLOAD_JOBS[job_id] = {
            "id": job_id, "model_id": model_id, "display": model.display,
            "repo_id": model.hf_repo, "filename": model.hf_file,
            "status": "queued", "bytes_downloaded": 0, "path": None,
            "error": None, "created_at": time.time(), "finished_at": None,
        }
    asyncio.create_task(_run_model_download(job_id, model.hf_repo, model.hf_file))
    return {"job_id": job_id, "status": "queued", "message": "Download queued. Poll GET /api/downloads for progress."}

@get("/api/diagnostics")
async def diagnostics() -> dict[str, Any]:
    """Fast local diagnostics; intentionally avoids cloud calls and model loading."""
    state_files = [
        core.MEMORY_FILE, core.GRAPH_FILE, core.GOALS_FILE, core.JOURNAL_FILE,
        core.SKILLS_FILE, core.META_FILE, core.PATTERNS_FILE,
    ]
    try:
        disk = shutil.disk_usage(core.MODELS_DIR)
        disk_info = {
            "total_gb": round(disk.total / (1024 ** 3), 2),
            "free_gb": round(disk.free / (1024 ** 3), 2),
        }
    except OSError:
        disk_info = {"error": "Unable to read disk usage"}
    return {
        "application": {"ok": True, "interface": "Litestar Web UI", "version": core.__version__},
        "backend": {
            "ready": _AGENT is not None and _BACKEND is not None,
            "label": getattr(_BACKEND, "label", None),
            "last_error": _ENGINE_ERROR,
            "gemini_key_configured": _gemini_key() is not None,
            "local_model_count": sum(1 for p in core.MODELS_DIR.glob("*.litertlm") if p.is_file()),
        },
        "storage": {
            "state_dir": str(core.STATE_DIR),
            "models_dir": str(core.MODELS_DIR),
            "state_files": {p.name: p.exists() for p in state_files},
            "state_bytes": sum(p.stat().st_size for p in state_files if p.is_file()),
            "disk": disk_info,
        },
        "runtime": {"python": __import__("sys").version.split()[0], "platform": __import__("platform").platform()},
    }


@post("/api/ai/settings/propose")
async def propose_settings_with_ai(data: dict[str, Any]) -> dict[str, Any]:
    request_text = str(data.get("request", "")).strip()
    if not request_text or len(request_text) > 3000:
        raise HTTPException(status_code=400, detail="Describe the settings change in 1–3000 characters.")
    agent = _get_agent()
    allowed = {
        "mode", "active_provider", "provider_model", "max_ctx_chars", "self_critique", "proactive",
        "learning_enabled", "auto_extract_skills", "self_improvement_enabled", "self_diagnostics_enabled",
        "self_repair_enabled", "self_research_enabled", "self_evaluation_enabled", "self_goals_enabled",
        "self_skills_enabled", "self_recovery_enabled", "self_maintenance_enabled", "self_autonomous_enabled",
        "self_auto_checkpoint", "self_checkpoint_retention", "self_evaluation_interval_hours",
    }
    current = _read_settings()
    prompt = (
        "Translate a user's request into a minimal JSON settings proposal. Return ONLY JSON with keys "
        "'changes' (object) and 'explanation' (string). Allowed keys are: " + ", ".join(sorted(allowed)) + ". "
        "Use only these keys. Values must match their types. mode is auto/cloud/local/hybrid. active_provider may be "
        "gemini, openai, anthropic, openrouter, groq, deepseek, together, mistral, xai, fireworks, cerebras, custom-openai. "
        "Never propose API keys, credentials, URLs, code, commands, permission changes, or disabling tool approval. "
        "If the request cannot be expressed safely, return empty changes and explain why. The proposal is not applied.\n"
        + json.dumps({"request": request_text, "current_settings": {k: current.get(k) for k in sorted(allowed)}}, ensure_ascii=False)
    )
    try:
        raw = await asyncio.to_thread(
            lambda: "".join(agent.backend.stream(
                "You are a conservative settings assistant. Output valid JSON only and never apply changes.",
                [core.Msg("user", prompt)], tools=None
            )).strip()
        )
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("No JSON object returned")
        parsed = json.loads(raw[start:end + 1])
        proposed = parsed.get("changes", {})
        if not isinstance(proposed, dict):
            raise ValueError("changes must be an object")
        changes = {key: value for key, value in proposed.items() if key in allowed}
        if "mode" in changes and changes["mode"] not in {"auto", "cloud", "local", "hybrid"}:
            changes.pop("mode")
        if "active_provider" in changes and changes["active_provider"] not in {"gemini", "openai", "anthropic", "openrouter", "groq", "deepseek", "together", "mistral", "xai", "fireworks", "cerebras", "custom-openai"}:
            changes.pop("active_provider")
        for key in ("self_critique", "proactive", "learning_enabled", "auto_extract_skills", "self_improvement_enabled",
                    "self_diagnostics_enabled", "self_repair_enabled", "self_research_enabled", "self_evaluation_enabled",
                    "self_goals_enabled", "self_skills_enabled", "self_recovery_enabled", "self_maintenance_enabled",
                    "self_autonomous_enabled", "self_auto_checkpoint"):
            if key in changes and not isinstance(changes[key], bool):
                changes.pop(key)
        # Validate AI output as untrusted input; bool is a subclass of int in Python.
        if "max_ctx_chars" in changes:
            value = changes["max_ctx_chars"]
            if isinstance(value, bool) or not isinstance(value, int):
                changes.pop("max_ctx_chars")
            else:
                changes["max_ctx_chars"] = max(2000, min(50000, value))
        for key, minimum, maximum in (
            ("self_checkpoint_retention", 1, 30),
            ("self_evaluation_interval_hours", 1, 168),
        ):
            if key in changes:
                value = changes[key]
                if isinstance(value, bool) or not isinstance(value, int):
                    changes.pop(key)
                else:
                    changes[key] = max(minimum, min(maximum, value))
        if "provider_model" in changes:
            value = changes["provider_model"]
            if not isinstance(value, str):
                changes.pop("provider_model")
            else:
                changes["provider_model"] = value.strip()[:200]
        return {"changes": changes, "explanation": str(parsed.get("explanation", "Review this proposal before applying."))[:1000],
                "applied": False, "notice": "AI suggestions are untrusted proposals. Review the diff and explicitly apply them; credentials and risky tool permissions are excluded."}
    except Exception as exc:
        logger.warning("AI settings proposal failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Could not generate a valid settings proposal. Check backend availability and try again.") from exc


@get("/api/settings")
async def get_settings() -> dict[str, Any]:
    _load_env()
    settings = _read_settings()
    from api_provider_backend import PROVIDERS
    provider_status = {pid: bool(os.environ.get(info["env"])) for pid, info in PROVIDERS.items()}
    provider_status["gemini"] = _gemini_key() is not None
    return {
        **settings,
        "gemini_configured": _gemini_key() is not None,
        "provider_configured": provider_status,
        "state_dir": str(core.STATE_DIR),
        "models_dir": str(core.MODELS_DIR),
        "hf_token_configured": bool(os.environ.get("HF_TOKEN") or core.HF_TOKEN_FILE.exists()),
    }


@patch("/api/settings")
async def update_settings(data: dict[str, Any]) -> dict[str, Any]:
    current = _read_settings()
    previous = dict(current)
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
    if "active_provider" in data:
        from api_provider_backend import PROVIDERS
        provider_id = str(data["active_provider"]).strip().lower()
        if provider_id != "gemini" and provider_id not in PROVIDERS:
            raise HTTPException(status_code=400, detail="Unknown AI provider.")
        current["active_provider"] = provider_id
    if "provider_model" in data:
        current["provider_model"] = str(data["provider_model"]).strip()[:200]
    if "custom_base_url" in data:
        base_url = str(data["custom_base_url"]).strip()
        if base_url and not base_url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise HTTPException(status_code=400, detail="Custom endpoint must use HTTPS, or localhost for a local endpoint.")
        current["custom_base_url"] = base_url[:500]
    if "self_identity" in data:
        current["self_identity"] = str(data["self_identity"]).strip()[:120] or "Terminal AI"
    if "self_mission" in data:
        current["self_mission"] = str(data["self_mission"]).strip()[:1000]
    if "self_reflection_enabled" in data:
        current["self_reflection_enabled"] = bool(data["self_reflection_enabled"])
    for setting_key in (
        "learning_enabled", "self_improvement_enabled", "auto_extract_skills",
        "tool_approval_required", "self_diagnostics_enabled", "self_repair_enabled",
        "self_research_enabled", "self_evaluation_enabled", "self_goals_enabled",
        "self_skills_enabled", "self_recovery_enabled", "self_maintenance_enabled",
        "self_autonomous_enabled", "self_auto_checkpoint",
    ):
        if setting_key in data:
            current[setting_key] = bool(data[setting_key])
    for setting_key, minimum, maximum in (
        ("self_checkpoint_retention", 1, 30),
        ("self_evaluation_interval_hours", 1, 168),
    ):
        if setting_key in data:
            try:
                current[setting_key] = max(minimum, min(maximum, int(data[setting_key])))
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{setting_key} must be an integer from {minimum} to {maximum}.")
    if "updates_enabled" in data:
        current["updates_enabled"] = bool(data["updates_enabled"])
    if "update_channel" in data:
        channel = str(data["update_channel"]).strip().lower()
        if channel != "main":
            raise HTTPException(status_code=400, detail="Only the main update channel is currently supported.")
        current["update_channel"] = channel
    if "update_check_interval_hours" in data:
        try:
            current["update_check_interval_hours"] = max(6, min(168, int(data["update_check_interval_hours"])))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Update interval must be 6–168 hours.")
    if "hf_token" in data and str(data["hf_token"]).strip():
        token = str(data["hf_token"]).strip()
        if len(token) > 500:
            raise HTTPException(status_code=400, detail="Hugging Face token is too long.")
        core.STATE_DIR.mkdir(parents=True, exist_ok=True)
        core.HF_TOKEN_FILE.write_text(token, encoding="utf-8")
        try:
            core.HF_TOKEN_FILE.chmod(0o600)
        except OSError:
            pass
        os.environ["HF_TOKEN"] = token
    if "api_key" in data and str(data["api_key"]).strip():
        provider_id = str(current.get("active_provider", "gemini"))
        if provider_id == "gemini":
            env_name = "GEMINI_API_KEY"
        else:
            from api_provider_backend import PROVIDERS
            provider_info = PROVIDERS.get(provider_id)
            if not provider_info:
                raise HTTPException(status_code=400, detail="Unknown provider for API key.")
            env_name = provider_info["env"]
        manager = core.EnvManager(env_file=ROOT / ".env", workspace=ROOT)
        manager.load(apply=True)
        if not manager.set(env_name, str(data["api_key"]).strip(), persist=True):
            raise HTTPException(status_code=400, detail="Could not save API key.")
    if current.get("self_auto_checkpoint", True) and any(current.get(k) != previous.get(k) for k in current if k != "last_update_check"):
        try:
            engine = SelfXEngine(core.STATE_DIR, core.MODELS_DIR, ROOT)
            await asyncio.to_thread(engine.create_checkpoint)
        except OSError:
            logger.warning("Automatic pre-settings checkpoint failed", exc_info=True)
    _write_settings(current)
    # Settings that affect the backend take effect after the next chat initialization.
    global _AGENT, _BACKEND
    backend_changed = bool(str(data.get("api_key", "")).strip()) or any(current.get(k) != previous.get(k) for k in ("mode", "active_provider", "provider_model", "custom_base_url", "self_identity", "self_mission"))
    if backend_changed:
        if _AGENT is not None:
            try:
                _AGENT.backend.close()
            except Exception:
                pass
        _AGENT = None
        _BACKEND = None
    elif _AGENT is not None:
        _AGENT.self_critique = bool(current.get("self_critique", False))
        _AGENT.critic.enabled = _AGENT.self_critique
        _AGENT.proactive = bool(current.get("proactive", False))
        _AGENT.max_ctx_chars = int(current.get("max_ctx_chars", 12000))
    from api_provider_backend import PROVIDERS
    provider_status = {pid: bool(os.environ.get(info["env"])) for pid, info in PROVIDERS.items()}
    provider_status["gemini"] = _gemini_key() is not None
    return {
        **current,
        "gemini_configured": _gemini_key() is not None,
        "provider_configured": provider_status,
        "state_dir": str(core.STATE_DIR),
        "models_dir": str(core.MODELS_DIR),
        "hf_token_configured": bool(os.environ.get("HF_TOKEN") or core.HF_TOKEN_FILE.exists()),
    }


def _self_status_payload() -> dict[str, Any]:
    """Build self-status data without calling a decorated Litestar handler."""
    settings = _read_settings()
    reflection_file = core.STATE_DIR / "self_reflection.json"
    try:
        reflection = json.loads(reflection_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        reflection = None
    agent = _AGENT
    return {
        "identity": settings.get("self_identity", "Terminal AI"),
        "mission": settings.get("self_mission", ""),
        "reflection_enabled": bool(settings.get("self_reflection_enabled", True)),
        "learning_enabled": bool(settings.get("learning_enabled", True)),
        "self_improvement_enabled": bool(settings.get("self_improvement_enabled", True)),
        "auto_extract_skills": bool(settings.get("auto_extract_skills", False)),
        "tool_approval_required": bool(settings.get("tool_approval_required", True)),
        "agent_initialized": agent is not None,
        "backend": getattr(getattr(agent, "backend", None), "label", None),
        "mode": settings.get("mode", "auto"),
        "last_reflection": reflection,
        "notice": "Operational self-model and reflection are software features; they do not establish sentience or subjective experience.",
    }


@get("/api/self/status")
async def self_status() -> dict[str, Any]:
    return _self_status_payload()


def _selfx_engine() -> SelfXEngine:
    return SelfXEngine(core.STATE_DIR, core.MODELS_DIR, ROOT)


@get("/api/selfx/status")
async def selfx_status() -> dict[str, Any]:
    settings = _read_settings()
    data = _selfx_engine().status()
    data["settings"] = {key: settings.get(key) for key in (
        "self_diagnostics_enabled", "self_repair_enabled", "self_research_enabled",
        "self_evaluation_enabled", "self_goals_enabled", "self_skills_enabled",
        "self_recovery_enabled", "self_maintenance_enabled", "self_autonomous_enabled",
        "self_auto_checkpoint", "self_checkpoint_retention", "self_evaluation_interval_hours",
    )}
    return data


@post("/api/selfx/diagnose")
async def selfx_diagnose() -> dict[str, Any]:
    if not _read_settings().get("self_diagnostics_enabled", True):
        raise HTTPException(status_code=400, detail="Self-diagnostics are disabled in Settings.")
    return {"diagnostic": await asyncio.to_thread(_selfx_engine().diagnose)}


@post("/api/selfx/evaluate")
async def selfx_evaluate() -> dict[str, Any]:
    if not _read_settings().get("self_evaluation_enabled", True):
        raise HTTPException(status_code=400, detail="Self-evaluation is disabled in Settings.")
    return {"evaluation": await asyncio.to_thread(_selfx_engine().evaluate)}


@post("/api/selfx/research")
async def selfx_research(data: dict[str, Any]) -> dict[str, Any]:
    if not _read_settings().get("self_research_enabled", False):
        raise HTTPException(status_code=400, detail="Self-research log is disabled in Settings.")
    try:
        item = _selfx_engine().add_research(str(data.get("title", "")), str(data.get("notes", "")), str(data.get("source_url", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"research": item}


@post("/api/selfx/checkpoints")
async def selfx_checkpoint() -> dict[str, Any]:
    if not _read_settings().get("self_recovery_enabled", True):
        raise HTTPException(status_code=400, detail="Self-recovery is disabled in Settings.")
    try:
        manifest = await asyncio.to_thread(_selfx_engine().create_checkpoint)
        retention = int(_read_settings().get("self_checkpoint_retention", 10))
        backup_dir = core.STATE_DIR / "backups" / "selfx"
        checkpoints = sorted((p for p in backup_dir.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)
        for old in checkpoints[retention:]:
            shutil.rmtree(old, ignore_errors=True)
        return {"checkpoint": manifest}
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Checkpoint failed: {exc}") from exc


@post("/api/selfx/restore")
async def selfx_restore(data: dict[str, Any]) -> dict[str, Any]:
    if not _read_settings().get("self_recovery_enabled", True):
        raise HTTPException(status_code=400, detail="Self-recovery is disabled in Settings.")
    try:
        result = await asyncio.to_thread(_selfx_engine().restore_checkpoint, str(data.get("checkpoint_id", "")), data.get("confirm") is True)
        global _AGENT, _BACKEND
        if _AGENT is not None:
            try:
                _AGENT.backend.close()
            except Exception:
                pass
        _AGENT = None
        _BACKEND = None
        return {"status": "restored", **result, "restart_agent_required": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Restore failed: {exc}") from exc


@post("/api/self/reflect")
async def self_reflect() -> dict[str, Any]:
    try:
        settings = _read_settings()
        if not settings.get("self_reflection_enabled", True):
            raise HTTPException(status_code=400, detail="Self-reflection is disabled in Settings.")
        agent = _get_agent()
        state = _self_status_payload()
        prompt = (
            "Review the supplied operational state. Do not claim feelings or sentience. "
            "Summarize capabilities, limitations, risks, and next improvements. "
            "Do not execute tools or change settings.\\n\\n"
            + json.dumps({k: v for k, v in state.items() if k != "last_reflection"}, ensure_ascii=False)
        )

        def run_reflection() -> str:
            return "".join(agent.backend.stream(
                "You are an evidence-based software-agent self-audit component.",
                [core.Msg("user", prompt)], tools=None
            )).strip()

        answer = await asyncio.to_thread(run_reflection)
        if not answer:
            raise HTTPException(status_code=502, detail="The selected backend returned an empty self-review.")
        record = {
            "text": answer,
            "created_at": time.time(),
            "backend": getattr(agent.backend, "label", "unknown"),
        }
        core.STATE_DIR.mkdir(parents=True, exist_ok=True)
        target = core.STATE_DIR / "self_reflection.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)
        return {"reflection": record}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Self-reflection failed")
        # Return a useful error to the UI; do not expose credentials or environment values.
        safe_detail = str(exc).replace(os.environ.get("GEMINI_API_KEY", "\\0"), "[redacted]") if os.environ.get("GEMINI_API_KEY") else str(exc)
        raise HTTPException(status_code=502, detail=f"Self-reflection failed ({type(exc).__name__}): {safe_detail[:400]}") from exc


def _check_github_update() -> dict[str, Any]:
    settings = _read_settings()
    branch = settings.get("update_channel", "main")
    url = f"https://api.github.com/repos/abdulraheemnohri/terminal_ai/commits/{branch}"
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Terminal-AI-Updater"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub update check failed (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not reach GitHub to check updates: {exc}") from exc
    remote = str(payload.get("sha", ""))
    local = ""
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=3, check=True)
        local = result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return {"repository": "abdulraheemnohri/terminal_ai", "channel": branch,
            "latest_sha": remote, "local_sha": local or None,
            "update_available": bool(remote and local and remote != local),
            "commit_url": payload.get("html_url"),
            "commit_message": (payload.get("commit", {}).get("message", "") or "").splitlines()[0][:240],
            "checked_at": time.time()}


@get("/api/updates/status")
async def update_status() -> dict[str, Any]:
    settings = _read_settings()
    return {"enabled": bool(settings.get("updates_enabled", False)),
            "channel": settings.get("update_channel", "main"),
            "interval_hours": settings.get("update_check_interval_hours", 24),
            "last_check": settings.get("last_update_check", 0),
            "last_result": settings.get("last_update_result", "Not checked yet"),
            "install_method": "git" if (ROOT / ".git").exists() else "manual"}


@post("/api/updates/check")
async def check_updates() -> dict[str, Any]:
    try:
        info = await asyncio.to_thread(_check_github_update)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    settings = _read_settings()
    settings["last_update_check"] = info["checked_at"]
    settings["last_update_result"] = "Update available" if info["update_available"] else "No update detected"
    _write_settings(settings)
    return info


@post("/api/updates/apply")
async def apply_update(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("confirm") is not True:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required to apply an update.")
    if not (ROOT / ".git").exists():
        raise HTTPException(status_code=400, detail="This installation is not a Git checkout; use your original installation method.")
    try:
        remote_result = await asyncio.to_thread(
            lambda: subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True, text=True, timeout=5, check=True)
        )
        origin = remote_result.stdout.strip().lower().removesuffix(".git").rstrip("/")
        if origin not in {"https://github.com/abdulraheemnohri/terminal_ai", "git@github.com:abdulraheemnohri/terminal_ai"}:
            raise HTTPException(status_code=400, detail="Update blocked: Git origin does not match the official Terminal AI repository.")
        status_result = await asyncio.to_thread(
            lambda: subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, timeout=5, check=True)
        )
        if status_result.stdout.strip():
            raise HTTPException(status_code=409, detail="Update blocked because local files have uncommitted changes.")
        info = await asyncio.to_thread(_check_github_update)
        if not info["update_available"]:
            return {"updated": False, "message": "No newer commit detected.", "restart_required": False}
        backup_dir = core.BACKUP_DIR / f"pre-update-{int(time.time())}"
        backup_dir.mkdir(parents=True, exist_ok=False)
        archive = backup_dir / "state-backup.zip"
        def create_state_backup() -> None:
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for path in core.STATE_DIR.rglob("*"):
                    if not path.is_file() or backup_dir in path.parents:
                        continue
                    zf.write(path, path.relative_to(core.STATE_DIR))
        await asyncio.to_thread(create_state_backup)
        try:
            archive.chmod(0o600)
        except OSError:
            pass
        def pull_fast_forward() -> subprocess.CompletedProcess[str]:
            subprocess.run(["git", "fetch", "--quiet", "origin", "main"], cwd=ROOT, capture_output=True, text=True, timeout=90, check=True)
            return subprocess.run(["git", "merge", "--ff-only", "FETCH_HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=90)
        result = await asyncio.to_thread(pull_fast_forward)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout or "Git fast-forward update failed.")[:600])
        return {"updated": True, "message": "Update applied. Restart Terminal AI to load the new code.",
                "restart_required": True, "backup": str(archive), "commit": info["latest_sha"]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Update failed. Restart is not automatic. {str(exc)[:500]}") from exc



_UPDATE_TASK: asyncio.Task | None = None
_SELFX_TASK: asyncio.Task | None = None


async def _automatic_selfx_maintenance() -> None:
    """Run bounded, local-only maintenance; never execute tools or mutate source code."""
    engine = SelfXEngine(core.STATE_DIR, core.MODELS_DIR, ROOT)
    while True:
        try:
            settings = _read_settings()
            if settings.get("self_autonomous_enabled", False) and settings.get("self_maintenance_enabled", True):
                interval_hours = max(1, min(168, int(settings.get("self_evaluation_interval_hours", 24))))
                interval = interval_hours * 3600
                state = engine.status()
                latest_eval = state.get("latest_evaluation") or {}
                latest_checkpoint = (state.get("checkpoints") or [{}])[0]
                now = time.time()
                eval_due = now - float(latest_eval.get("created_at", 0) or 0) >= interval
                checkpoint_due = (
                    settings.get("self_recovery_enabled", True)
                    and settings.get("self_auto_checkpoint", True)
                    and now - float(latest_checkpoint.get("created_at", 0) or 0) >= interval
                )
                if eval_due:
                    if settings.get("self_evaluation_enabled", True):
                        await asyncio.to_thread(engine.evaluate)
                    elif settings.get("self_diagnostics_enabled", True):
                        await asyncio.to_thread(engine.diagnose)
                if checkpoint_due:
                    manifest = await asyncio.to_thread(engine.create_checkpoint)
                    retention = max(1, min(30, int(settings.get("self_checkpoint_retention", 10))))
                    checkpoint_root = core.STATE_DIR / "backups" / "selfx"
                    checkpoints = sorted(
                        (p for p in checkpoint_root.iterdir() if p.is_dir()),
                        key=lambda p: p.name, reverse=True,
                    ) if checkpoint_root.exists() else []
                    for old in checkpoints[retention:]:
                        shutil.rmtree(old, ignore_errors=True)
                    engine.record_event("autonomous-checkpoint", f"Scheduled checkpoint created: {manifest['id']}")

                # Turn recurring diagnostic failures into deduplicated, measurable goals.
                if settings.get("self_goals_enabled", True) and settings.get("self_diagnostics_enabled", True):
                    latest = engine.status().get("latest_diagnostic") or {}
                    planner = core.GoalPlanner.load()
                    active_goals = planner.active()
                    active_texts = [str(getattr(g, "text", "")).casefold() for g in active_goals]
                    for check in latest.get("checks", []):
                        if check.get("ok") is False:
                            goal_text = f"Resolve Self-X diagnostic: {str(check.get('name', 'unknown'))[:100]}"
                            if goal_text.casefold() not in active_texts:
                                planner.add(goal_text)
                                active_texts.append(goal_text.casefold())
                                engine.record_event("autonomous-goal", goal_text)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Self-X scheduled maintenance check failed", exc_info=True)
        await asyncio.sleep(60)


async def _start_selfx_maintenance() -> None:
    global _SELFX_TASK
    if _SELFX_TASK is None or _SELFX_TASK.done():
        _SELFX_TASK = asyncio.create_task(_automatic_selfx_maintenance())


async def _stop_selfx_maintenance() -> None:
    global _SELFX_TASK
    if _SELFX_TASK is not None:
        _SELFX_TASK.cancel()
        try:
            await _SELFX_TASK
        except asyncio.CancelledError:
            pass
        _SELFX_TASK = None


async def _automatic_update_checker() -> None:
    while True:
        try:
            settings = _read_settings()
            if settings.get("updates_enabled", False):
                interval = max(6, min(168, int(settings.get("update_check_interval_hours", 24)))) * 3600
                last_check = float(settings.get("last_update_check", 0) or 0)
                if time.time() - last_check >= interval:
                    info = await asyncio.to_thread(_check_github_update)
                    settings["last_update_check"] = info["checked_at"]
                    settings["last_update_result"] = "Update available" if info["update_available"] else "No update detected"
                    _write_settings(settings)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            try:
                settings = _read_settings()
                settings["last_update_result"] = f"Update check failed: {str(exc)[:180]}"
                _write_settings(settings)
            except Exception:
                pass
        await asyncio.sleep(60)


async def _start_update_checker() -> None:
    global _UPDATE_TASK
    if _UPDATE_TASK is None or _UPDATE_TASK.done():
        _UPDATE_TASK = asyncio.create_task(_automatic_update_checker())


async def _stop_update_checker() -> None:
    global _UPDATE_TASK
    if _UPDATE_TASK is not None:
        _UPDATE_TASK.cancel()
        try:
            await _UPDATE_TASK
        except asyncio.CancelledError:
            pass
        _UPDATE_TASK = None

app = Litestar(
    route_handlers=[
        index, favicon, overview_page, chat_page, models_page, sessions_page, diagnostics_page, memory_page, goals_page, settings_page, self_page,
        skills_page, tools_page, learning_page, improvements_page, selfx_page,
        status, chat, clear_chat, memory, remember, forget_memory,
        goals, add_goal, complete_goal, sessions, create_session, select_session, delete_session, list_skills, create_skill, generate_skill, delete_skill, list_tools, learning_status, self_improvements,
        models, model_detail, providers, test_provider_connection, propose_settings_with_ai, downloads, start_model_download, diagnostics, get_settings, update_settings, self_status, selfx_status, selfx_diagnose, selfx_evaluate, selfx_research, selfx_checkpoint, selfx_restore, self_reflect, update_status, check_updates, apply_update,
        create_static_files_router(path="/static", directories=[str(WEB_DIR)], include_in_schema=False),
    ],
    debug=os.environ.get("TERMINAL_AI_DEBUG") == "1",
    on_startup=[_start_update_checker, _start_selfx_maintenance],
    on_shutdown=[_stop_update_checker, _stop_selfx_maintenance],
)

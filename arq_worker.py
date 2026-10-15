"""Optional ARQ worker for bounded local maintenance jobs.

Run with: arq arq_worker.WorkerSettings
Requires requirements-queue.txt and a Redis instance reachable via REDIS_URL.
No job in this module runs arbitrary shell commands or edits source code.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

import terminal_ai as core
from command_control import CommandControl
from selfx_engine import SelfXEngine
from task_scheduler import TaskScheduler

ROOT = Path(__file__).resolve().parent
CONTROL = CommandControl(core.STATE_DIR / "command_control.sqlite3")
SCHEDULER = TaskScheduler(core.STATE_DIR / "scheduled_tasks.sqlite3")


def _settings() -> dict[str, Any]:
    try:
        value = json.loads((core.STATE_DIR / "web_settings.json").read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _engine() -> SelfXEngine:
    return SelfXEngine(core.STATE_DIR, core.MODELS_DIR, ROOT)


async def run_selfx_maintenance(manual: bool = False) -> dict[str, Any]:
    settings = _settings()
    if not manual and not settings.get("self_autonomous_enabled", False):
        return {"status": "skipped", "reason": "autonomous maintenance is disabled"}
    if not settings.get("self_maintenance_enabled", True):
        return {"status": "skipped", "reason": "self-maintenance is disabled"}

    engine = _engine()
    if settings.get("self_evaluation_enabled", True):
        evaluation = await asyncio.to_thread(engine.evaluate)
        diagnostic = engine.status().get("latest_diagnostic")
    elif settings.get("self_diagnostics_enabled", True):
        diagnostic = await asyncio.to_thread(engine.diagnose)
        evaluation = None
    else:
        return {"status": "skipped", "reason": "diagnostics and evaluation are disabled"}

    checkpoint_id = None
    profile = settings.get("self_autonomy_profile", "maintain")
    if profile != "observe" and settings.get("self_recovery_enabled", True) and settings.get("self_auto_checkpoint", True):
        manifest = await asyncio.to_thread(engine.create_checkpoint)
        checkpoint_id = manifest.get("id")
        retention = max(1, min(30, int(settings.get("self_checkpoint_retention", 10))))
        await asyncio.to_thread(engine.prune_checkpoints, retention)

    result = {"status": "completed", "profile": profile, "diagnostic": diagnostic,
              "evaluation": evaluation, "checkpoint_id": checkpoint_id, "manual": bool(manual)}
    CONTROL.audit("arq-worker", "selfx.maintenance.completed", "selfx",
                  {"profile": str(profile), "checkpoint_id": checkpoint_id, "manual": bool(manual)})
    return result


async def create_selfx_checkpoint(retention: int = 10) -> dict[str, Any]:
    engine = _engine()
    manifest = await asyncio.to_thread(engine.create_checkpoint)
    await asyncio.to_thread(engine.prune_checkpoints, max(1, min(30, int(retention))))
    CONTROL.audit("arq-worker", "selfx.checkpoint.created", str(manifest.get("id", "unknown")), {})
    return {"status": "completed", "checkpoint": manifest}


async def run_scheduled_task(task: dict[str, Any]) -> str:
    """Execute only the three scheduler's hard-coded maintenance job kinds."""
    if not isinstance(task, dict):
        raise ValueError("Scheduled task payload must be an object.")
    ident = str(task.get("id", ""))[:80]
    kind = str(task.get("kind", ""))
    if kind not in {"diagnostics", "backup_memory", "cleanup_temp"}:
        raise ValueError("Unsupported scheduled task type.")

    try:
        if kind == "diagnostics":
            result = await asyncio.to_thread(_engine().diagnose)
            summary = f"Diagnostics completed: {result.get('status', 'unknown')}"
        elif kind == "backup_memory":
            backup_dir = core.STATE_DIR / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            destination = backup_dir / f"memory-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}.sqlite3"
            source = sqlite3.connect(str(core.STATE_DIR / "long_term_memory.sqlite3"), timeout=15)
            target = sqlite3.connect(str(destination), timeout=15)
            try:
                source.execute("PRAGMA busy_timeout=15000")
                source.backup(target)
            finally:
                target.close()
                source.close()
            try:
                destination.chmod(0o600)
            except OSError:
                pass
            summary = f"Memory backup created: {destination.name}"
        else:
            removed = 0
            for path in ROOT.rglob("*.terminal-ai.tmp"):
                if path.is_file() and ROOT in path.resolve().parents:
                    path.unlink(missing_ok=True)
                    removed += 1
            summary = f"Removed {removed} temporary file(s)."

        if ident:
            SCHEDULER.mark(ident, summary)
        CONTROL.audit("arq-worker", "scheduled-task.completed", ident or kind,
                      {"kind": kind, "summary": summary[:300]})
        return summary
    except Exception as exc:
        if ident:
            SCHEDULER.mark(ident, "Failed: " + type(exc).__name__)
        CONTROL.audit("arq-worker", "scheduled-task.failed", ident or kind,
                      {"kind": kind, "reason": type(exc).__name__})
        raise


from arq.connections import RedisSettings


class WorkerSettings:
    functions = [run_selfx_maintenance, create_selfx_checkpoint, run_scheduled_task]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    max_jobs = 4
    job_timeout = 900
    keep_result = 3600

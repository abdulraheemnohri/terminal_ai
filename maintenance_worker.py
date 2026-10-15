"""Optional ARQ worker for longer local Self-X maintenance jobs.

Install requirements-queue.txt and run:
  arq maintenance_worker.WorkerSettings
Set REDIS_URL and TERMINAL_AI_ARQ_ENABLED=1 in the web process to enqueue jobs.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from arq.connections import RedisSettings
from selfx_engine import SelfXEngine
import terminal_ai as core


async def run_selfx_maintenance(ctx, include_checkpoint: bool = True) -> dict:
    project = Path(__file__).resolve().parent
    engine = SelfXEngine(core.STATE_DIR, core.MODELS_DIR, project)
    evaluation = await asyncio.to_thread(engine.evaluate)
    checkpoint_id = None
    if include_checkpoint:
        manifest = await asyncio.to_thread(engine.create_checkpoint)
        checkpoint_id = manifest.get("id")
        await asyncio.to_thread(engine.prune_checkpoints, 10)
    engine.record_event("arq-maintenance", "Queued Self-X maintenance completed")
    return {"status": "completed", "checkpoint_id": checkpoint_id,
            "evaluation": evaluation, "worker": "arq"}


async def create_selfx_checkpoint(ctx, retention: int = 10) -> dict:
    project = Path(__file__).resolve().parent
    engine = SelfXEngine(core.STATE_DIR, core.MODELS_DIR, project)
    manifest = await asyncio.to_thread(engine.create_checkpoint)
    await asyncio.to_thread(engine.prune_checkpoints, max(1, min(30, int(retention))))
    engine.record_event("arq-checkpoint", f"Queued checkpoint created: {manifest.get('id', 'unknown')}")
    return {"status": "completed", "checkpoint_id": manifest.get("id"), "worker": "arq"}


async def run_scheduled_task(ctx, task: dict) -> dict:
    """Execute only the scheduler's three registered safe maintenance task types."""
    from task_scheduler import TaskScheduler

    scheduler = TaskScheduler(core.STATE_DIR / "scheduled_tasks.sqlite3")
    ident = str(task.get("id", ""))
    kind = task.get("kind")
    try:
        if kind == "diagnostics":
            engine = SelfXEngine(core.STATE_DIR, core.MODELS_DIR, Path(__file__).resolve().parent)
            result = await asyncio.to_thread(engine.diagnose)
            summary = "Diagnostics completed"
        elif kind == "backup_memory":
            import sqlite3
            target = core.STATE_DIR / "backups"
            target.mkdir(parents=True, exist_ok=True)
            dest = target / ("memory-" + __import__("time").strftime("%Y%m%d-%H%M%S") + ".sqlite3")
            source = sqlite3.connect(str(core.STATE_DIR / "long_term_memory.sqlite3"), timeout=15)
            backup = sqlite3.connect(str(dest), timeout=15)
            try:
                source.backup(backup)
            finally:
                backup.close()
                source.close()
            result = {"backup": dest.name}
            summary = "Memory backup created: " + dest.name
        elif kind == "cleanup_temp":
            removed = 0
            root = Path(__file__).resolve().parent
            for path in root.rglob("*.terminal-ai.tmp"):
                if path.is_file() and root in path.resolve().parents:
                    path.unlink(missing_ok=True)
                    removed += 1
            result = {"removed": removed}
            summary = f"Removed {removed} temporary file(s)"
        else:
            raise ValueError("Unsupported scheduled task type")
        scheduler.mark(ident, summary)
        return {"status": "completed", "summary": summary, "result": result}
    except Exception as exc:
        scheduler.mark(ident, "Failed: " + type(exc).__name__)
        raise


class WorkerSettings:
    functions = [run_selfx_maintenance, create_selfx_checkpoint, run_scheduled_task]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    max_jobs = 2
    job_timeout = 900

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


class WorkerSettings:
    functions = [run_selfx_maintenance, create_selfx_checkpoint]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    max_jobs = 2
    job_timeout = 900

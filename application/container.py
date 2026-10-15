"""Central construction of long-lived application services.

This module wires infrastructure dependencies but deliberately contains no HTTP
handlers, agent decisions, or request-specific business logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.memory import MemoryStore
from command_control import CommandControl
from task_scheduler import TaskScheduler
from workspace_tools import WorkspaceTools


@dataclass(frozen=True)
class RuntimeServices:
    """Long-lived local services shared by Litestar route handlers."""

    memory: MemoryStore
    workspace: WorkspaceTools
    scheduler: TaskScheduler
    command_control: CommandControl

    @classmethod
    def create(cls, *, state_dir: Path, workspace_root: Path) -> "RuntimeServices":
        """Construct services using explicit filesystem roots."""
        state_dir = Path(state_dir).resolve()
        workspace_root = Path(workspace_root).resolve()
        state_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            memory=MemoryStore(state_dir / "long_term_memory.sqlite3"),
            workspace=WorkspaceTools(workspace_root),
            scheduler=TaskScheduler(state_dir / "scheduled_tasks.sqlite3"),
            command_control=CommandControl(state_dir / "command_control.sqlite3"),
        )

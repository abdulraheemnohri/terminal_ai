"""Workspace API routes with typed requests, explicit approval, and audit events."""
from __future__ import annotations

import subprocess
from typing import Any, Callable
from pathlib import Path

from litestar import Router, get, post
from litestar.exceptions import HTTPException

from api_schemas import WorkspaceExecuteRequest, WorkspaceReadRequest, WorkspaceWriteRequest
from command_control import CommandControl
from workspace_tools import WorkspaceTools


def create_workspace_router(
    workspace: WorkspaceTools,
    control: CommandControl,
    settings_reader: Callable[[], dict[str, Any]],
) -> Router:
    def ensure_enabled() -> None:
        if not settings_reader().get("workspace_tools_enabled", True):
            raise HTTPException(status_code=403, detail="Workspace tools are disabled in Settings.")

    @get("/")
    async def workspace_list(path: str = ".") -> dict[str, Any]:
        ensure_enabled()
        try:
            return {"workspace": str(workspace.workspace), "path": path, "items": workspace.list_files(path)}
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @post("/read")
    async def workspace_read(data: WorkspaceReadRequest) -> dict[str, Any]:
        ensure_enabled()
        try:
            return {"path": data.path, "content": workspace.read_file(data.path)}
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @post("/write")
    async def workspace_write(data: WorkspaceWriteRequest) -> dict[str, Any]:
        ensure_enabled()
        if not data.approved:
            raise HTTPException(status_code=403, detail="Explicit approval is required.")
        try:
            result = {"status": "written", **workspace.write_file(data.path, data.content, approved=True)}
            control.audit("user", "workspace.file.written", result.get("path", data.path),
                          {"bytes": result.get("bytes", 0), "approved": True})
            return result
        except (ValueError, PermissionError) as exc:
            control.audit("user", "workspace.file.write_rejected", data.path, {"reason": type(exc).__name__})
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @post("/execute")
    async def workspace_execute(data: WorkspaceExecuteRequest) -> dict[str, Any]:
        ensure_enabled()
        if not data.approved:
            raise HTTPException(status_code=403, detail="Explicit approval is required.")
        command = Path(data.argv[0]).name if data.argv else ""
        policy = control.get_policy()
        if command in set(policy.get("blocklist", [])) or command not in set(policy.get("allowlist", [])):
            control.audit("user", "workspace.command.blocked", command or "invalid-argv",
                          {"approved": True, "reason": "control-center policy denied executable"})
            raise HTTPException(status_code=403, detail="Command is blocked by the Command Control Center policy.")
        control.audit("user", "workspace.command.approved", command,
                      {"approved": True, "timeout": data.timeout})
        try:
            result = workspace.run_command(data.argv, approved=True, timeout=data.timeout)
            control.audit("user", "workspace.command.completed", command,
                          {"returncode": result.get("returncode"), "approved": True})
            return result
        except subprocess.TimeoutExpired as exc:
            control.audit("user", "workspace.command.timeout", command, {"approved": True})
            raise HTTPException(status_code=408, detail="Command timed out.") from exc
        except (ValueError, PermissionError) as exc:
            control.audit("user", "workspace.command.rejected", command,
                          {"approved": True, "reason": type(exc).__name__})
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Router(path="/api/workspace", route_handlers=[
        workspace_list, workspace_read, workspace_write, workspace_execute,
    ])

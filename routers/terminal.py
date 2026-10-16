"""Approval-bound terminal execution for the Terminal AI control center.

Commands run as argv (never through a shell), inside the configured workspace,
and only after a matching, recent Command Control Center approval is consumed.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

from litestar import Router, get, post
from litestar.exceptions import HTTPException

from command_control import CommandControl
from workspace_tools import WorkspaceTools

_MAX_ARGV = 64
_MAX_ARG_LENGTH = 4000
_SHELL_TOKENS = {"&&", "||", ";", "|", ">", "<", "`", "$(", "${"}


def _validate_argv(argv: object) -> list[str]:
    if not isinstance(argv, list) or not argv or len(argv) > _MAX_ARGV:
        raise HTTPException(status_code=400, detail=f"argv must contain between 1 and {_MAX_ARGV} arguments.")
    if any(not isinstance(arg, str) or len(arg) > _MAX_ARG_LENGTH or "\x00" in arg for arg in argv):
        raise HTTPException(status_code=400, detail="Every argument must be text of at most 4000 characters.")
    if any(arg in _SHELL_TOKENS for arg in argv):
        raise HTTPException(status_code=400, detail="Shell operators are not accepted; pass a program and separate arguments.")
    if not argv[0].strip():
        raise HTTPException(status_code=400, detail="Executable cannot be empty.")
    return argv


def create_terminal_router(workspace: WorkspaceTools, control: CommandControl) -> Router:
    """Create terminal routes with an explicit, auditable approval lifecycle."""

    @get("/api/terminal/status")
    async def terminal_status() -> dict[str, Any]:
        policy = control.get_policy()
        return {
            "workspace": str(workspace.workspace),
            "execution_mode": "argv-only; shell disabled",
            "approval_required": True,
            "auto_execute": False,
            "allowlist": policy.get("allowlist", []),
            "blocklist": policy.get("blocklist", []),
            "pending_count": len(control.list_pending("pending", 500)),
            "notice": "Commands execute only after a recent approval for the exact arguments. No shell expansion or chaining.",
        }

    @post("/api/terminal/queue")
    async def queue_terminal_command(data: dict[str, Any]) -> dict[str, Any]:
        argv = _validate_argv(data.get("argv"))
        cwd = data.get("cwd", ".")
        timeout = data.get("timeout", 30)
        if not isinstance(cwd, str) or len(cwd) > 1000:
            raise HTTPException(status_code=400, detail="cwd must be a relative workspace path.")
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 120:
            raise HTTPException(status_code=400, detail="timeout must be an integer between 1 and 120 seconds.")
        try:
            target = workspace.resolve(cwd)
            if not target.is_dir():
                raise ValueError("Working directory must exist and be a directory.")
            policy = control.get_policy()
            command = Path(argv[0]).name
            if command in set(policy.get("blocklist", [])) or command not in set(policy.get("allowlist", [])):
                raise PermissionError("Executable is not permitted by the Command Control Center policy.")
            operation = control.queue("terminal", "execute", {
                "argv": argv,
                "cwd": str(target.relative_to(workspace.workspace)),
                "timeout": timeout,
            })
        except HTTPException:
            raise
        except (ValueError, PermissionError, OSError) as exc:
            raise HTTPException(status_code=403 if isinstance(exc, PermissionError) else 400, detail=str(exc)) from exc
        control.audit("user", "terminal.command.queued", operation["id"], {
            "executable": command, "argument_count": len(argv), "cwd": str(target.relative_to(workspace.workspace)),
            "timeout": timeout,
        })
        return {
            "operation": operation,
            "notice": "Queued for review. Visit Command Control Center and approve this exact operation before execution.",
            "execute_url": f"/api/terminal/execute/{operation['id']}",
        }

    @post("/api/terminal/execute/{operation_id:str}")
    async def execute_terminal_command(operation_id: str) -> dict[str, Any]:
        operation = control.get_operation(operation_id)
        if not operation:
            raise HTTPException(status_code=404, detail="Terminal operation not found.")
        if operation.get("tool") != "terminal" or operation.get("operation") != "execute":
            raise HTTPException(status_code=400, detail="Approval is not for a terminal command.")
        arguments = operation.get("arguments")
        if not isinstance(arguments, dict):
            raise HTTPException(status_code=400, detail="Stored terminal operation is malformed.")
        argv = _validate_argv(arguments.get("argv"))
        cwd = arguments.get("cwd", ".")
        timeout = arguments.get("timeout", 30)
        try:
            target = workspace.resolve(cwd)
            if not target.is_dir():
                raise ValueError("Working directory must exist and be a directory.")
            command = Path(argv[0]).name
            policy = control.get_policy()
            if command in set(policy.get("blocklist", [])) or command not in set(policy.get("allowlist", [])):
                raise PermissionError("Executable is no longer permitted by the current policy.")
            claimed = control.claim_approved(
                operation_id, "terminal", "execute", arguments, max_age_seconds=600
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PermissionError as exc:
            control.audit("system", "terminal.command.blocked", operation_id, {"executable": command})
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if not claimed:
            raise HTTPException(status_code=409, detail="No matching approved terminal operation is available.")
        control.audit("user", "terminal.command.started", operation_id, {
            "executable": command, "cwd": str(target.relative_to(workspace.workspace)), "timeout": timeout,
        })
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                argv,
                cwd=target,
                text=True,
                capture_output=True,
                timeout=max(1, min(int(timeout), 120)),
                shell=False,
                check=False,
                env=os.environ.copy(),
            )
            payload = {
                "operation_id": operation_id,
                "returncode": result.returncode,
                "stdout": result.stdout[-30000:],
                "stderr": result.stderr[-15000:],
                "cwd": str(target),
                "executable": command,
            }
            control.finish_operation(operation_id, success=result.returncode == 0,
                                     note=f"exit={result.returncode}")
            control.audit("user", "terminal.command.completed", operation_id, {
                "executable": command, "returncode": result.returncode,
            })
            return payload
        except subprocess.TimeoutExpired as exc:
            control.finish_operation(operation_id, success=False, note="timed out")
            control.audit("user", "terminal.command.timeout", operation_id, {"executable": command})
            raise HTTPException(status_code=408, detail="Terminal command timed out; the approval has been consumed.") from exc
        except OSError as exc:
            control.finish_operation(operation_id, success=False, note=type(exc).__name__)
            control.audit("user", "terminal.command.failed", operation_id, {"executable": command, "reason": type(exc).__name__})
            raise HTTPException(status_code=400, detail=f"Could not start terminal command ({type(exc).__name__}).") from exc

    return Router(path="", route_handlers=[terminal_status, queue_terminal_command, execute_terminal_command])

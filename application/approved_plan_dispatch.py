"""Prepare an exact terminal operation for a tracked plan without executing it."""
from __future__ import annotations

from pathlib import Path
from typing import Any

MAX_ARGV = 64
MAX_ARG_LENGTH = 4000
SHELL_TOKENS = {"&&", "||", ";", "|", ">", "<", "`", "$(", "${"}
SHELL_COMMAND_FLAGS = {"-c", "--command"}


def validate_argv(argv: object) -> list[str]:
    if not isinstance(argv, list) or not argv or len(argv) > MAX_ARGV:
        raise ValueError(f"argv must contain between 1 and {MAX_ARGV} arguments")
    if any(not isinstance(arg, str) or len(arg) > MAX_ARG_LENGTH or "\x00" in arg for arg in argv):
        raise ValueError("Every argument must be text of at most 4000 characters")
    if any(arg in SHELL_TOKENS for arg in argv) or any(arg in SHELL_COMMAND_FLAGS for arg in argv):
        raise ValueError("Shell operators and shell command flags are not accepted")
    if not argv[0].strip():
        raise ValueError("Executable cannot be empty")
    return argv


def prepare_plan_operation(*, task_id: str, argv: object, cwd: object, timeout: object,
                           control: Any, workspace: Any, task_lifecycle: Any) -> dict[str, Any]:
    """Queue a plan-linked operation for review; never consumes approval or executes it."""
    task = task_lifecycle.get(task_id)
    if task is None:
        raise KeyError("task not found")
    if task.get("status") != "planned" or task.get("operation_id"):
        raise ValueError("only an unlinked planned task can receive a new operation")

    safe_argv = validate_argv(argv)
    if not isinstance(cwd, str) or not cwd.strip() or len(cwd) > 1000:
        raise ValueError("cwd must be a relative workspace directory")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 120:
        raise ValueError("timeout must be an integer from 1 to 120 seconds")

    target = workspace.resolve(cwd)
    if not target.is_dir():
        raise ValueError("Working directory must exist and be a directory")
    relative_cwd = str(target.relative_to(workspace.workspace))
    executable = Path(safe_argv[0]).name
    policy = control.get_policy()
    if executable in set(policy.get("blocklist", [])) or executable not in set(policy.get("allowlist", [])):
        raise PermissionError("Executable is not permitted by the current Command Control Center policy")

    operation = control.queue("terminal", "execute", {
        "argv": safe_argv, "cwd": relative_cwd, "timeout": timeout,
    })
    try:
        linked = task_lifecycle.link_operation(task_id, operation)
    except Exception:
        # Do not leave an accidentally executable pending operation if linking failed.
        try:
            control.review(operation["id"], False, "system", "Task linking failed; operation rejected")
        finally:
            raise
    control.audit("agentic", "task.terminal_operation_queued", task_id, {
        "operation_id": operation["id"], "executable": executable,
        "argument_count": len(safe_argv), "cwd": relative_cwd,
        "approval_required": True, "execution_started": False,
    })
    return {
        "task": linked,
        "operation": operation,
        "execute_url": f"/api/terminal/execute/{operation['id']}",
        "execution_started": False,
        "notice": "Operation linked and queued for human approval. Approve it in Command Control Center, then explicitly execute it. Queueing did not run the command.",
    }

"""One-shot dispatch bridge between Command Control approvals and ToolRegistry."""
from __future__ import annotations

from typing import Any

from agentic_runtime import ToolRegistry
from command_control import CommandControl


def execute_approved_operation(
    control: CommandControl,
    registry: ToolRegistry,
    operation_id: str,
    *,
    max_output_chars: int = 12000,
) -> dict[str, Any]:
    """Execute only a reviewed operation whose exact canonical arguments still match.

    Approval is consumed atomically before dispatch. Failures are recorded and the same
    approval cannot be replayed. This function must only be called from an authenticated,
    CSRF-protected application endpoint or trusted local operator workflow.
    """
    queued = control.get_operation(operation_id)
    if queued is None:
        raise ValueError("Operation not found")
    if queued.get("status") != "approved":
        raise ValueError("Operation has no unused approval")
    tool_name = queued["tool"]
    if queued["operation"] != tool_name:
        raise ValueError("Operation identifier must match the registered tool name")

    # Claim uses the values read from storage; any separately supplied arguments must not
    # be accepted here. The claim method checks stored tool/operation/arguments and expiry.
    claimed = control.claim_approved(
        operation_id, tool_name, tool_name, queued["arguments"],
    )
    if claimed is None:
        raise ValueError("Operation not found")

    result = registry.execute(
        tool_name, claimed["arguments"], approved=True,
        max_output_chars=max(100, min(int(max_output_chars), 50000)),
    )
    if result.ok:
        control.finish_operation(
            operation_id, success=True,
            note="tool completed; duration_ms=" + str(result.duration_ms),
        )
        return {
            "operation_id": operation_id, "status": "executed",
            "tool": tool_name, "ok": True, "output": result.output,
            "duration_ms": result.duration_ms,
        }

    control.finish_operation(
        operation_id, success=False,
        note=(result.error or "tool failed")[:450],
    )
    return {
        "operation_id": operation_id, "status": "failed",
        "tool": tool_name, "ok": False, "error": result.error,
        "duration_ms": result.duration_ms,
    }

"""Modular Command Control Center routes; approval never executes an operation."""
from __future__ import annotations
import asyncio
from typing import Any
import yaml
from litestar import Router, WebSocket, get, patch, post, websocket
from litestar.exceptions import HTTPException
from litestar.response import Response
from api_schemas import CommandPolicyPatch, QueueOperationRequest, ReviewOperationRequest, SkillPackageRequest, YAMLImportRequest
from command_control import CommandControl

def create_control_router(control: CommandControl) -> Router:
    @get("/policy")
    async def get_policy() -> dict[str, Any]:
        return {"policy": control.get_policy(), "execution_enabled": False,
                "notice": "Global auto-execution remains disabled. Approval records never execute commands."}

    @patch("/policy")
    async def patch_policy(data: CommandPolicyPatch) -> dict[str, Any]:
        try:
            policy = control.update_policy(data.model_dump(exclude_unset=True))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"policy": policy, "execution_enabled": False}

    @get("/pending")
    async def pending(status: str = "pending", limit: int = 100) -> dict[str, Any]:
        if status not in {"pending", "approved", "rejected", "executing", "executed", "failed", "expired"}:
            raise HTTPException(status_code=400, detail="Invalid operation status.")
        return {"operations": control.list_pending(status, limit), "status": status, "allowed_statuses": ["pending", "approved", "rejected", "executing", "executed", "failed", "expired"]}

    @post("/pending")
    async def queue_operation(data: QueueOperationRequest) -> dict[str, Any]:
        try:
            item = control.queue(data.tool, data.operation, data.arguments)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"operation": item, "notice": "Queued for human review; queueing does not execute it."}

    @post("/pending/{operation_id:str}/review")
    async def review_operation(operation_id: str, data: ReviewOperationRequest) -> dict[str, Any]:
        try:
            item = control.review(operation_id, data.approve, "user", data.note)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if item is None:
            raise HTTPException(status_code=404, detail="Pending operation not found.")
        return {"operation": item, "executed": False,
                "notice": "Review decision recorded. This endpoint never executes the operation."}

    @get("/audit")
    async def audit(limit: int = 100) -> dict[str, Any]:
        return {"entries": control.list_audit(limit), "integrity": control.verify_audit(),
                "append_only": True, "storage": "sqlite-wal-hash-chain"}

    @get("/skills/export")
    async def export_skills() -> dict[str, Any]:
        return control.export_skills()

    @post("/skills/import")
    async def import_skills(data: SkillPackageRequest) -> dict[str, Any]:
        try:
            return control.import_skills(data.model_dump(mode="json"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @get("/skills/export.yaml")
    async def export_skills_yaml() -> Response:
        return Response(content=yaml.safe_dump(control.export_skills(), sort_keys=False, allow_unicode=True),
                        media_type="application/yaml")

    @post("/skills/import.yaml")
    async def import_skills_yaml(data: YAMLImportRequest) -> dict[str, Any]:
        try:
            payload = yaml.safe_load(data.content)
            validated = SkillPackageRequest.model_validate(payload)
            return control.import_skills(validated.model_dump(mode="json"))
        except yaml.YAMLError as exc:
            raise HTTPException(status_code=400, detail="Invalid skill YAML.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid skill package: {str(exc)[:300]}") from exc

    @websocket("/events")
    async def events(socket: WebSocket) -> None:
        """Stream operational event summaries, never prompts or hidden reasoning."""
        await socket.accept()
        last_seq = 0
        try:
            await socket.send_json({"type": "connected", "message": "Operational events connected."})
            while True:
                for entry in reversed(control.list_audit(100)):
                    seq = int(entry["seq"])
                    if seq > last_seq:
                        await socket.send_json({
                            "type": "action_event", "seq": seq, "timestamp": entry["timestamp"],
                            "actor": entry["actor"], "action": entry["action"], "target": entry["target"],
                            "details": entry["details"], "entry_hash": entry["entry_hash"],
                        })
                        last_seq = seq
                # Receive with a short timeout so client disconnects are observed; a send-only
                # loop otherwise keeps the WebSocket task alive and can hang TestClient shutdown.
                try:
                    await asyncio.wait_for(socket.receive_text(), timeout=0.75)
                except asyncio.TimeoutError:
                    pass
        except Exception:
            return

    return Router(path="/api/control", route_handlers=[
        get_policy, patch_policy, pending, queue_operation, review_operation, audit,
        export_skills, import_skills, export_skills_yaml, import_skills_yaml, events,
    ])

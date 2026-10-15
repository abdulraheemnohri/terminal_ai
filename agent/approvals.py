"""Human approval gate and auditable decisions for agent actions."""
from __future__ import annotations
import json, time, uuid
from pathlib import Path
from typing import Any

class ApprovalStore:
    """Persistent approval requests. Approval is per request and expires; no blanket grants."""
    def __init__(self, path: str | Path, *, ttl_seconds: int = 600):
        if not 30 <= ttl_seconds <= 86400: raise ValueError("ttl_seconds must be 30..86400")
        self.path, self.ttl_seconds = Path(path), ttl_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: list[dict[str, Any]] = []
        self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list): self._items = data[-2000:]
        except (OSError, json.JSONDecodeError): self._items = []

    def _save(self):
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._items[-2000:], indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def request(self, *, tool: str, arguments: dict[str, Any], risk: str, reason: str) -> dict[str, Any]:
        if not tool.strip(): raise ValueError("tool is required")
        if risk not in {"low", "medium", "high", "critical"}: raise ValueError("invalid risk")
        now = time.time()
        item = {"id": uuid.uuid4().hex, "tool": tool, "arguments": arguments,
                "risk": risk, "reason": reason[:1000], "created_at": now,
                "expires_at": now+self.ttl_seconds, "status": "pending", "decision_at": None}
        self._items.append(item); self._save()
        return dict(item)

    def decide(self, request_id: str, *, approve: bool, actor: str) -> dict[str, Any]:
        if not actor.strip(): raise ValueError("actor is required")
        for item in self._items:
            if item["id"] != request_id: continue
            if item["status"] != "pending": raise ValueError("request already decided")
            if item["expires_at"] <= time.time():
                item["status"] = "expired"; item["decision_at"] = time.time(); self._save()
                raise ValueError("approval request expired")
            item["status"] = "approved" if approve else "rejected"
            item["decision_at"], item["actor"] = time.time(), actor[:120]
            self._save(); return dict(item)
        raise KeyError("approval request not found")

    def can_execute(self, request_id: str, *, tool: str) -> bool:
        item = next((x for x in self._items if x["id"] == request_id), None)
        return bool(item and item["tool"] == tool and item["status"] == "approved"
                    and item["expires_at"] > time.time()
                    and item.get("consumed_at") is None
                    and item["risk"] not in {"high", "critical"})

    def consume(self, request_id: str, *, tool: str) -> bool:
        """Consume a low/medium approval once; high/critical must always be freshly reviewed by caller."""
        if not self.can_execute(request_id, tool=tool): return False
        item = next(x for x in self._items if x["id"] == request_id)
        item["consumed_at"] = time.time(); self._save(); return True

    def pending(self) -> list[dict[str, Any]]:
        now = time.time()
        changed = False
        for item in self._items:
            if item["status"] == "pending" and item["expires_at"] <= now:
                item["status"], item["decision_at"], changed = "expired", now, True
        if changed: self._save()
        return [dict(x) for x in self._items if x["status"] == "pending"]

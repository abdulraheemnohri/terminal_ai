"""Command control, approval queue, append-only audit, and skill exchange.

This module never executes an approved command by itself. Approval records authorize
a separately invoked, policy-checked operation; this avoids turning a click into
unreviewed arbitrary execution.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

DEFAULT_POLICY = {
    "auto_execute": False,
    "tool_auto_execute": {},
    "allowlist": ["pwd", "ls", "cat", "head", "tail", "grep", "find", "git", "python", "python3", "pytest", "ruff"],
    "blocklist": ["rm", "sudo", "su", "chmod", "chown", "mkfs", "dd", "shutdown", "reboot", "curl", "wget"],
}
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


class CommandControl:
    def __init__(self, db_path: Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _init(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS control_settings(
                id INTEGER PRIMARY KEY CHECK(id=1), policy_json TEXT NOT NULL, updated_at REAL NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS pending_operations(
                id TEXT PRIMARY KEY, tool TEXT NOT NULL, operation TEXT NOT NULL,
                arguments_json TEXT NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL,
                reviewed_at REAL, reviewer TEXT, note TEXT NOT NULL DEFAULT '')""")
            db.execute("""CREATE TABLE IF NOT EXISTS audit_log(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
                timestamp REAL NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
                target TEXT NOT NULL, details_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL UNIQUE)""")
            db.execute("""CREATE TABLE IF NOT EXISTS skill_packages(
                id TEXT PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL,
                description TEXT NOT NULL, steps_json TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL, created_at REAL NOT NULL)""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS audit_log_no_update
                BEFORE UPDATE ON audit_log BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
                BEFORE DELETE ON audit_log BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END""")
            row = db.execute("SELECT id FROM control_settings WHERE id=1").fetchone()
            if not row:
                db.execute("INSERT INTO control_settings VALUES(1,?,?)",
                           (json.dumps(DEFAULT_POLICY), time.time()))
                self._audit(db, "system", "control.initialized", "command-control", {"safe_defaults": True})

    def _audit(self, db, actor: str, action: str, target: str, details: dict[str, Any]):
        previous = db.execute("SELECT entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
        previous_hash = previous["entry_hash"] if previous else "0" * 64
        record = {"event_id": uuid.uuid4().hex, "timestamp": time.time(), "actor": actor[:80],
                  "action": action[:100], "target": target[:240],
                  "details": details, "previous_hash": previous_hash}
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        db.execute("INSERT INTO audit_log(event_id,timestamp,actor,action,target,details_json,previous_hash,entry_hash) VALUES(?,?,?,?,?,?,?,?)",
                   (record["event_id"], record["timestamp"], record["actor"], record["action"],
                    record["target"], json.dumps(details, ensure_ascii=False), previous_hash, digest))
        return {**record, "entry_hash": digest}

    def audit(self, actor: str, action: str, target: str, details: dict[str, Any] | None = None):
        with self._connect() as db:
            return self._audit(db, actor, action, target, details or {})

    def list_audit(self, limit=100):
        limit = max(1, min(int(limit), 500))
        with self._connect() as db:
            rows = db.execute("SELECT * FROM audit_log ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r, details=json.loads(r["details_json"])) for r in rows]

    def verify_audit(self):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM audit_log ORDER BY seq").fetchall()
        previous = "0" * 64
        for row in rows:
            record = {"event_id": row["event_id"], "timestamp": row["timestamp"], "actor": row["actor"],
                      "action": row["action"], "target": row["target"],
                      "details": json.loads(row["details_json"]), "previous_hash": row["previous_hash"]}
            digest = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"),
                                               ensure_ascii=False).encode("utf-8")).hexdigest()
            if row["previous_hash"] != previous or row["entry_hash"] != digest:
                return {"valid": False, "checked": row["seq"], "reason": "hash-chain mismatch"}
            previous = digest
        return {"valid": True, "checked": len(rows), "head": previous}

    def get_policy(self):
        with self._connect() as db:
            row = db.execute("SELECT policy_json,updated_at FROM control_settings WHERE id=1").fetchone()
        policy = dict(DEFAULT_POLICY)
        policy.update(json.loads(row["policy_json"]))
        return {**policy, "updated_at": row["updated_at"]}

    def update_policy(self, data: dict[str, Any]):
        policy = self.get_policy()
        if "auto_execute" in data:
            if not isinstance(data["auto_execute"], bool):
                raise ValueError("auto_execute must be a boolean")
            policy["auto_execute"] = data["auto_execute"]
        if "tool_auto_execute" in data:
            tools = data["tool_auto_execute"]
            if not isinstance(tools, dict) or len(tools) > 100:
                raise ValueError("tool_auto_execute must be a map of at most 100 tools")
            if any(not SAFE_NAME.fullmatch(str(k)) or not isinstance(v, bool) for k, v in tools.items()):
                raise ValueError("Tool names must be simple identifiers and values must be booleans")
            policy["tool_auto_execute"] = tools
        for key in ("allowlist", "blocklist"):
            if key in data:
                values = data[key]
                if not isinstance(values, list) or len(values) > 100:
                    raise ValueError(f"{key} must be a list of at most 100 command names")
                if any(not isinstance(v, str) or not SAFE_NAME.fullmatch(v) for v in values):
                    raise ValueError(f"{key} entries must be simple executable names, not command strings")
                policy[key] = list(dict.fromkeys(values))
        # Hard-deny dangerous command names even if a user attempts to allow them.
        hard_deny = set(DEFAULT_POLICY["blocklist"])
        policy["allowlist"] = [name for name in policy["allowlist"] if name not in hard_deny]
        policy["auto_execute"] = False  # global auto-execution intentionally remains disabled
        with self._connect() as db:
            db.execute("UPDATE control_settings SET policy_json=?,updated_at=? WHERE id=1",
                       (json.dumps({k: policy[k] for k in DEFAULT_POLICY}, sort_keys=True), time.time()))
            self._audit(db, "user", "control.policy.updated", "command-control",
                        {"auto_execute": False, "allowlist_count": len(policy["allowlist"]),
                         "blocklist_count": len(policy["blocklist"]), "tool_rules_count": len(policy["tool_auto_execute"])})
        return self.get_policy()

    def queue(self, tool: str, operation: str, arguments: dict[str, Any]):
        tool, operation = str(tool).strip(), str(operation).strip()
        if not SAFE_NAME.fullmatch(tool) or not SAFE_NAME.fullmatch(operation):
            raise ValueError("Tool and operation names must be simple identifiers")
        if not isinstance(arguments, dict) or len(json.dumps(arguments, ensure_ascii=False)) > 12000:
            raise ValueError("Arguments must be a JSON object under 12 KB")
        ident = uuid.uuid4().hex
        with self._connect() as db:
            db.execute("INSERT INTO pending_operations VALUES(?,?,?,?,?,?,?,?,?)",
                       (ident, tool, operation, json.dumps(arguments, ensure_ascii=False), "pending",
                        time.time(), None, None, ""))
            self._audit(db, "agent", "operation.queued", ident, {"tool": tool, "operation": operation})
        return self.get_operation(ident)

    def get_operation(self, ident):
        with self._connect() as db:
            row = db.execute("SELECT * FROM pending_operations WHERE id=?", (ident,)).fetchone()
        return dict(row, arguments=json.loads(row["arguments_json"])) if row else None

    def list_pending(self, status="pending", limit=100):
        limit = max(1, min(int(limit), 500))
        with self._connect() as db:
            rows = db.execute("SELECT * FROM pending_operations WHERE status=? ORDER BY created_at DESC LIMIT ?",
                              (status, limit)).fetchall()
        return [dict(r, arguments=json.loads(r["arguments_json"])) for r in rows]

    def review(self, ident: str, approve: bool, reviewer="user", note=""):
        with self._connect() as db:
            row = db.execute("SELECT * FROM pending_operations WHERE id=?", (ident,)).fetchone()
            if not row:
                return None
            if row["status"] != "pending":
                raise ValueError("Operation has already been reviewed")
            status = "approved" if approve else "rejected"
            db.execute("UPDATE pending_operations SET status=?,reviewed_at=?,reviewer=?,note=? WHERE id=? AND status='pending'",
                       (status, time.time(), reviewer[:80], note[:500], ident))
            self._audit(db, reviewer, "operation." + status, ident,
                        {"tool": row["tool"], "operation": row["operation"], "note": note[:500]})
        return self.get_operation(ident)

    def export_skills(self):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM skill_packages ORDER BY created_at DESC").fetchall()
        return {"format": "terminal-ai-skills", "version": 1, "skills": [
            {"id": r["id"], "name": r["name"], "version": r["version"], "description": r["description"],
             "steps": json.loads(r["steps_json"]), "verified": bool(r["verified"]),
             "source": r["source"], "created_at": r["created_at"]} for r in rows]}

    def import_skills(self, payload: Any):
        if not isinstance(payload, dict) or payload.get("format") != "terminal-ai-skills" or payload.get("version") != 1:
            raise ValueError("Unsupported skill package format")
        skills = payload.get("skills")
        if not isinstance(skills, list) or not 1 <= len(skills) <= 100:
            raise ValueError("Package must contain 1–100 skills")
        imported = []
        with self._connect() as db:
            for item in skills:
                if not isinstance(item, dict):
                    raise ValueError("Each skill must be an object")
                name = str(item.get("name", "")).strip()
                version = str(item.get("version", "1.0.0")).strip()
                description = str(item.get("description", "")).strip()
                steps = item.get("steps")
                if not name or len(name) > 120 or not version or len(version) > 40 or len(description) > 1000:
                    raise ValueError("Invalid skill name, version, or description")
                if not isinstance(steps, list) or not 1 <= len(steps) <= 30 or any(not isinstance(s, str) or not s.strip() or len(s) > 1000 for s in steps):
                    raise ValueError(f"Skill '{name}' needs 1–30 non-empty steps of at most 1000 characters")
                ident = uuid.uuid4().hex
                db.execute("INSERT INTO skill_packages VALUES(?,?,?,?,?,?,?,?)",
                           (ident, name, version, description, json.dumps(steps, ensure_ascii=False),
                            0, "imported-unverified", time.time()))
                imported.append({"id": ident, "name": name, "version": version, "verified": False})
                self._audit(db, "user", "skill.imported", ident, {"name": name, "step_count": len(steps), "verified": False})
        return {"imported": imported, "notice": "Imported skills are unverified procedure text only; they are not executable."}

    def create_skill(self, data: dict[str, Any]):
        payload = {"format": "terminal-ai-skills", "version": 1, "skills": [data]}
        result = self.import_skills(payload)
        return result["imported"][0]

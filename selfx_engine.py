"""Local-first Self-X diagnostics, evaluation, research log, and recovery checkpoints.

This module deliberately performs no arbitrary command execution, network research,
source-code mutation, permission escalation, or model-weight training.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

STATE_FILES = (
    "memory.json", "graph.json", "goals.json", "journal.md", "skills.json",
    "meta.json", "tools.json", "patterns.json", "stats.json",
    "self_reflection.json", "selfx_state.json", "web_settings.json",
)
SECRET_NAMES = {"hf_token", ".env", "credentials.json", "secrets.json"}


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


class SelfXEngine:
    def __init__(self, state_dir: Path, models_dir: Path, project_dir: Path):
        self.state_dir = Path(state_dir)
        self.models_dir = Path(models_dir)
        self.project_dir = Path(project_dir)
        self.data_path = self.state_dir / "selfx_state.json"
        self.backup_dir = self.state_dir / "backups" / "selfx"

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.data_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {"version": 1, "diagnostics": [], "evaluations": [],
                "research": [], "checkpoints": [], "events": []}

    def _write(self, data: dict[str, Any]) -> None:
        _atomic_json(self.data_path, data)

    def _event(self, data: dict[str, Any], kind: str, summary: str) -> None:
        events = data.setdefault("events", [])
        events.append({"id": uuid.uuid4().hex[:12], "kind": kind,
                       "summary": summary[:240], "created_at": time.time()})
        del events[:-100]

    def diagnose(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def add(name: str, ok: bool, detail: str, severity: str = "info") -> None:
            checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:500],
                           "severity": severity if ok else ("warning" if severity == "info" else severity)})

        add("Python runtime", sys.version_info >= (3, 10), platform.python_version(),
            "info" if sys.version_info >= (3, 10) else "error")
        add("Operating system", True, f"{platform.system()} {platform.release()}")
        add("State directory", self.state_dir.is_dir() and os.access(self.state_dir, os.W_OK),
            str(self.state_dir), "info" if self.state_dir.is_dir() and os.access(self.state_dir, os.W_OK) else "error")
        add("Model directory", self.models_dir.is_dir(), str(self.models_dir),
            "info" if self.models_dir.is_dir() else "warning")
        local_models = sorted(p.name for p in self.models_dir.glob("*.litertlm") if p.is_file())
        add("Local LiteRT models", bool(local_models), ", ".join(local_models) if local_models else "No .litertlm files detected",
            "info" if local_models else "warning")
        lite_runtime = importlib.util.find_spec("litert_lm") is not None
        add("LiteRT-LM Python API", lite_runtime, "Installed" if lite_runtime else "Not installed",
            "info" if lite_runtime else "warning")
        disk = shutil.disk_usage(self.state_dir if self.state_dir.exists() else self.project_dir)
        add("Disk space", disk.free > 300 * 1024 * 1024,
            f"{disk.free // (1024 * 1024)} MiB free",
            "info" if disk.free > 300 * 1024 * 1024 else "warning")
        required = ["app.py", "terminal_ai.py", "litert_api_backend.py"]
        missing = [name for name in required if not (self.project_dir / name).is_file()]
        add("Core files", not missing, "All core files present" if not missing else "Missing: " + ", ".join(missing),
            "info" if not missing else "error")
        summary = {"id": uuid.uuid4().hex[:12], "created_at": time.time(),
                   "checks": checks, "passed": sum(c["ok"] for c in checks),
                   "total": len(checks), "status": "healthy" if all(c["ok"] for c in checks) else
                   ("degraded" if not any(c["severity"] == "error" for c in checks) else "attention")}
        data = self._read()
        data.setdefault("diagnostics", []).append(summary)
        del data["diagnostics"][:-30]
        self._event(data, "diagnostics", f"Ran {summary['total']} local checks: {summary['status']}")
        self._write(data)
        return summary

    def evaluate(self) -> dict[str, Any]:
        """Run a deterministic operational evaluation without network/model calls."""
        diagnosis = self.diagnose()
        models = [p for p in self.models_dir.glob("*.litertlm") if p.is_file()]
        checks = [
            {"name": "Core files", "passed": next((c["ok"] for c in diagnosis["checks"] if c["name"] == "Core files"), False)},
            {"name": "Writable state", "passed": next((c["ok"] for c in diagnosis["checks"] if c["name"] == "State directory"), False)},
            {"name": "LiteRT runtime available", "passed": next((c["ok"] for c in diagnosis["checks"] if c["name"] == "LiteRT-LM Python API"), False)},
            {"name": "Local model installed", "passed": bool(models)},
        ]
        score = round(100 * sum(c["passed"] for c in checks) / len(checks))
        result = {"id": uuid.uuid4().hex[:12], "created_at": time.time(), "score": score,
                  "checks": checks, "scope": "static local operational checks; not a language-quality benchmark"}
        data = self._read()
        data.setdefault("evaluations", []).append(result)
        del data["evaluations"][:-30]
        self._event(data, "evaluation", f"Operational readiness score {score}/100")
        self._write(data)
        return result

    def add_research(self, title: str, notes: str = "", source_url: str = "") -> dict[str, Any]:
        title = title.strip()
        notes = notes.strip()
        source_url = source_url.strip()
        if not title or len(title) > 200:
            raise ValueError("Research title must be 1–200 characters.")
        if len(notes) > 6000:
            raise ValueError("Research notes must be at most 6000 characters.")
        if source_url:
            parsed = urlparse(source_url)
            if parsed.scheme not in {"https", "http"} or not parsed.netloc:
                raise ValueError("Source URL must be a valid HTTP(S) URL.")
        item = {"id": uuid.uuid4().hex[:12], "title": title, "notes": notes,
                "source_url": source_url, "status": "unverified",
                "created_at": time.time(),
                "trust_notice": "External material is untrusted until independently verified."}
        data = self._read()
        data.setdefault("research", []).append(item)
        del data["research"][:-100]
        self._event(data, "research", f"Saved research note: {title}")
        self._write(data)
        return item

    def create_checkpoint(self) -> dict[str, Any]:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        destination = self.backup_dir / checkpoint_id
        destination.mkdir(parents=True, exist_ok=False)
        files = []
        for name in STATE_FILES:
            if name.lower() in SECRET_NAMES:
                continue
            source = self.state_dir / name
            if not source.is_file():
                continue
            payload = source.read_bytes()
            target = destination / name
            target.write_bytes(payload)
            files.append({"name": name, "bytes": len(payload),
                          "sha256": hashlib.sha256(payload).hexdigest()})
        manifest = {"id": checkpoint_id, "created_at": time.time(),
                    "files": files, "file_count": len(files),
                    "notice": "Secrets and API tokens are excluded."}
        _atomic_json(destination / "manifest.json", manifest)
        data = self._read()
        data.setdefault("checkpoints", []).append(manifest)
        del data["checkpoints"][:-30]
        self._event(data, "checkpoint", f"Created recovery checkpoint {checkpoint_id}")
        self._write(data)
        return manifest

    def restore_checkpoint(self, checkpoint_id: str, confirm: bool) -> dict[str, Any]:
        if not confirm:
            raise ValueError("Explicit confirmation is required to restore a checkpoint.")
        if not checkpoint_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in checkpoint_id):
            raise ValueError("Invalid checkpoint ID.")
        source_dir = self.backup_dir / checkpoint_id
        manifest_path = source_dir / "manifest.json"
        if not source_dir.is_dir() or not manifest_path.is_file():
            raise ValueError("Checkpoint not found.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        allowed = set(STATE_FILES) - SECRET_NAMES
        # Preserve current state before restoring any files.
        safety_backup = self.create_checkpoint()
        restored = []
        for item in manifest.get("files", []):
            name = item.get("name")
            if name not in allowed or Path(name).name != name:
                continue
            src = source_dir / name
            if not src.is_file():
                continue
            payload = src.read_bytes()
            if hashlib.sha256(payload).hexdigest() != item.get("sha256"):
                raise ValueError(f"Checkpoint integrity check failed for {name}.")
            target = self.state_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + ".restore-tmp")
            temporary.write_bytes(payload)
            temporary.replace(target)
            restored.append(name)
        data = self._read()
        self._event(data, "restore", f"Restored {len(restored)} state files from {checkpoint_id}")
        self._write(data)
        return {"restored": restored, "safety_checkpoint": safety_backup["id"],
                "checkpoint_id": checkpoint_id}

    def record_event(self, kind: str, summary: str) -> dict[str, Any]:
        """Persist a bounded, non-secret audit event for autonomous maintenance."""
        data = self._read()
        self._event(data, kind, summary)
        self._write(data)
        return data.get("events", [])[-1]

    def prune_checkpoints(self, retention: int) -> dict[str, Any]:
        """Remove expired checkpoint directories and stale manifest entries together."""
        retention = max(1, min(30, int(retention)))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        directories = sorted(
            (path for path in self.backup_dir.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        keep_ids = {path.name for path in directories[:retention]}
        removed = 0
        for path in directories[retention:]:
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
        data = self._read()
        existing = data.get("checkpoints", [])
        data["checkpoints"] = [
            item for item in existing
            if isinstance(item, dict) and item.get("id") in keep_ids
        ]
        self._event(data, "checkpoint-retention", f"Retained {len(keep_ids)} checkpoints; removed {removed}")
        self._write(data)
        return {"retained": len(keep_ids), "removed": removed}

    def status(self) -> dict[str, Any]:
        data = self._read()
        return {
            "diagnostics": data.get("diagnostics", [])[-10:],
            "latest_diagnostic": (data.get("diagnostics") or [None])[-1],
            "evaluations": data.get("evaluations", [])[-10:],
            "latest_evaluation": (data.get("evaluations") or [None])[-1],
            "research": list(reversed(data.get("research", [])[-50:])),
            "checkpoints": list(reversed(data.get("checkpoints", [])[-30:])),
            "events": list(reversed(data.get("events", [])[-50:])),
            "capabilities": [
                {"name": "Self-identity", "status": "available", "mode": "user-configured"},
                {"name": "Self-diagnostics", "status": "available", "mode": "local checks"},
                {"name": "Self-repair", "status": "advisory", "mode": "proposals only; no source edits"},
                {"name": "Self-research", "status": "manual", "mode": "local research log; source trust remains unverified"},
                {"name": "Self-evaluation", "status": "available", "mode": "deterministic operational checks"},
                {"name": "Self-goals", "status": "available", "mode": "existing goal planner"},
                {"name": "Self-skills", "status": "available", "mode": "reviewed reusable procedures"},
                {"name": "Self-learning", "status": "available", "mode": "local records; no weight training"},
                {"name": "Self-recovery", "status": "available", "mode": "verified state checkpoints"},
                {"name": "Self-maintenance", "status": "manual", "mode": "diagnose and propose; no autonomous updates"},
            ],
            "safety": {"autonomous_source_edits": False, "arbitrary_command_execution": False,
                       "permission_escalation": False, "model_weight_training": False},
        }

from __future__ import annotations

import os
from pathlib import Path

from litestar.testing import TestClient

import app as web_app
from app import app


def test_backup_controls_create_list_validate_and_download(tmp_path: Path, monkeypatch):
    backup_dir = tmp_path / "private-backups"
    monkeypatch.setenv("TERMINAL_AI_BACKUP_DIR", str(backup_dir))
    state_dir = Path(web_app.core.STATE_DIR)
    state_dir.mkdir(parents=True, exist_ok=True)
    sentinel = state_dir / "backup-api-test.txt"
    sentinel.write_text("backup-test", encoding="utf-8")
    try:
        with TestClient(app=app) as client:
            created = client.post("/api/operations/backups", json={})
            assert created.status_code == 201 or created.status_code == 200, created.text
            payload = created.json()
            assert payload["file_count"] >= 1
            assert Path(payload["path"]).parent == backup_dir.resolve()

            listed = client.get("/api/operations/backups")
            assert listed.status_code == 200
            assert any(item["name"] == payload["name"] for item in listed.json()["backups"])

            validated = client.post("/api/operations/backups/validate", json={"name": payload["name"]})
            assert validated.status_code == 200, validated.text
            assert validated.json()["valid"] is True
            assert validated.json()["restore_performed"] is False

            downloaded = client.get(f"/api/operations/backups/{payload['name']}/download")
            assert downloaded.status_code == 200
            assert downloaded.headers["content-type"].startswith("application/zip")
            assert downloaded.content[:2] == b"PK"
    finally:
        sentinel.unlink(missing_ok=True)


def test_backup_validation_rejects_path_traversal(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TERMINAL_AI_BACKUP_DIR", str(tmp_path / "backups"))
    with TestClient(app=app) as client:
        response = client.post("/api/operations/backups/validate", json={"name": "../secret.zip"})
    assert response.status_code == 400

from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from application.state_backups import BackupError, create_backup, list_backups, validate_backup


def test_create_list_and_validate_backup(tmp_path: Path):
    state = tmp_path / "state"
    (state / "sessions").mkdir(parents=True)
    (state / "memory.json").write_text('{"facts": []}', encoding="utf-8")
    (state / "sessions" / "session.json").write_text('{"messages": []}', encoding="utf-8")
    (state / "backups").mkdir()
    (state / "backups" / "nested.zip").write_text("do not include nested backups", encoding="utf-8")
    output = tmp_path / "private-backups"

    created = create_backup(state, output)
    assert created["file_count"] == 2
    assert Path(created["path"]).stat().st_mode & 0o777 == 0o600
    listed = list_backups(output)
    assert listed["count"] == 1
    assert listed["backups"][0]["name"] == created["name"]

    report = validate_backup(created["name"], state, output)
    assert report["valid"] is True
    assert report["file_count"] == 2
    assert report["existing_file_conflicts"] == 2
    assert report["restore_performed"] is False


def test_validate_backup_detects_checksum_tampering(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "fact.txt").write_text("original", encoding="utf-8")
    output = tmp_path / "backups"
    created = create_backup(state, output)
    archive_path = Path(created["path"])
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive_path) as source, zipfile.ZipFile(tampered, "w") as target:
        manifest = json.loads(source.read("manifest.json"))
        target.writestr("manifest.json", json.dumps(manifest))
        target.writestr("state/fact.txt", "tampered")
    archive_path.unlink()
    tampered.rename(archive_path)

    with pytest.raises(BackupError, match="Checksum mismatch"):
        validate_backup(created["name"], state, output)


@pytest.mark.parametrize("name", ["../outside.zip", "/tmp/backup.zip", "wrong.zip", "terminal-ai-state-../x.zip"])
def test_backup_names_cannot_escape_backup_directory(tmp_path: Path, name: str):
    with pytest.raises(BackupError):
        validate_backup(name, tmp_path / "state", tmp_path / "backups")


def test_validate_backup_rejects_non_object_manifest(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    output = tmp_path / "backups"
    output.mkdir()
    name = "terminal-ai-state-invalid.zip"
    with zipfile.ZipFile(output / name, "w") as archive:
        archive.writestr("manifest.json", json.dumps(["not", "an", "object"]))
    with pytest.raises(BackupError, match="Unsupported backup manifest"):
        validate_backup(name, state, output)


def test_backup_directory_must_not_be_inside_state(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    with pytest.raises(BackupError, match="outside the state directory"):
        create_backup(state, state / "backups")

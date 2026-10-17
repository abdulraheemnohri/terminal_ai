from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESTORE_SCRIPT = ROOT / "scripts" / "restore_state.py"


def _archive(path: Path, files: dict[str, bytes], *, extra: dict[str, bytes] | None = None):
    manifest = {
        "format": 1,
        "created_at": "test",
        "state_root_name": "state",
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, data in files.items():
            archive.writestr("state/" + name, data)
        for name, data in (extra or {}).items():
            archive.writestr(name, data)


def _run_restore(archive: Path, state: Path, *flags: str):
    env = os.environ.copy()
    env["TERMINAL_AI_STATE"] = str(state)
    return subprocess.run(
        [sys.executable, str(RESTORE_SCRIPT), str(archive), *flags],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def test_restore_requires_explicit_confirmation(tmp_path: Path):
    archive = tmp_path / "backup.zip"
    _archive(archive, {"facts.json": b'{"ok": true}'})
    result = _run_restore(archive, tmp_path / "state")
    assert result.returncode != 0
    assert "--confirm" in result.stderr


def test_restore_validates_then_restores_file(tmp_path: Path):
    archive = tmp_path / "backup.zip"
    state = tmp_path / "state"
    _archive(archive, {"nested/facts.json": b'{"ok": true}'})
    result = _run_restore(archive, state, "--confirm")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (state / "nested" / "facts.json").read_bytes() == b'{"ok": true}'


def test_restore_rejects_unlisted_archive_members_without_writing(tmp_path: Path):
    archive = tmp_path / "backup.zip"
    state = tmp_path / "state"
    _archive(archive, {"facts.json": b"safe"}, extra={"state/unlisted.txt": b"not in manifest"})
    result = _run_restore(archive, state, "--confirm")
    assert result.returncode == 2
    assert "unlisted or unexpected" in result.stdout.lower()
    assert not (state / "facts.json").exists()


def test_restore_rejects_duplicate_zip_members(tmp_path: Path):
    archive = tmp_path / "backup.zip"
    data = b"safe"
    manifest = {"format": 1, "files": {"facts.json": hashlib.sha256(data).hexdigest()}}
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("manifest.json", json.dumps(manifest))
        output.writestr("state/facts.json", data)
        output.writestr("state/facts.json", b"duplicate")
    result = _run_restore(archive, tmp_path / "state", "--confirm")
    assert result.returncode == 2
    assert "duplicate archive members" in result.stdout.lower()
    assert not (tmp_path / "state" / "facts.json").exists()


def test_restore_rejects_path_traversal_in_manifest(tmp_path: Path):
    archive = tmp_path / "backup.zip"
    outside = tmp_path / "outside.txt"
    data = b"blocked"
    manifest = {"format": 1, "files": {"../outside.txt": hashlib.sha256(data).hexdigest()}}
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("manifest.json", json.dumps(manifest))
        output.writestr("state/../outside.txt", data)
    result = _run_restore(archive, tmp_path / "state", "--confirm")
    assert result.returncode == 2
    assert "unsafe path" in result.stdout.lower()
    assert not outside.exists()


def test_restore_rejects_symlink_escape_before_writing_any_file(tmp_path: Path):
    archive = tmp_path / "backup.zip"
    state = tmp_path / "state"
    outside = tmp_path / "outside"
    state.mkdir()
    outside.mkdir()
    (state / "escape").symlink_to(outside, target_is_directory=True)
    _archive(archive, {"first.txt": b"must not be written", "escape/outside.txt": b"blocked"})
    result = _run_restore(archive, state, "--confirm")
    assert result.returncode == 2
    assert not (state / "first.txt").exists()
    assert not (outside / "outside.txt").exists()


def test_restore_rejects_path_traversal_before_checksum_validation(tmp_path: Path):
    archive = tmp_path / "backup.zip"
    manifest = {"format": 1, "files": {"../outside.txt": "not-a-valid-checksum"}}
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("manifest.json", json.dumps(manifest))
    result = _run_restore(archive, tmp_path / "state", "--confirm")
    assert result.returncode == 2
    assert "unsafe path" in result.stdout.lower()
    assert "invalid sha-256" not in result.stdout.lower()


def test_restore_rejects_windows_path_separator(tmp_path: Path):
    archive = tmp_path / "backup.zip"
    relative = r"..\\outside.txt"
    manifest = {"format": 1, "files": {relative: hashlib.sha256(b"blocked").hexdigest()}}
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("manifest.json", json.dumps(manifest))
    result = _run_restore(archive, tmp_path / "state", "--confirm")
    assert result.returncode == 2
    assert "unsafe path" in result.stdout.lower()
    assert not (tmp_path / "outside.txt").exists()


def test_restore_refuses_existing_files_without_overwrite_and_writes_nothing_else(tmp_path: Path):
    archive = tmp_path / "backup.zip"
    state = tmp_path / "state"
    state.mkdir()
    (state / "existing.txt").write_text("keep this", encoding="utf-8")
    _archive(archive, {"existing.txt": b"replace me", "new.txt": b"must not appear"})

    result = _run_restore(archive, state, "--confirm")

    assert result.returncode == 2
    assert "already exist" in result.stdout.lower()
    assert (state / "existing.txt").read_text(encoding="utf-8") == "keep this"
    assert not (state / "new.txt").exists()


def test_restore_overwrite_requires_explicit_flag_and_replaces_requested_file(tmp_path: Path):
    archive = tmp_path / "backup.zip"
    state = tmp_path / "state"
    state.mkdir()
    (state / "existing.txt").write_text("old content", encoding="utf-8")
    _archive(archive, {"existing.txt": b"new content"})

    blocked = _run_restore(archive, state, "--confirm")
    assert blocked.returncode == 2
    assert (state / "existing.txt").read_text(encoding="utf-8") == "old content"

    restored = _run_restore(archive, state, "--confirm", "--overwrite")
    assert restored.returncode == 0, restored.stdout + restored.stderr
    assert (state / "existing.txt").read_bytes() == b"new content"




def test_restore_preflights_all_destinations_before_overwriting(tmp_path: Path):
    archive = tmp_path / "backup.zip"
    state = tmp_path / "state"
    state.mkdir()
    existing = state / "existing.txt"
    existing.write_text("keep original", encoding="utf-8")
    # A later archive entry conflicts with a directory. The restore must discover
    # this before replacing the earlier, otherwise-valid existing file.
    (state / "blocked.txt").mkdir()
    _archive(archive, {"existing.txt": b"replacement", "blocked.txt": b"not a directory"})

    result = _run_restore(archive, state, "--confirm", "--overwrite")

    assert result.returncode == 2
    assert "destination is a directory" in result.stdout.lower()
    assert existing.read_text(encoding="utf-8") == "keep original"
    assert (state / "blocked.txt").is_dir()


def test_restore_rejects_empty_backup_without_writing_state(tmp_path: Path):
    archive = tmp_path / "empty.zip"
    state = tmp_path / "state"
    _archive(archive, {})
    result = _run_restore(archive, state, "--confirm")
    assert result.returncode == 2
    assert "contains no state files" in result.stdout.lower()
    assert not state.exists()

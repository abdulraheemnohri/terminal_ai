from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def run_script(name: str, state: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["TERMINAL_AI_STATE"] = str(state)
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_backup_and_restore_round_trip_without_overwrite(tmp_path: Path):
    source = tmp_path / "source-state"
    (source / "sessions").mkdir(parents=True)
    (source / "memory.json").write_text('{"facts": []}', encoding="utf-8")
    (source / "sessions" / "session.json").write_text('{"messages": []}', encoding="utf-8")
    (source / "backups").mkdir()
    (source / "backups" / "old.zip").write_text("must not nest", encoding="utf-8")
    backup_dir = tmp_path / "private-backups"

    created = run_script("backup_state.py", source, "--output-dir", str(backup_dir))
    assert created.returncode == 0, created.stderr + created.stdout
    archives = list(backup_dir.glob("terminal-ai-state-*.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert set(manifest["files"]) == {"memory.json", "sessions/session.json"}
        assert "backups/old.zip" not in archive.namelist()

    target = tmp_path / "restored-state"
    restored = run_script("restore_state.py", target, str(archives[0]), "--confirm")
    assert restored.returncode == 0, restored.stderr + restored.stdout
    assert (target / "memory.json").read_text(encoding="utf-8") == '{"facts": []}'
    assert (target / "sessions" / "session.json").is_file()

    refused = run_script("restore_state.py", target, str(archives[0]), "--confirm")
    assert refused.returncode == 2
    assert "already exist" in refused.stdout

    overwritten = run_script("restore_state.py", target, str(archives[0]), "--confirm", "--overwrite")
    assert overwritten.returncode == 0, overwritten.stderr + overwritten.stdout


def test_restore_rejects_path_traversal_and_missing_confirmation(tmp_path: Path):
    archive_path = tmp_path / "unsafe.zip"
    manifest = {"format": 1, "files": {"../escape.txt": "00"}}
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("state/../escape.txt", "bad")
    target = tmp_path / "state"
    no_confirmation = run_script("restore_state.py", target, str(archive_path))
    assert no_confirmation.returncode != 0
    blocked = run_script("restore_state.py", target, str(archive_path), "--confirm")
    assert blocked.returncode == 2
    assert "Unsafe path" in blocked.stdout
    assert not (tmp_path / "escape.txt").exists()


def test_backup_skips_symlinks(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    secret = tmp_path / "outside-secret.txt"
    secret.write_text("not for backup", encoding="utf-8")
    try:
        (source / "external-link").symlink_to(secret)
    except (OSError, NotImplementedError):
        return
    backup_dir = tmp_path / "backups"
    result = run_script("backup_state.py", source, "--output-dir", str(backup_dir))
    assert result.returncode == 0, result.stderr + result.stdout
    archive_path = next(backup_dir.glob("*.zip"))
    with zipfile.ZipFile(archive_path) as archive:
        assert "state/external-link" not in archive.namelist()

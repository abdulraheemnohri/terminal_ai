"""Local state backup inventory and checksum-only restore validation.

Restore application state from the CLI while the server is stopped. The web API
never overwrites live SQLite databases; it creates backups and validates archives.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from datetime import datetime, timezone
import zipfile
from typing import Any

MAX_FILES = 10_000
MAX_MEMBER_BYTES = 100 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024


class BackupError(ValueError):
    """An archive or backup request violates the local backup policy."""


def default_backup_dir() -> Path:
    return Path(os.environ.get("TERMINAL_AI_BACKUP_DIR", Path.home() / "terminal-ai-backups")).expanduser()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_backup_path(name: str, backup_dir: Path | None = None) -> Path:
    if not isinstance(name, str) or not name or name in {".", ".."} or Path(name).name != name:
        raise BackupError("Backup name must be a simple filename.")
    if not name.startswith("terminal-ai-state-") or not name.endswith(".zip"):
        raise BackupError("Only Terminal AI state backup ZIP files are accepted.")
    root = (backup_dir or default_backup_dir()).expanduser().resolve()
    candidate = root / name
    if candidate.is_symlink() or not candidate.is_file():
        raise BackupError("Backup file was not found.")
    if candidate.resolve().parent != root:
        raise BackupError("Backup path escapes the backup directory.")
    return candidate


def list_backups(backup_dir: Path | None = None) -> dict[str, Any]:
    root = (backup_dir or default_backup_dir()).expanduser().resolve()
    items = []
    if root.is_dir():
        for path in sorted(root.glob("terminal-ai-state-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
            if path.is_symlink() or not path.is_file():
                continue
            stat_result = path.stat()
            items.append({
                "name": path.name,
                "size_bytes": stat_result.st_size,
                "modified_at": datetime.fromtimestamp(stat_result.st_mtime, timezone.utc).isoformat(),
            })
    return {"backups": items, "backup_dir": str(root), "count": len(items)}


def create_backup(state_dir: Path, backup_dir: Path | None = None) -> dict[str, Any]:
    state = state_dir.expanduser().resolve()
    if not state.is_dir():
        raise BackupError("State directory does not exist.")
    root = (backup_dir or default_backup_dir()).expanduser().resolve()
    if root == state or state in root.parents:
        raise BackupError("Backup directory must be outside the state directory.")
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, stat.S_IRWXU)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = root / f"terminal-ai-state-{stamp}.zip"
    fd, temp_name = tempfile.mkstemp(prefix=".terminal-ai-backup-", suffix=".zip.tmp", dir=root)
    os.close(fd)
    manifest: dict[str, Any] = {"format": 1, "created_at": stamp, "state_root_name": state.name, "files": {}}
    total_bytes = 0
    try:
        with zipfile.ZipFile(temp_name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(state.rglob("*")):
                if path.is_symlink() or not path.is_file():
                    continue
                relative_parts = path.relative_to(state).parts
                if "backups" in relative_parts:
                    continue
                size = path.stat().st_size
                if size > MAX_MEMBER_BYTES:
                    raise BackupError(f"State file exceeds the 100 MiB backup limit: {'/'.join(relative_parts)}")
                total_bytes += size
                if total_bytes > MAX_TOTAL_BYTES:
                    raise BackupError("State backup exceeds the 1 GiB safety limit.")
                if len(manifest["files"]) >= MAX_FILES:
                    raise BackupError("State backup contains more than 10,000 files.")
                relative = path.relative_to(state).as_posix()
                manifest["files"][relative] = _sha256_file(path)
                archive.write(path, "state/" + relative)
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        os.chmod(temp_name, stat.S_IRUSR | stat.S_IWUSR)
        # Preserve every backup by choosing a collision-safe name even within one second.
        final = target
        suffix = 1
        while final.exists():
            final = root / f"terminal-ai-state-{stamp}-{suffix}.zip"
            suffix += 1
        os.replace(temp_name, final)
        return {
            "name": final.name,
            "path": str(final),
            "file_count": len(manifest["files"]),
            "size_bytes": final.stat().st_size,
            "created_at": stamp,
            "warning": "Backup may contain private memories, settings, or sensitive application state. Keep it in a private location.",
        }
    finally:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except OSError:
            pass


def validate_backup(name: str, state_dir: Path, backup_dir: Path | None = None) -> dict[str, Any]:
    path = _safe_backup_path(name, backup_dir)
    state = state_dir.expanduser().resolve()
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = archive.namelist()
            if names.count("manifest.json") != 1:
                raise BackupError("Backup must contain exactly one manifest.")
            manifest = json.loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict):
                raise BackupError("Unsupported backup manifest.")
            files = manifest.get("files")
            if manifest.get("format") != 1 or not isinstance(files, dict):
                raise BackupError("Unsupported backup manifest.")
            if len(files) > MAX_FILES:
                raise BackupError("Backup contains too many files.")
            seen_members = set()
            total_bytes = 0
            conflicts = 0
            for relative, expected in files.items():
                if not isinstance(relative, str) or not isinstance(expected, str):
                    raise BackupError("Manifest entries must contain path and SHA-256 strings.")
                part = PurePosixPath(relative)
                if part.is_absolute() or not part.parts or any(piece in {"", ".", ".."} for piece in part.parts) or "\\" in relative:
                    raise BackupError(f"Unsafe path in manifest: {relative!r}")
                member = "state/" + part.as_posix()
                if member in seen_members or member not in names:
                    raise BackupError(f"Missing or duplicate backup member: {relative}")
                seen_members.add(member)
                info = archive.getinfo(member)
                if info.file_size > MAX_MEMBER_BYTES:
                    raise BackupError(f"Backup member is too large: {relative}")
                total_bytes += info.file_size
                if total_bytes > MAX_TOTAL_BYTES:
                    raise BackupError("Backup exceeds the 1 GiB restore safety limit.")
                data = archive.read(member)
                if _sha256_bytes(data) != expected:
                    raise BackupError(f"Checksum mismatch: {relative}")
                destination = state / part.as_posix()
                if destination.exists():
                    conflicts += 1
            unexpected = set(names) - seen_members - {"manifest.json"}
            if unexpected:
                raise BackupError("Backup contains unlisted or unexpected archive members.")
    except BackupError:
        raise
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise BackupError(f"Unable to validate backup: {exc}") from exc
    return {
        "name": path.name,
        "valid": True,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "existing_file_conflicts": conflicts,
        "restore_performed": False,
        "notice": "Validation only. To restore, stop Terminal AI first and run scripts/restore_state.py with explicit --confirm; use --overwrite only after creating a fresh backup.",
    }

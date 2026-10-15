"""Restore a validated state backup without overwriting files by default."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

STATE = Path(os.environ.get("TERMINAL_AI_STATE", Path.home() / ".terminal_ai")).expanduser()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--confirm", action="store_true", help="Confirm that state files may be restored")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing files (make a backup first)")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("Restoration is disabled without --confirm.")
    try:
        with zipfile.ZipFile(args.archive.expanduser(), "r") as archive:
            names = archive.namelist()
            if "manifest.json" not in names:
                raise ValueError("Backup has no manifest.")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("format") != 1 or not isinstance(manifest.get("files"), dict):
                raise ValueError("Unsupported backup manifest.")
            entries: list[tuple[str, bytes]] = []
            for relative, expected in manifest["files"].items():
                part = PurePosixPath(relative)
                if part.is_absolute() or not part.parts or any(p in ("", ".", "..") for p in part.parts) or "\\\\" in relative:
                    raise ValueError(f"Unsafe path in manifest: {relative!r}")
                member = "state/" + part.as_posix()
                if member not in names:
                    raise ValueError(f"Missing backup member: {relative}")
                data = archive.read(member)
                if sha256(data) != expected:
                    raise ValueError(f"Checksum mismatch: {relative}")
                entries.append((part.as_posix(), data))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Restore blocked: {exc}")
        return 2
    existing = [relative for relative, _ in entries if (STATE / relative).exists()]
    if existing and not args.overwrite:
        print(f"Restore blocked: {len(existing)} destination file(s) already exist. Use --overwrite only after making a backup.")
        return 2
    STATE.mkdir(parents=True, exist_ok=True)
    resolved_root = STATE.resolve()
    for relative, data in entries:
        target = STATE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if resolved_root not in target.resolve().parents:
            print(f"Restore blocked: destination escapes state directory: {relative}")
            return 2
        fd, temporary = tempfile.mkstemp(prefix=".restore-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print(f"Restored {len(entries)} file(s) to {STATE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

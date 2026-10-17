""""Restore a validated state backup without overwriting files by default."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile

STATE = Path(os.environ.get("TERMINAL_AI_STATE", Path.home() / ".terminal_ai")).expanduser()
MAX_FILES = 10_000
MAX_MEMBER_BYTES = 100 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 5 * 1024 * 1024
MAX_ARCHIVE_BYTES = MAX_TOTAL_BYTES + 20 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validated_entries(archive_path: Path) -> list[tuple[str, bytes]]:
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Backup archive exceeds the compressed-size safety limit.")
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("Backup contains duplicate archive members.")
        if names.count("manifest.json") != 1:
            raise ValueError("Backup must contain exactly one manifest.")
        if archive.getinfo("manifest.json").file_size > MAX_MANIFEST_BYTES:
            raise ValueError("Backup manifest exceeds the 5 MiB safety limit.")
        manifest = json.loads(archive.read("manifest.json"))
        if not isinstance(manifest, dict):
            raise ValueError("Unsupported backup manifest.")
        files = manifest.get("files")
        if manifest.get("format") != 1 or not isinstance(files, dict):
            raise ValueError("Unsupported backup manifest.")
        if len(files) > MAX_FILES:
            raise ValueError("Backup contains too many files.")

        entries: list[tuple[str, bytes]] = []
        expected_members = {"manifest.json"}
        total_bytes = 0
        for relative, expected in files.items():
            if not isinstance(relative, str) or not isinstance(expected, str):
                raise ValueError("Manifest entries must contain path and SHA-256 strings.")
            # Validate the path before checksum details so malformed/traversal paths
            # are consistently rejected as unsafe, even if their checksum is invalid.
            if not relative or "\\\\" in relative or ":" in relative:
                raise ValueError(f"Unsafe path in manifest: {relative!r}")
            raw_parts = relative.split("/")
            part = PurePosixPath(relative)
            if (
                part.is_absolute()
                or not part.parts
                or any(piece in {"", ".", ".."} for piece in raw_parts)
                or any(piece in {"", ".", ".."} for piece in part.parts)
            ):
                raise ValueError(f"Unsafe path in manifest: {relative!r}")
            if not SHA256_RE.fullmatch(expected):
                raise ValueError(f"Invalid SHA-256 value for {relative!r}.")
            member = "state/" + part.as_posix()
            if member not in names:
                raise ValueError(f"Missing backup member: {relative}")
            info = archive.getinfo(member)
            if info.is_dir():
                raise ValueError(f"Backup member is not a file: {relative}")
            if info.file_size > MAX_MEMBER_BYTES:
                raise ValueError(f"Backup member is too large: {relative}")
            total_bytes += info.file_size
            if total_bytes > MAX_TOTAL_BYTES:
                raise ValueError("Backup exceeds the 1 GiB restore safety limit.")
            data = archive.read(member)
            if sha256(data) != expected:
                raise ValueError(f"Checksum mismatch: {relative}")
            expected_members.add(member)
            entries.append((part.as_posix(), data))

        if set(names) != expected_members:
            raise ValueError("Backup contains unlisted or unexpected archive members.")
        return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--confirm", action="store_true", help="Confirm that state files may be restored")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing files (make a backup first)")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("Restoration is disabled without --confirm.")

    try:
        entries = _validated_entries(args.archive.expanduser())
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Restore blocked: {exc}")
        return 2

    if not entries:
        print("Restore blocked: backup contains no state files.")
        return 2

    try:
        STATE.mkdir(parents=True, exist_ok=True)
        resolved_root = STATE.resolve()
        destinations: list[tuple[str, bytes, Path]] = []
        for relative, data in entries:
            target = STATE / relative
            resolved_target = target.resolve()
            if resolved_root not in resolved_target.parents:
                print(f"Restore blocked: destination escapes state directory: {relative}")
                return 2
            if target.is_dir():
                print(f"Restore blocked: destination is a directory: {relative}")
                return 2
            destinations.append((relative, data, target))

        existing = [relative for relative, _, target in destinations if target.exists()]
        if existing and not args.overwrite:
            print(f"Restore blocked: {len(existing)} destination file(s) already exist. Use --overwrite only after making a backup.")
            return 2

        # Validate every destination before the first write so a later path failure
        # cannot leave an otherwise valid restore only partially applied.
        for relative, data, target in destinations:
            target.parent.mkdir(parents=True, exist_ok=True)
            resolved_parent = target.parent.resolve()
            if resolved_parent != resolved_root and resolved_root not in resolved_parent.parents:
                print(f"Restore blocked: destination escapes state directory: {relative}")
                return 2

        for relative, data, target in destinations:
            fd, temporary = tempfile.mkstemp(prefix=".restore-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
    except OSError as exc:
        print(f"Restore blocked: {exc}")
        return 2

    print(f"Restored {len(entries)} file(s) to {STATE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

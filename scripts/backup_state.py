"""Create a permission-restricted ZIP backup of Terminal AI's state directory."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import zipfile
from datetime import datetime, timezone

STATE = Path(os.environ.get("TERMINAL_AI_STATE", Path.home() / ".terminal_ai")).expanduser()
DEFAULT_OUTPUT = Path.home() / "terminal-ai-backups"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not STATE.is_dir():
        parser.error(f"State directory does not exist: {STATE}")
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.chmod(output, stat.S_IRWXU)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = output / f"terminal-ai-state-{stamp}.zip"
    manifest = {"format": 1, "created_at": stamp, "state_root_name": STATE.name, "files": {}}
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(STATE.rglob("*")):
            if path.is_symlink() or not path.is_file() or "backups" in path.relative_to(STATE).parts:
                continue
            relative = path.relative_to(STATE).as_posix()
            manifest["files"][relative] = digest(path)
            archive.write(path, "state/" + relative)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
    print(f"Backup created: {target}")
    print(f"Files included: {len(manifest['files'])}")
    print("Treat this archive as sensitive: application state may contain credentials or private data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

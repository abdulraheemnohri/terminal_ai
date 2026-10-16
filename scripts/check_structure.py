"""Validate the repository's expected source layout without touching runtime state."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "app.py",
    "terminal_ai.py",
    "requirements.txt",
    "command_control.py",
    "api_schemas.py",
    "application/task_intelligence.py",
    "application/autonomy.py",
    "application/learning.py",
    "application/skill_evolution.py",
    "application/task_lifecycle.py",
    "application/recovery_proposals.py",
    "application/browser_runtime.py",
    "application/browser_dispatch.py",
    "scripts/execute_approved_browser_operation.py",
    "scripts/doctor.py",
    "scripts/backup_state.py",
    "scripts/restore_state.py",
    "scripts/validate.sh",
    "scripts/validate.ps1",
    "scripts/README.md",
    "web/index.html",
    "web/app.js",
    "web/app.css",
    "tests/test_autonomy.py",
)
REQUIRED_DIRS = ("agent", "application", "routers", "tests", "docs", "scripts")


def main() -> int:
    missing = [
        *(f"file: {name}" for name in REQUIRED_FILES if not (ROOT / name).is_file()),
        *(f"directory: {name}" for name in REQUIRED_DIRS if not (ROOT / name).is_dir()),
    ]
    # Keep a forwarding entrypoint in scripts/ for every legacy root-level shell
    # or PowerShell script, while preserving the original commands for compatibility.
    legacy_scripts = [
        path.name for path in ROOT.iterdir()
        if path.is_file() and path.suffix.lower() in {".sh", ".ps1"}
    ]
    for name in legacy_scripts:
        root_entry = ROOT / name
        canonical = ROOT / "scripts" / name
        if not canonical.is_file():
            missing.append(f"scripts catalog entrypoint: scripts/{name}")
            continue
        wrapper_text = root_entry.read_text(encoding="utf-8", errors="replace")
        canonical_text = canonical.read_text(encoding="utf-8", errors="replace")
        target = f"scripts\\{name}" if name.lower().endswith(".ps1") else f"scripts/{name}"
        if "Backwards-compatible wrapper" not in wrapper_text or target not in wrapper_text:
            missing.append(f"root compatibility wrapper: {name}")
        if "Compatibility forwarding entrypoint" in canonical_text:
            missing.append(f"canonical implementation is still a wrapper: scripts/{name}")
    if missing:
        print("Project structure check failed:")
        for item in missing:
            print(f"  - missing {item}")
        return 1
    print(f"Project structure OK: {len(REQUIRED_FILES)} required files, {len(REQUIRED_DIRS)} required directories, and {len(legacy_scripts)} compatibility wrappers with canonical script implementations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

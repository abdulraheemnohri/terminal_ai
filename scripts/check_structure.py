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
)
REQUIRED_DIRS = ("agent", "application", "routers", "tests", "docs", "scripts")


def main() -> int:
    missing = [
        *(f"file: {name}" for name in REQUIRED_FILES if not (ROOT / name).is_file()),
        *(f"directory: {name}" for name in REQUIRED_DIRS if not (ROOT / name).is_dir()),
    ]
    if missing:
        print("Project structure check failed:")
        for item in missing:
            print(f"  - missing {item}")
        return 1
    print(f"Project structure OK: {len(REQUIRED_FILES)} required files and {len(REQUIRED_DIRS)} required directories present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

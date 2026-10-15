from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_structure_check_passes_from_repository_root():
    result = subprocess.run(
        [sys.executable, "scripts/check_structure.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Project structure OK" in result.stdout


def test_modular_boundaries_are_present():
    for relative in ("agent/__init__.py", "routers/__init__.py", "docs/ARCHITECTURE.md"):
        assert (ROOT / relative).is_file(), f"Expected modular boundary: {relative}"

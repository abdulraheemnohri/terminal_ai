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



def test_root_operational_scripts_are_compatibility_wrappers():
    for root_script in ROOT.iterdir():
        if not root_script.is_file() or root_script.suffix.lower() not in {".sh", ".ps1"}:
            continue
        canonical = ROOT / "scripts" / root_script.name
        assert canonical.is_file(), f"Missing canonical script: {canonical}"
        wrapper = root_script.read_text(encoding="utf-8")
        implementation = canonical.read_text(encoding="utf-8")
        assert "Backwards-compatible wrapper" in wrapper, root_script.name
        target = f"scripts\\{root_script.name}" if root_script.suffix.lower() == ".ps1" else f"scripts/{root_script.name}"
        assert target in wrapper, root_script.name
        assert "Compatibility forwarding entrypoint" not in implementation, canonical.name

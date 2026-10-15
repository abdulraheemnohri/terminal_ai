"""Run safe, read-only installation and runtime checks for Terminal AI."""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get("TERMINAL_AI_STATE", Path.home() / ".terminal_ai")).expanduser()
REQUIRED = ("litestar", "pydantic", "httpx")
OPTIONAL = ("google.genai", "litert_lm_api", "huggingface_hub", "playwright")


def check(label: str, ok: bool, detail: str, *, warning: bool = False) -> bool:
    marker = "WARN" if warning and not ok else "PASS" if ok else "FAIL"
    print(f"[{marker}] {label}: {detail}")
    return ok or warning


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="Skip compile and script syntax checks")
    args = parser.parse_args()
    failures = 0
    failures += not check("Python", sys.version_info >= (3, 10), sys.version.split()[0] + " (requires >=3.10)")
    failures += not check("Repository", (ROOT / "app.py").is_file() and (ROOT / "requirements.txt").is_file(), str(ROOT))
    for module in REQUIRED:
        ok = importlib.util.find_spec(module) is not None
        failures += not check("Dependency " + module, ok, "available" if ok else "not installed in this interpreter")
    for module in OPTIONAL:
        try:
            available = importlib.util.find_spec(module) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            available = False
        check("Optional " + module, available, "available" if available else "not installed (feature may be unavailable)", warning=True)
    failures += not check("State directory", STATE.exists() and STATE.is_dir(), str(STATE) if STATE.exists() else f"not created yet: {STATE}", warning=not STATE.exists())
    check("Git", shutil.which("git") is not None, shutil.which("git") or "not installed", warning=True)
    if not args.quick:
        result = subprocess.run([sys.executable, "-m", "compileall", "-q", "app.py", "terminal_ai.py", "agent", "application", "routers"], cwd=ROOT, check=False)
        failures += not check("Python compilation", result.returncode == 0, "compileall completed" if result.returncode == 0 else f"exit {result.returncode}")
        shell = shutil.which("sh")
        if shell:
            scripts = sorted((ROOT / "scripts").glob("*.sh"))
            for script in scripts:
                result = subprocess.run([shell, "-n", str(script)], cwd=ROOT, check=False)
                failures += not check("Shell syntax " + script.name, result.returncode == 0, "valid" if result.returncode == 0 else f"exit {result.returncode}")
    print(f"\nDoctor finished: {failures} required check(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Test configuration — isolate terminal-ai state before importing the module.

terminal_ai computes STATE_DIR at import time from $TERMINAL_AI_STATE, so the
env var must be set here (conftest runs before test modules import terminal_ai).
"""
import os
import sys
import tempfile
from pathlib import Path

# make repo root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# isolated state + models dirs BEFORE terminal_ai is imported anywhere
_STATE = tempfile.mkdtemp(prefix="tai-state-")
_MODELS = tempfile.mkdtemp(prefix="tai-models-")
os.environ["TERMINAL_AI_STATE"] = _STATE
os.environ["TERMINAL_AI_MODELS"] = _MODELS
os.environ["NO_COLOR"] = "1"
os.environ.pop("TERMINAL_AI_DEBUG", None)
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GOOGLE_API_KEY", None)

"""Pytest configuration — must run before terminal_ai is imported.

Redirects all agent state (memory, graph, settings, sessions…) into a
throwaway temp dir so tests never touch the developer's real ~/.terminal_ai.
"""
import os
import sys
import tempfile
from pathlib import Path

_TEST_STATE = tempfile.mkdtemp(prefix="terminal_ai_test_state_")
os.environ["TERMINAL_AI_STATE"] = _TEST_STATE
os.environ["NO_COLOR"] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

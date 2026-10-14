#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  TERMINAL-AI Â· ONE FILE Â· HYBRID SELF-EVOLVING AGENT Â· v4.0.0
--------------------------------------------------------------------------------
  ð§­ Task Router            auto-selects best model per task
  ð¥ Auto Downloader        fetches local models from HF on demand
  ð Hybrid Mode            cloud + local work together, auto-fallback
  ð Model Registry         all 2026 Gemini + local models
  ð©º Self-Diagnosis         agent checks its own health
  ð¾ Auto-Backup            memory snapshots before risky ops
  ð Pattern Learner        learns your task patterns
  âï¸  Gemini (all models)   3.8/3.7/3.5 Flash, 3.1 Pro, 3 Pro
  â¡ LiteRT-LM (local 0.6B) Qwen3
  ð§  Memory + Graph         persistent facts, entities, relations
  ð¯ Goals + Journal        multi-step planning, self-reflection
  ð  Skills + Forge         learned procedures, self-written tools
  ð¤ Dreamer                offline memory consolidation
  ð Observer               auto-extracts learnings
  ðª Self-Critique          critique + refine pass
  ð¡ Proactive Advisor      suggests next steps
  âï¸  Settings Manager       persistent settings.json (/set, /settings)
  🔐 Env Manager            .env file support (/env, /env-set, /env-save)
  🖥 System Tools          sys_info · now · find_files · read_lines · env
  ð Usage Stats            per-backend turns/chars/time (/usage)
  ð¾ Sessions               save/load conversations (--resume)
  ð  File Tools            list/edit/append/delete/copy/grep + web_search

  MODES
      auto      Task Router picks best model per prompt (DEFAULT)
      cloud     Force Gemini only
      local     Force LiteRT-LM only
      hybrid    Try cloud, fallback to local on failure

  INSTALL
      pip install google-genai litert-lm huggingface_hub

  WEB APP
      litestar --app app:app run --host 127.0.0.1 --port 8000
      open http://127.0.0.1:8000 in a browser

  This module is the internal agent engine. The terminal REPL is no longer
  the supported interface; use app.py for the Litestar web application.
================================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

try:
    import readline  # noqa: F401
except Exception:
    pass

if os.name == "nt":
    os.system("")

__version__ = "4.2.0"
STATE_DIR = Path(os.environ.get("TERMINAL_AI_STATE", Path.home() / ".terminal_ai"))
STATE_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR = STATE_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_FILE = STATE_DIR / "memory.json"
GRAPH_FILE = STATE_DIR / "graph.json"
GOALS_FILE = STATE_DIR / "goals.json"
JOURNAL_FILE = STATE_DIR / "journal.md"
SKILLS_FILE = STATE_DIR / "skills.json"
META_FILE = STATE_DIR / "meta.json"
TOOLS_FILE = STATE_DIR / "tools.json"
PATTERNS_FILE = STATE_DIR / "patterns.json"
HF_TOKEN_FILE = STATE_DIR / "hf_token"
SETTINGS_FILE = STATE_DIR / "settings.json"
STATS_FILE = STATE_DIR / "stats.json"
SESSIONS_DIR = STATE_DIR / "sessions"
MODELS_DIR = Path(os.environ.get("TERMINAL_AI_MODELS", Path.home() / "terminal-ai" / "models"))
MODELS_DIR.mkdir(parents=True, exist_ok=True)


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  TERMINAL  ââ
class C:
    RESET = "\033[0m";  BOLD = "\033[1m";  DIM = "\033[2m";  ITAL = "\033[3m"
    RED = "\033[31m";   GREEN = "\033[32m"; YELLOW = "\033[33m"; BLUE = "\033[34m"
    MAGENTA = "\033[35m"; CYAN = "\033[36m"; WHITE = "\033[37m"
    GREY = "\033[90m";  BRED = "\033[91m"; BGREEN = "\033[92m"
    BYELLOW = "\033[93m"; BCYAN = "\033[96m"


# Module-level aliases (fixes NameError in f-strings)
RESET = C.RESET;    BOLD = C.BOLD;     DIM = C.DIM;     ITAL = C.ITAL
RED = C.RED;        GREEN = C.GREEN;   YELLOW = C.YELLOW; BLUE = C.BLUE
MAGENTA = C.MAGENTA; CYAN = C.CYAN;    WHITE = C.WHITE
GREY = C.GREY;      BRED = C.BRED;     BGREEN = C.BGREEN; BYELLOW = C.BYELLOW
BCYAN = C.BCYAN


COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def paint(s: str, *codes: str) -> str:
    return ("".join(codes) + s + C.RESET) if COLOR else s


def info(msg: str) -> None:
    print(paint(msg, C.GREY))


def err(msg: str) -> None:
    print(paint("  â ", C.BRED) + paint(msg, C.RED), file=sys.stderr)


def ok(msg: str) -> None:
    print(paint("  â ", C.BGREEN) + paint(msg, C.GREEN))


def warn(msg: str) -> None:
    print(paint("  â  ", C.BYELLOW) + paint(msg, C.YELLOW))


def dbg(tag: str, msg: str) -> None:
    if os.environ.get("TERMINAL_AI_DEBUG"):
        print(paint(f"  [{tag}] ", C.DIM) + paint(msg, C.GREY), file=sys.stderr)


class Spinner:
    FRAMES = "â â â ¹â ¸â ¼â ´â ¦â §â â "

    def __init__(self, label: str = "thinking"):
        self.label, self._stop, self._t = label, True, None

    def start(self) -> None:
        if not COLOR:
            return
        self._stop = False
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self) -> None:
        i = 0
        while not self._stop:
            sys.stdout.write(f"\r{paint(self.FRAMES[i % len(self.FRAMES)], C.BCYAN)} "
                             f"{paint(self.label + 'â¦', C.DIM)} ")
            sys.stdout.flush()
            i += 1
            time.sleep(0.08)

    def stop(self) -> None:
        if self._stop:
            return
        self._stop = True
        if self._t:
            self._t.join(timeout=0.2)
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  MODEL  ââââ
@dataclass
class Msg:
    role: str
    text: str
    meta: dict = field(default_factory=dict)


class BackendError(RuntimeError):
    pass


class Backend:
    label = "backend"
    supports_tools = False

    def stream(self, system: str, history: list[Msg],
               tools: Optional[list[dict]] = None) -> Iterator[str]:
        raise NotImplementedError

    def cancel(self) -> None:
        pass

    def close(self) -> None:
        pass


def _import_first(*names: str):
    for n in names:
        try:
            return importlib.import_module(n)
        except Exception:
            continue
    return None


def _find(obj: Any, *names: str):
    for n in names:
        v = getattr(obj, n, None)
        if v is not None:
            return v
    return None


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  MODEL REGISTRY  ââ
@dataclass
class ModelInfo:
    name: str              # API model ID
    display: str           # human-readable
    kind: str              # "cloud" | "local"
    tier: str              # "pro" | "flash" | "lite" | "local"
    strengths: list[str] = field(default_factory=list)
    hf_repo: str = ""      # for local models
    hf_file: str = ""
    size: str = ""         # e.g., "1B", "4B"


class ModelRegistry:
    """Registry of all known models (cloud + local) with metadata."""

    CLOUD_MODELS = [
        ModelInfo("gemini-3.8-flash", "Gemini 3.8 Flash", "cloud", "flash",
                  ["fast", "cheap", "general", "agentic", "coding"]),
        ModelInfo("gemini-3.7-flash", "Gemini 3.7 Flash", "cloud", "flash",
                  ["fast", "agentic", "reasoning"]),
        ModelInfo("gemini-3.5-flash", "Gemini 3.5 Flash", "cloud", "flash",
                  ["balanced", "creative", "multimodal"]),
        ModelInfo("gemini-3.1-pro", "Gemini 3.1 Pro", "cloud", "pro",
                  ["powerful", "complex-reasoning", "coding", "long-context"]),
        ModelInfo("gemini-3-pro", "Gemini 3 Pro", "cloud", "pro",
                  ["reasoning", "research", "analysis"]),
    ]

    LOCAL_MODELS = [
        ModelInfo("qwen3-0.6b", "Qwen3 0.6B LiteRT-LM", "local", "local",
                  ["private", "offline", "multilingual", "small", "chat"],
                  hf_repo="litert-community/Qwen3-0.6B",
                  hf_file="Qwen3-0.6B.litertlm", size="0.6B"),
    ]

    def __init__(self):
        self.cloud = {m.name: m for m in self.CLOUD_MODELS}
        self.local = {m.name: m for m in self.LOCAL_MODELS}

    def all_models(self) -> list[ModelInfo]:
        return list(self.cloud.values()) + list(self.local.values())

    def get(self, name: str) -> Optional[ModelInfo]:
        return self.cloud.get(name) or self.local.get(name)

    def best_for(self, task_type: str, prefer_local: bool = False) -> Optional[ModelInfo]:
        """Pick the best model for a task type."""
        if prefer_local:
            for m in self.local.values():
                return m
        routing = {
            "simple_chat": "gemini-3.8-flash",
            "coding": "gemini-3.1-pro",
            "complex_reasoning": "gemini-3.1-pro",
            "research": "gemini-3.8-flash",
            "creative": "gemini-3.5-flash",
            "math": "gemini-3-pro",
            "privacy": None,  # will use local
            "fast": "gemini-3.8-flash",
        }
        model_name = routing.get(task_type)
        if model_name:
            return self.cloud.get(model_name)
        # fallback to first available cloud model
        return next(iter(self.cloud.values()), None)


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  TASK ROUTER  ââââ
class TaskRouter:
    """Classifies user prompts and routes them to the best model."""

    TASK_PATTERNS = {
        "coding": [
            r"\b(code|python|function|class|debug|fix|bug|error|compile|run|script|"
            r"program|implement|algorithm|api|sql|javascript|java|cpp|rust)\b",
            r"```", r"def\s+\w+", r"class\s+\w+",
        ],
        "complex_reasoning": [
            r"\b(analyze|prove|derive|theorem|philosophy|ethics|compare|evaluate|"
            r"critique|argument|logic|paradox|hypothesis)\b",
        ],
        "research": [
            r"\b(research|investigate|study|survey|find|search|latest|current|"
            r"news|paper|citation|source|verify|fact-check)\b",
        ],
        "creative": [
            r"\b(write|story|poem|song|lyrics|creative|fiction|novel|script|"
            r"brainstorm|imagine|invent|design|art)\b",
        ],
        "math": [
            r"\b(calculate|solve|equation|integral|derivative|matrix|probability|"
            r"statistics|geometry|algebra|calculus|\d+\s*[\+\-\*\/]\s*\d+)\b",
        ],
        "privacy": [
            r"\b(private|secret|confidential|sensitive|personal|password|"
            r"don'?t (send|share|upload)|offline|local only)\b",
        ],
    }

    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self._pattern_cache = {
            task: [re.compile(p, re.I) for p in pats]
            for task, pats in self.TASK_PATTERNS.items()
        }

    def classify(self, prompt: str) -> str:
        """Classify a prompt into a task type."""
        scores: dict[str, int] = {}
        for task, patterns in self._pattern_cache.items():
            score = sum(1 for p in patterns if p.search(prompt))
            if score > 0:
                scores[task] = score

        if not scores:
            return "simple_chat"

        # privacy overrides everything
        if scores.get("privacy", 0) > 0:
            return "privacy"

        return max(scores, key=scores.get)

    def select_backend(self, prompt: str, prefer_local: bool = False,
                       local_available: bool = False) -> tuple[str, str]:
        """Returns (backend_type, model_name). backend_type: 'cloud'|'local'."""
        task = self.classify(prompt)

        # privacy or prefer_local â local
        if task == "privacy" or prefer_local:
            if local_available:
                return "local", "qwen3-0.6b"
            # fallback to cloud if no local available
            if task == "privacy":
                warn("Privacy requested but no local model. Using cloud.")

        # route to best cloud model
        model = self.registry.best_for(task, prefer_local=False)
        if model:
            return "cloud", model.name
        return "cloud", "gemini-3.8-flash"

    def describe(self, prompt: str) -> str:
        task = self.classify(prompt)
        backend, model = self.select_backend(prompt)
        return f"task={task} â {backend}/{model}"


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  AUTO DOWNLOADER  ââ
class AutoDownloader:
    """Automatically downloads local models from Hugging Face if missing."""

    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self._token = os.environ.get("HF_TOKEN") or self._load_token()

    def _load_token(self) -> Optional[str]:
        if HF_TOKEN_FILE.exists():
            try:
                return HF_TOKEN_FILE.read_text(encoding="utf-8").strip()
            except Exception:
                return None
        return None

    def find_local_model(self, model_name: str = "qwen3-0.6b") -> Optional[Path]:
        """Find an already-downloaded local model."""
        for d in (MODELS_DIR, Path("models"), Path.cwd(), Path.home() / "models"):
            for pat in ("*.litertlm", "*.task", "*.litert", "*.bin"):
                for f in d.glob(pat):
                    normalized_model = model_name.lower().replace("-", "").replace("_", "")
                    normalized_file = f.name.lower().replace("-", "").replace("_", "")
                    if normalized_model in normalized_file:
                        return f
        return None

    def ensure_model(self, model_name: str = "qwen3-0.6b",
                     force: bool = False) -> Optional[Path]:
        """Ensure a local model exists. Download if missing. Returns path."""
        # Check if already downloaded
        existing = self.find_local_model(model_name)
        if existing and not force:
            info(f"  â local model found: {existing.name}")
            return existing

        # Get model info from registry
        model_info = self.registry.local.get(model_name)
        if not model_info or not model_info.hf_repo:
            # Try to find any local model
            existing = self.find_local_model()
            if existing:
                return existing
            return None

        # Download from HF
        return self._download(model_info)

    def _download(self, model_info: ModelInfo) -> Optional[Path]:
        try:
            from huggingface_hub import hf_hub_download
        except ImportError:
            err("huggingface_hub not installed. Run: pip install huggingface_hub")
            return None

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        info(f"  ð¥ downloading {model_info.hf_repo}/{model_info.hf_file}â¦")
        spinner = Spinner("downloading")
        spinner.start()

        try:
            local_path = hf_hub_download(
                repo_id=model_info.hf_repo,
                filename=model_info.hf_file,
                token=self._token,
                local_dir=str(MODELS_DIR),
                local_dir_use_symlinks=False,
            )
            spinner.stop()
            ok(f"saved to {local_path}")
            return Path(local_path)
        except Exception as e:
            spinner.stop()
            if "gated" in str(e).lower() or "403" in str(e):
                err(f"Model is gated. Accept license at https://huggingface.co/{model_info.hf_repo}")
                err("Then set: export HF_TOKEN='hf_...'")
            else:
                err(f"download failed: {e}")
            return None

    def list_local_models(self) -> list[Path]:
        """List all local model files found."""
        found = []
        for d in (MODELS_DIR, Path("models"), Path.home() / "models"):
            for pat in ("*.litertlm", "*.task", "*.litert", "*.bin"):
                found.extend(d.glob(pat))
        return sorted(set(found))


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  HUGGING FACE  ââ
class HFManager:
    """Hugging Face Hub integration: login, download, list models."""

    POPULAR_MODELS = {
        "qwen3-0.6b": ("litert-community/Qwen3-0.6B", "Qwen3-0.6B.litertlm"),
        "phi-3-mini": ("microsoft/phi-3-mini-4k-instruct", "model.bin"),
    }

    def __init__(self):
        self._token = os.environ.get("HF_TOKEN") or self._load_token()

    def _load_token(self) -> Optional[str]:
        if HF_TOKEN_FILE.exists():
            try:
                return HF_TOKEN_FILE.read_text(encoding="utf-8").strip()
            except Exception:
                return None
        return None

    def _save_token(self, token: str) -> None:
        HF_TOKEN_FILE.write_text(token, encoding="utf-8")
        HF_TOKEN_FILE.chmod(0o600)
        self._token = token

    def login(self, token: str) -> bool:
        try:
            from huggingface_hub import whoami
            info_ = whoami(token=token)
            self._save_token(token)          # only persist after validation
            ok(f"logged in as {info_.get('name', 'unknown')}")
            return True
        except ImportError:
            # no SDK to validate: save but warn
            self._save_token(token)
            warn("huggingface_hub not installed; token saved but not validated")
            return True
        except Exception as e:
            err(f"token invalid: {e}")
            return False

    def logout(self) -> None:
        if HF_TOKEN_FILE.exists():
            HF_TOKEN_FILE.unlink()
        self._token = None
        ok("logged out from Hugging Face")

    def is_logged_in(self) -> bool:
        return bool(self._token)

    def download(self, repo_id: str, filename: str,
                 dest_dir: Optional[Path] = None) -> Path:
        try:
            from huggingface_hub import hf_hub_download
        except ImportError:
            raise BackendError("huggingface_hub not installed.\n"
                               "      pip install huggingface_hub")

        dest_dir = dest_dir or MODELS_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)

        info(f"  ð¥ downloading {repo_id}/{filename}â¦")
        spinner = Spinner("downloading")
        spinner.start()

        try:
            local_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                token=self._token,
                local_dir=str(dest_dir),
                local_dir_use_symlinks=False,
            )
            spinner.stop()
            ok(f"saved to {local_path}")
            return Path(local_path)
        except Exception as e:
            spinner.stop()
            if "gated" in str(e).lower() or "403" in str(e):
                raise BackendError(
                    f"model is gated. You need:\n"
                    f"      1. Accept license at https://huggingface.co/{repo_id}\n"
                    f"      2. Set HF_TOKEN: export HF_TOKEN='hf_...'\n"
                    f"      3. Or run /hf-login <token>")
            raise BackendError(f"download failed: {e}")

    def list_popular(self) -> list[tuple[str, str, str]]:
        return [(k, v[0], v[1]) for k, v in self.POPULAR_MODELS.items()]


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  PATTERN LEARNER  ââ
@dataclass
class PatternLearner:
    """Learns user's task patterns to improve routing over time."""
    task_counts: dict[str, int] = field(default_factory=dict)
    model_preferences: dict[str, dict[str, int]] = field(default_factory=dict)
    avg_prompt_length: float = 20.0
    total_prompts: int = 0

    @classmethod
    def load(cls, path: Path = PATTERNS_FILE) -> "PatternLearner":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()

    def save(self, path: Path = PATTERNS_FILE) -> None:
        try:
            path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except Exception:
            pass

    def record(self, task_type: str, model_name: str, prompt_length: int) -> None:
        self.task_counts[task_type] = self.task_counts.get(task_type, 0) + 1
        if task_type not in self.model_preferences:
            self.model_preferences[task_type] = {}
        self.model_preferences[task_type][model_name] = \
            self.model_preferences[task_type].get(model_name, 0) + 1
        self.total_prompts += 1
        self.avg_prompt_length = (
            (self.avg_prompt_length * (self.total_prompts - 1) + prompt_length)
            / self.total_prompts
        )
        self.save()

    def preferred_model(self, task_type: str) -> Optional[str]:
        """Get the most-used model for a task type."""
        prefs = self.model_preferences.get(task_type, {})
        if not prefs:
            return None
        return max(prefs, key=prefs.get)

    def most_common_task(self) -> Optional[str]:
        if not self.task_counts:
            return None
        return max(self.task_counts, key=self.task_counts.get)

    def summary(self) -> str:
        if not self.task_counts:
            return "(no patterns learned yet)"
        lines = [f"Total prompts: {self.total_prompts}",
                 f"Avg prompt length: {self.avg_prompt_length:.0f} words"]
        for task, count in sorted(self.task_counts.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"  {task}: {count}x")
        return "\n".join(lines)


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  SELF DIAGNOSTIC  ââ
class SelfDiagnostic:
    """Agent checks its own health: backends, memory, tools, models."""

    def __init__(self, registry: ModelRegistry, downloader: AutoDownloader):
        self.registry = registry
        self.downloader = downloader

    def run(self) -> dict:
        report = {
            "cloud": self._check_cloud(),
            "local": self._check_local(),
            "memory": self._check_memory(),
            "disk": self._check_disk(),
        }
        return report

    def _check_cloud(self) -> dict:
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        result = {"available": bool(key), "models": []}
        if key:
            try:
                from google import genai
                client = genai.Client(api_key=key)
                # Try listing models
                try:
                    models = client.models.list()
                    for m in models:
                        if "flash" in m.name.lower() or "pro" in m.name.lower():
                            result["models"].append(m.name)
                    result["available"] = True
                except Exception:
                    result["available"] = True  # key exists but can't list
            except ImportError:
                result["available"] = False
                result["error"] = "google-genai not installed"
            except Exception as e:
                result["available"] = False
                result["error"] = str(e)
        return result

    def _check_local(self) -> dict:
        models = self.downloader.list_local_models()
        litert_ok = _import_first("litert_lm", "litertlm") is not None
        return {
            "available": bool(models) and litert_ok,
            "models_found": [str(m) for m in models],
            "litert_installed": litert_ok,
        }

    def _check_memory(self) -> dict:
        files = [MEMORY_FILE, GRAPH_FILE, GOALS_FILE, JOURNAL_FILE,
                 SKILLS_FILE, META_FILE, PATTERNS_FILE]
        return {
            "files": {f.name: f.exists() for f in files},
            "total_size": sum(f.stat().st_size for f in files if f.exists()),
        }

    def _check_disk(self) -> dict:
        try:
            stat = shutil.disk_usage(MODELS_DIR)
            return {
                "total_gb": stat.total / (1024**3),
                "free_gb": stat.free / (1024**3),
                "enough_for_models": stat.free > 2 * 1024**3,  # > 2GB
            }
        except Exception:
            return {"error": "could not check disk"}

    def format_report(self, report: dict) -> str:
        lines = [paint("âââ SELF-DIAGNOSTIC REPORT âââ", C.BOLD + C.BCYAN)]

        # Cloud
        cloud = report.get("cloud", {})
        status = paint("â", C.BGREEN) if cloud.get("available") else paint("â", C.BRED)
        lines.append(f"\n  {status} Cloud (Gemini API)")
        if cloud.get("available"):
            models = cloud.get("models", [])[:5]
            if models:
                lines.append(f"      models: {', '.join(models)}")
        else:
            lines.append(f"      {paint(cloud.get('error', 'no API key'), C.DIM)}")

        # Local
        local = report.get("local", {})
        status = paint("â", C.BGREEN) if local.get("available") else paint("â", C.BRED)
        lines.append(f"\n  {status} Local (LiteRT-LM)")
        if local.get("models_found"):
            for m in local["models_found"][:3]:
                lines.append(f"      {paint('â¢', C.GREY)} {m}")
        else:
            lines.append(f"      {paint('no local models found', C.DIM)}")

        # Memory
        mem = report.get("memory", {})
        size = mem.get("total_size", 0)
        lines.append(f"\n  {paint('â', C.BCYAN)} Memory: {size / 1024:.1f} KB across "
                     f"{sum(mem.get('files', {}).values())} files")

        # Disk
        disk = report.get("disk", {})
        if "free_gb" in disk:
            enough = paint("â", C.BGREEN) if disk.get("enough_for_models") else paint("â ", C.BYELLOW)
            lines.append(f"\n  {enough} Disk: {disk['free_gb']:.1f} GB free")

        return "\n".join(lines)


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  AUTO BACKUP  âââââ
class AutoBackup:
    """Backs up memory files before risky operations."""

    def __init__(self, backup_dir: Path = BACKUP_DIR):
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup(self, tag: str = "manual") -> Optional[Path]:
        ts = time.strftime("%Y%m%d_%H%M%S")
        dest = self.backup_dir / f"backup_{tag}_{ts}"
        dest.mkdir(parents=True, exist_ok=True)
        files = [MEMORY_FILE, GRAPH_FILE, GOALS_FILE, JOURNAL_FILE,
                 SKILLS_FILE, META_FILE, PATTERNS_FILE]
        copied = 0
        for f in files:
            if f.exists():
                shutil.copy2(f, dest / f.name)
                copied += 1
        if copied > 0:
            dbg("backup", f"backed up {copied} files to {dest}")
        return dest if copied > 0 else None

    def list_backups(self) -> list[Path]:
        return sorted(self.backup_dir.iterdir(), reverse=True)[:10]


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  SETTINGS  âââ
class SettingsManager:
    """Persistent user settings stored in settings.json â survives restarts.

    Values here become CLI defaults; /set changes them live (LIVE_KEYS)
    or persists them for the next startup.
    """

    DEFAULTS: dict[str, Any] = {
        "mode": "auto",
        "gemini_model": "gemini-3.8-flash",
        "system": ("You are a sharp, autonomous, self-evolving terminal assistant. "
                   "Be concise. Use tools when useful. Remember what you learn. "
                   "Pursue goals. Reflect on your reasoning. Extract reusable skills."),
        "autonomy": 3,
        "temperature": 0.8,
        "top_p": 0.95,
        "top_k": 64,
        "max_tokens": 1024,
        "chat_template": "chatml",
        "max_ctx_chars": 24000,
        "self_critique": False,
        "proactive": False,
        "confirm_shell": True,
        "shell_timeout": 30,
        "auto_backup_every": 0,
        "cloud_retries": 2,
        "debug": False,
        "history_limit": 40,
        "tool_rounds": 10,
        "ask_delete": True,
        "env_autoload": True,
    }
    LIVE_KEYS = {"system", "autonomy", "self_critique", "proactive", "confirm_shell",
                 "shell_timeout", "max_ctx_chars", "auto_backup_every", "debug",
                 "tool_rounds", "ask_delete"}

    def __init__(self, path: Optional[Path] = SETTINGS_FILE):
        self.path = path
        self.data: dict[str, Any] = dict(self.DEFAULTS)
        self.load()

    @classmethod
    def blank(cls) -> "SettingsManager":
        """A pure-defaults instance that never touches disk (--no-settings)."""
        m = cls.__new__(cls)
        m.path = None
        m.data = dict(cls.DEFAULTS)
        return m

    @classmethod
    def _cast(cls, key: str, value: Any) -> Any:
        default = cls.DEFAULTS.get(key)
        if default is None:
            return value
        try:
            if isinstance(default, bool):
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() in ("on", "true", "1", "yes")
            if isinstance(default, int) and not isinstance(default, bool):
                return int(value)
            if isinstance(default, float):
                return float(value)
            return str(value)
        except (TypeError, ValueError):
            return default

    def load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                for k in self.DEFAULTS:
                    if k in loaded:
                        self.data[k] = self._cast(k, loaded[k])
        except Exception:
            pass
        # sanitize values argparse would reject
        if self.data["mode"] not in ("auto", "cloud", "local", "hybrid"):
            self.data["mode"] = "auto"
        if self.data["chat_template"] not in ("gemma", "chatml", "raw"):
            self.data["chat_template"] = "chatml"
        elif self.data["chat_template"] == "gemma":
            # The default local model is Qwen3; migrate the old Gemma-specific default.
            self.data["chat_template"] = "chatml"
        try:
            if not 0 <= int(self.data["autonomy"]) <= 5:
                self.data["autonomy"] = 3
        except (TypeError, ValueError):
            self.data["autonomy"] = 3
        # sanitize values argparse would reject
        if self.data["mode"] not in ("auto", "cloud", "local", "hybrid"):
            self.data["mode"] = "auto"
        if self.data["chat_template"] not in ("gemma", "chatml", "raw"):
            self.data["chat_template"] = "chatml"
        elif self.data["chat_template"] == "gemma":
            # The default local model is Qwen3; migrate the old Gemma-specific default.
            self.data["chat_template"] = "chatml"
        try:
            if not 0 <= int(self.data["autonomy"]) <= 5:
                self.data["autonomy"] = 3
        except (TypeError, ValueError):
            self.data["autonomy"] = 3

    def save(self) -> None:
        if self.path is None:
            return
        try:
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.data:
            return self.data[key]
        return self.DEFAULTS.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        if key not in self.DEFAULTS:
            return False
        casted = self._cast(key, value)
        if key == "mode" and casted not in ("auto", "cloud", "local", "hybrid"):
            return False
        if key == "chat_template" and casted not in ("gemma", "chatml", "raw"):
            return False
        if key == "autonomy" and not 0 <= casted <= 5:
            return False
        self.data[key] = casted
        self.save()
        return True


# ââââââââââââââââââââââââââââââââââââââââââââââââââââ  USAGE STATS  ââââââââ
class StatsTracker:
    """Tracks usage stats (turns, chars, seconds, tool calls) per backend."""

    def __init__(self, path: Path = STATS_FILE):
        self.path = path
        self.data: dict[str, Any] = {"turns": 0, "chars_in": 0, "chars_out": 0,
                                     "seconds": 0.0, "tool_calls": 0, "by_backend": {}}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                for k in self.data:
                    if k in loaded:
                        self.data[k] = loaded[k]
        except Exception:
            pass

    def save(self) -> None:
        try:
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def record(self, backend_label: str, chars_in: int, chars_out: int,
               seconds: float, tool_calls: int = 0) -> None:
        self.data["turns"] += 1
        self.data["chars_in"] += chars_in
        self.data["chars_out"] += chars_out
        self.data["seconds"] += seconds
        self.data["tool_calls"] += tool_calls
        b = self.data["by_backend"].setdefault(
            backend_label, {"turns": 0, "chars_out": 0, "seconds": 0.0})
        b["turns"] += 1
        b["chars_out"] += chars_out
        b["seconds"] += seconds
        self.save()

    def summary(self) -> str:
        d = self.data
        lines = [f"turns: {d['turns']} Â· chars in: {d['chars_in']} Â· "
                 f"chars out: {d['chars_out']} Â· time: {d['seconds']:.0f}s Â· "
                 f"tool calls: {d['tool_calls']}"]
        for label, b in list(d["by_backend"].items())[:8]:
            lines.append(f"  {label}: {b['turns']} turns Â· {b['chars_out']} chars Â· {b['seconds']:.0f}s")
        return "\n".join(lines)


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  SESSIONS  âââââââ
class SessionManager:
    """Save / load whole conversations as JSON snapshots."""

    def __init__(self, dir_path: Path = SESSIONS_DIR):
        self.dir = dir_path
        self.dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_name(name: str) -> str:
        name = re.sub(r"[^a-zA-Z0-9_\-. ]", "_", (name or "").strip()) or "session"
        if not name.endswith(".json"):
            name += ".json"
        return name

    def save(self, name: str, history: list[Msg]) -> Path:
        p = self.dir / self._safe_name(name)
        payload = [{"role": m.role, "text": m.text, "meta": m.meta} for m in history]
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return p

    def load(self, name: str) -> list[Msg]:
        p = self.dir / self._safe_name(name)
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
            return [Msg(str(m.get("role", "user")), str(m.get("text", "")))
                    for m in data if isinstance(m, dict)]
        except Exception:
            return []

    def list_sessions(self) -> list[str]:
        return sorted(f.stem for f in self.dir.glob("*.json"))


# ──────────────────────────────────────────────────────────────  ENV FILE ──
class EnvManager:
    """Lightweight .env file support: KEY=VALUE pairs, loaded into os.environ.

    Search order: $TERMINAL_AI_ENV, workspace/.env, STATE_DIR/.env.
    Secrets are never printed in full (masked as ab***xy).
    """

    SECRET_HINTS = ("key", "token", "secret", "password", "passwd", "credential")

    def __init__(self, env_file: Optional[Path] = None,
                 workspace: Optional[Path] = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.path = env_file or self._find_env_file()
        self._data: dict[str, str] = {}

    @classmethod
    def _default_candidates(cls) -> list[Path]:
        cands = []
        env_override = os.environ.get("TERMINAL_AI_ENV")
        if env_override:
            cands.append(Path(env_override))
        cands.append(Path.cwd() / ".env")
        cands.append(STATE_DIR / ".env")
        return cands

    def _find_env_file(self) -> Optional[Path]:
        for c in self._default_candidates():
            if c.is_file():
                return c.resolve()
        return self.workspace / ".env"          # default write location

    # ── parsing ──────────────────────────────────────────────────────
    @staticmethod
    def _parse_line(line: str) -> Optional[tuple[str, str]]:
        s = line.strip()
        if not s or s.startswith("#"):
            return None
        if "=" not in s:
            return None
        key, _, value = s.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            return None
        value = value.strip()
        # strip surrounding matching quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        # optional "export " prefix
        return key, value

    def load(self, apply: bool = True) -> int:
        """Load .env into memory (and os.environ if apply). Returns count."""
        self._data = {}
        if self.path is None or not self.path.exists():
            return 0
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                parsed = self._parse_line(line)
                if parsed:
                    self._data[parsed[0]] = parsed[1]
        except OSError:
            return 0
        if apply:
            self.apply()
        return len(self._data)

    def apply(self) -> None:
        """Export loaded values into os.environ (never overwrites existing)."""
        for k, v in self._data.items():
            os.environ.setdefault(k, v)

    def apply_force(self) -> None:
        for k, v in self._data.items():
            os.environ[k] = v

    def save(self) -> Optional[Path]:
        """Write current data back to the .env file."""
        if self.path is None:
            return None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            lines = ["# terminal-ai .env — loaded automatically at startup"]
            for k in sorted(self._data):
                v = self._data[k]
                if " " in v or v.startswith(("\"", "'")):
                    v = '"' + v.replace('"', '\\"') + '"'
                lines.append(f"{k}={v}")
            self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return self.path
        except OSError:
            return None

    # ── accessors ─────────────────────────────────────────────────────
    def get(self, key: str, default: str = "") -> str:
        return os.environ.get(key) or self._data.get(key, default)

    def set(self, key: str, value: str, persist: bool = True) -> bool:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key or ""):
            return False
        self._data[key] = value
        os.environ[key] = value
        if persist:
            self.save()
        return True

    def unset(self, key: str, persist: bool = True) -> bool:
        existed = key in self._data or key in os.environ
        self._data.pop(key, None)
        os.environ.pop(key, None)
        if persist:
            self.save()
        return existed

    def keys(self) -> list[str]:
        return sorted(self._data)

    @classmethod
    def mask(cls, key: str, value: str) -> str:
        k = key.lower()
        if any(h in k for h in cls.SECRET_HINTS):
            if len(value) <= 4:
                return "***"
            return value[:2] + "***" + value[-2:]
        return value

    def summary(self, only_pattern: str = "") -> str:
        keys = self.keys()
        if only_pattern:
            rx = re.compile(only_pattern, re.I)
            keys = [k for k in keys if rx.search(k)]
        if not keys:
            return "(no env vars)"
        return "\n".join(f"  {k}={self.mask(k, self._data[k])}" for k in keys)

    def status(self) -> str:
        p = self.path
        if p and p.exists():
            return f"{p} ({len(self._data)} vars)"
        return "(no .env file)"


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  MEMORY  ââââ
@dataclass
class Memory:
    facts: list[dict] = field(default_factory=list)
    corrections: list[dict] = field(default_factory=list)
    preferences: dict = field(default_factory=dict)
    skills: list[dict] = field(default_factory=list)
    episodes: list[dict] = field(default_factory=list)
    version: int = 1

    @classmethod
    def load(cls, path: Path = MEMORY_FILE) -> "Memory":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()

    def save(self, path: Path = MEMORY_FILE) -> None:
        try:
            path.write_text(json.dumps(asdict(self), indent=2, default=str), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _tokens(s: str) -> set[str]:
        return {w for w in re.findall(r"[a-zA-Z0-9_]+", s.lower()) if len(w) > 2}

    def recall(self, query: str, kind: str = "all", top_k: int = 5) -> list[dict]:
        qtok = self._tokens(query)
        if not qtok:
            return []
        scored = []
        pools = {"facts": self.facts, "corrections": self.corrections,
                 "skills": self.skills, "episodes": self.episodes}
        items = []
        if kind == "all":
            for pool in pools.values():
                items.extend(pool)
        else:
            items = pools.get(kind, [])
        for it in items:
            blob = " ".join(str(v) for v in it.values())
            tok = self._tokens(blob)
            score = len(qtok & tok) / max(len(qtok), 1)
            if score > 0:
                scored.append((score, it))
        scored.sort(key=lambda x: -x[0])
        return [it for _, it in scored[:top_k]]

    def add_fact(self, k: str, v: str, source: str = "user") -> None:
        self.facts = [f for f in self.facts if f.get("k") != k]
        self.facts.append({"k": k, "v": v, "source": source, "t": time.time()})
        self.save()

    def add_correction(self, wrong: str, right: str) -> None:
        self.corrections.append({"wrong": wrong, "right": right, "t": time.time()})
        self.corrections = self.corrections[-50:]
        self.save()

    def add_episode(self, q: str, a: str, learned: str = "") -> None:
        self.episodes.append({"q": q[:200], "a": a[:400], "learned": learned, "t": time.time()})
        self.episodes = self.episodes[-200:]
        self.save()

    def forget(self, key: str) -> int:
        before = len(self.facts)
        self.facts = [f for f in self.facts if key.lower() not in f.get("k", "").lower()]
        self.save()
        return before - len(self.facts)

    def set_pref(self, k: str, v: Any) -> None:
        self.preferences[k] = v
        self.save()

    def context_block(self, query: str, max_chars: int = 1500) -> str:
        parts = []
        rec = self.recall(query, top_k=6)
        if rec:
            lines = []
            for it in rec:
                if "k" in it and "v" in it:
                    lines.append(f"  â¢ {it['k']}: {it['v']}")
                elif "right" in it:
                    lines.append(f"  â¢ correction: {it['wrong']} â {it['right']}")
            if lines:
                parts.append("RECALL:\n" + "\n".join(lines[:8]))
        if self.preferences:
            prefs = "\n".join(f"  â¢ {k} = {v}" for k, v in list(self.preferences.items())[:10])
            parts.append("PREFERENCES:\n" + prefs)
        return "\n\n".join(parts)[:max_chars]


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  KNOWLEDGE GRAPH  â
@dataclass
class KnowledgeGraph:
    entities: dict[str, dict] = field(default_factory=dict)
    relations: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = GRAPH_FILE) -> "KnowledgeGraph":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()

    def save(self, path: Path = GRAPH_FILE) -> None:
        try:
            path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except Exception:
            pass

    def add_entity(self, name: str, etype: str = "thing", props: Optional[dict] = None) -> None:
        self.entities[name] = {"type": etype, "props": props or {}, "t": time.time()}
        self.save()

    def add_relation(self, from_e: str, to_e: str, rel: str, props: Optional[dict] = None) -> None:
        self.relations.append({"from": from_e, "to": to_e, "rel": rel,
                               "props": props or {}, "t": time.time()})
        self.save()

    def query(self, entity: Optional[str] = None, rel: Optional[str] = None) -> list[dict]:
        results = []
        for r in self.relations:
            if entity and entity not in (r["from"], r["to"]):
                continue
            if rel and r["rel"] != rel:
                continue
            results.append(r)
        return results

    def context_block(self, query: str, max_chars: int = 800) -> str:
        if not self.entities and not self.relations:
            return ""
        qtok = Memory._tokens(query)
        hits = []
        for r in self.relations:
            blob = f"{r['from']} {r['rel']} {r['to']}"
            if any(t in blob.lower() for t in qtok):
                hits.append(f"  â¢ {r['from']} â[{r['rel']}]â {r['to']}")
        if not hits:
            return ""
        return "KNOWLEDGE GRAPH:\n" + "\n".join(hits[:10])[:max_chars]


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  GOALS  âââââ
@dataclass
class Goal:
    id: str
    text: str
    subgoals: list[str] = field(default_factory=list)
    status: str = "active"
    created: float = field(default_factory=time.time)
    completed: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Goal":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class GoalPlanner:
    goals: list[Goal] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = GOALS_FILE) -> "GoalPlanner":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(goals=[Goal.from_dict(g) for g in data.get("goals", [])])
        except Exception:
            return cls()

    def save(self, path: Path = GOALS_FILE) -> None:
        try:
            path.write_text(json.dumps({"goals": [g.to_dict() for g in self.goals]}, indent=2),
                            encoding="utf-8")
        except Exception:
            pass

    def add(self, text: str) -> Goal:
        gid = hashlib.md5(f"{text}{time.time()}".encode()).hexdigest()[:8]
        g = Goal(id=gid, text=text)
        self.goals.append(g)
        self.save()
        return g

    def add_subgoal(self, goal_id: str, sub: str) -> None:
        for g in self.goals:
            if g.id == goal_id:
                g.subgoals.append(sub)
                self.save()
                return

    def complete(self, goal_id: str) -> None:
        for g in self.goals:
            if g.id == goal_id:
                g.status = "done"
                g.completed = time.time()
                self.save()
                return

    def active(self) -> list[Goal]:
        return [g for g in self.goals if g.status == "active"]

    def context_block(self, max_chars: int = 600) -> str:
        active = self.active()
        if not active:
            return ""
        lines = ["ACTIVE GOALS:"]
        for g in active[:5]:
            lines.append(f"  â¢ [{g.id}] {g.text}")
            for s in g.subgoals[:3]:
                lines.append(f"      - {s}")
        return "\n".join(lines)[:max_chars]


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  JOURNAL  ââââ
class Journal:
    def __init__(self, path: Path = JOURNAL_FILE):
        self.path = path

    def write(self, entry: str) -> None:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"\n## {ts}\n{entry}\n")

    def read(self, n: int = 10) -> str:
        if not self.path.exists():
            return "(journal is empty)"
        text = self.path.read_text(encoding="utf-8")
        entries = [e.strip() for e in re.split(r"\n## ", text) if e.strip()]
        if not entries:
            return "(journal is empty)"
        return "\n\n".join("## " + e for e in entries[-max(1, n):])

    def context_block(self, max_chars: int = 500) -> str:
        if not self.path.exists():
            return ""
        text = self.path.read_text(encoding="utf-8")
        if not text.strip():
            return ""
        entries = re.split(r"\n## ", text)
        if len(entries) < 2:
            return ""
        return f"LAST JOURNAL ENTRY:\n{entries[-1][:max_chars]}"


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  SKILLS  âââââââ
@dataclass
class SkillLibrary:
    skills: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = SKILLS_FILE) -> "SkillLibrary":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(skills=data.get("skills", []))
        except Exception:
            return cls()

    def save(self, path: Path = SKILLS_FILE) -> None:
        try:
            path.write_text(json.dumps({"skills": self.skills}, indent=2), encoding="utf-8")
        except Exception:
            pass

    def add(self, name: str, steps: list[str], context: str = "") -> None:
        self.skills = [s for s in self.skills if s["name"] != name]
        self.skills.append({"name": name, "steps": steps, "context": context, "t": time.time()})
        self.save()

    def recall(self, query: str, top_k: int = 3) -> list[dict]:
        qtok = Memory._tokens(query)
        scored = []
        for s in self.skills:
            blob = f"{s['name']} {' '.join(s['steps'])} {s['context']}"
            tok = Memory._tokens(blob)
            score = len(qtok & tok) / max(len(qtok), 1)
            if score > 0:
                scored.append((score, s))
        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[:top_k]]

    def context_block(self, query: str, max_chars: int = 600) -> str:
        rec = self.recall(query, top_k=2)
        if not rec:
            return ""
        lines = ["RELEVANT SKILLS:"]
        for s in rec:
            lines.append(f"  â¢ {s['name']}:")
            for step in s["steps"][:5]:
                lines.append(f"      {step}")
        return "\n".join(lines)[:max_chars]


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  META  âââââââââ
@dataclass
class MetaLearner:
    strategies: dict[str, list[dict]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path = META_FILE) -> "MetaLearner":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(strategies=data.get("strategies", {}))
        except Exception:
            return cls()

    def save(self, path: Path = META_FILE) -> None:
        try:
            path.write_text(json.dumps({"strategies": self.strategies}, indent=2), encoding="utf-8")
        except Exception:
            pass

    def record(self, problem_type: str, strategy: str, success: bool) -> None:
        if problem_type not in self.strategies:
            self.strategies[problem_type] = []
        self.strategies[problem_type].append({"strategy": strategy, "success": success, "t": time.time()})
        self.strategies[problem_type] = self.strategies[problem_type][-50:]
        self.save()

    def best_strategy(self, problem_type: str) -> Optional[str]:
        if problem_type not in self.strategies:
            return None
        stats: dict[str, list[bool]] = {}
        for s in self.strategies[problem_type]:
            strat = s["strategy"]
            stats.setdefault(strat, []).append(s["success"])
        best, best_rate = None, -1.0
        for strat, outcomes in stats.items():
            rate = sum(outcomes) / len(outcomes)
            if rate > best_rate:
                best, best_rate = strat, rate
        return best

    def context_block(self, problem_type: str, max_chars: int = 300) -> str:
        best = self.best_strategy(problem_type)
        if not best:
            return ""
        return f"META-LEARNING: for '{problem_type}', strategy '{best}' has worked best."


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  DREAMER  ââââââ
class Dreamer:
    PROMPT = (
        "You are a memory consolidation system. Given recent conversation episodes, "
        "extract 2-3 high-level insights or patterns. Be concise. Plain text, no JSON."
    )

    def __init__(self, backend: Backend, memory: Memory, journal: Journal):
        self.backend = backend
        self.memory = memory
        self.journal = journal

    def dream(self, n_episodes: int = 20) -> str:
        episodes = self.memory.episodes[-n_episodes:]
        if len(episodes) < 5:
            return "(not enough episodes to dream)"
        blob = "\n\n".join(f"Q: {e['q']}\nA: {e['a'][:200]}" for e in episodes)
        hist = [Msg("user", blob)]
        try:
            insights = "".join(self.backend.stream(self.PROMPT, hist)).strip()
        except Exception as e:
            return f"(dream failed: {e})"
        self.journal.write(f"**Dream insights:**\n{insights}")
        return insights


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  TOOL FORGE  âââ
class ToolForge:
    def __init__(self, path: Path = TOOLS_FILE):
        self.path = path
        self.tools: dict[str, str] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            self.tools = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self.tools = {}

    def save(self) -> None:
        try:
            self.path.write_text(json.dumps(self.tools, indent=2), encoding="utf-8")
        except Exception:
            pass

    def forge(self, name: str, source: str) -> bool:
        # word-boundary check: don't reject words like "important" or "execute"
        if re.search(r"\b(import|exec|eval)\b", source):
            return False
        self.tools[name] = source
        self.save()
        return True

    def get(self, name: str) -> Optional[Callable]:
        src = self.tools.get(name)
        if not src:
            return None
        try:
            namespace: dict[str, Any] = {}
            exec(src, namespace)
            return namespace.get("tool_impl")
        except Exception:
            return None

    def list_tools(self) -> list[str]:
        return list(self.tools.keys())


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  PROACTIVE  ââââ
class ProactiveAdvisor:
    PROMPT = (
        "Given the current conversation and any active goals, suggest 1-2 proactive "
        "next steps. Be concise. If nothing to suggest, say 'none'."
    )

    def __init__(self, backend: Backend, enabled: bool = True):
        self.backend = backend
        self.enabled = enabled

    def suggest(self, history: list[Msg], goals: list[Goal]) -> Optional[str]:
        if not self.enabled or not history:
            return None
        ctx = "\n".join(f"{m.role}: {m.text[:100]}" for m in history[-5:])
        if goals:
            ctx += "\n\nActive goals:\n" + "\n".join(f"- {g.text}" for g in goals[:3])
        hist = [Msg("user", ctx)]
        try:
            suggestion = "".join(self.backend.stream(self.PROMPT, hist)).strip()
            if suggestion.lower() in ("none", ""):
                return None
            return suggestion
        except Exception:
            return None


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  TOOLS  ââââ
TOOL_SCHEMA: list[dict] = [
    {"name": "shell", "desc": "Run a shell command.", "args": {"cmd": "string"}},
    {"name": "read_file", "desc": "Read a text file.", "args": {"path": "string", "max_bytes": "int"}},
    {"name": "write_file", "desc": "Write text to a file.", "args": {"path": "string", "content": "string"}},
    {"name": "web_fetch", "desc": "Fetch a URL.", "args": {"url": "string"}},
    {"name": "remember", "desc": "Persist a fact.", "args": {"key": "string", "value": "string"}},
    {"name": "forget", "desc": "Remove facts matching key.", "args": {"key": "string"}},
    {"name": "search_memory", "desc": "Recall facts/skills/episodes.", "args": {"query": "string"}},
    {"name": "add_entity", "desc": "Add entity to knowledge graph.", "args": {"name": "string", "type": "string"}},
    {"name": "add_relation", "desc": "Add relation between entities.", "args": {"from": "string", "to": "string", "rel": "string"}},
    {"name": "query_graph", "desc": "Query knowledge graph.", "args": {"entity": "string", "rel": "string"}},
    {"name": "set_goal", "desc": "Set a new goal.", "args": {"text": "string"}},
    {"name": "add_subgoal", "desc": "Add subgoal to goal.", "args": {"goal_id": "string", "subgoal": "string"}},
    {"name": "complete_goal", "desc": "Mark goal done.", "args": {"goal_id": "string"}},
    {"name": "list_goals", "desc": "List active goals.", "args": {}},
    {"name": "reflect", "desc": "Write to journal.", "args": {"entry": "string"}},
    {"name": "read_journal", "desc": "Read journal entries.", "args": {"n": "int"}},
    {"name": "extract_skill", "desc": "Extract reusable skill.", "args": {"name": "string", "steps": "list"}},
    {"name": "forge_tool", "desc": "Forge new tool (Python).", "args": {"name": "string", "source": "string"}},
    {"name": "list_forged_tools", "desc": "List forged tools.", "args": {}},
    {"name": "list_dir", "desc": "List files in a directory.", "args": {"path": "string", "pattern": "string"}},
    {"name": "edit_file", "desc": "Search & replace text in a file (unique match required).", "args": {"path": "string", "old": "string", "new": "string"}},
    {"name": "append_file", "desc": "Append text to a file.", "args": {"path": "string", "content": "string"}},
    {"name": "delete_file", "desc": "Delete a file (asks confirmation).", "args": {"path": "string"}},
    {"name": "copy_file", "desc": "Copy a file.", "args": {"src": "string", "dst": "string"}},
    {"name": "grep_files", "desc": "Regex search across files in a directory.", "args": {"pattern": "string", "path": "string", "max_results": "int"}},
    {"name": "web_search", "desc": "Web search via DuckDuckGo (no API key).", "args": {"query": "string"}},
    {"name": "sys_info", "desc": "Show system info (python, platform, cpu, disk).", "args": {}},
    {"name": "now", "desc": "Current date/time (optional strftime format).", "args": {"format": "string"}},
    {"name": "find_files", "desc": "Find files matching a glob pattern recursively.", "args": {"pattern": "string", "path": "string", "max_results": "int"}},
    {"name": "read_lines", "desc": "Read a file line-by-line with line numbers.", "args": {"path": "string", "start": "int", "end": "int"}},
    {"name": "env", "desc": "Inspect env vars (action: list/get/set/unset/save). Secrets masked.", "args": {"action": "string", "key": "string", "value": "string"}},
    {"name": "dream", "desc": "Trigger offline memory consolidation.", "args": {}},
    {"name": "done", "desc": "Task complete with final answer.", "args": {"answer": "string"}},
]


class ToolRegistry:
    SHELL_DENY = {"rm -rf /", "mkfs", "dd if=", ":(){:|:&};:"}
    SHELL_ASK = {"sudo", "apt", "brew", "pip install", "rm ", "chmod ", "curl | sh"}

    def __init__(self, memory: Memory, graph: KnowledgeGraph, goals: GoalPlanner,
                 journal: Journal, skills: SkillLibrary, forge: ToolForge,
                 workspace: Path, confirm_shell: bool = True,
                 shell_timeout: int = 30,
                 dreamer: Optional[Dreamer] = None,
                 env: Optional[EnvManager] = None,
                 ask_delete: bool = True):
        self.memory = memory
        self.graph = graph
        self.goals = goals
        self.journal = journal
        self.skills = skills
        self.forge = forge
        self.workspace = workspace.resolve()
        self.confirm_shell = confirm_shell
        self.shell_timeout = max(1, int(shell_timeout))
        self.dreamer = dreamer
        self.env = env
        self.ask_delete = ask_delete
        self._map: dict[str, Callable] = {
            "shell": self._shell, "read_file": self._read_file,
            "write_file": self._write_file, "web_fetch": self._web_fetch,
            "remember": self._remember, "forget": self._forget,
            "search_memory": self._search_memory,
            "add_entity": self._add_entity, "add_relation": self._add_relation,
            "query_graph": self._query_graph,
            "set_goal": self._set_goal, "add_subgoal": self._add_subgoal,
            "complete_goal": self._complete_goal, "list_goals": self._list_goals,
            "reflect": self._reflect, "read_journal": self._read_journal,
            "extract_skill": self._extract_skill,
            "forge_tool": self._forge_tool,
            "list_forged_tools": self._list_forged_tools,
            "list_dir": self._list_dir, "edit_file": self._edit_file,
            "append_file": self._append_file, "delete_file": self._delete_file,
            "copy_file": self._copy_file, "grep_files": self._grep_files,
            "web_search": self._web_search,
            "sys_info": self._sys_info, "now": self._now,
            "find_files": self._find_files, "read_lines": self._read_lines,
            "env": self._env_tool,
            "dream": self._dream, "done": self._done,
        }

    def call(self, name: str, args: dict) -> str:
        if name not in self._map:
            fn = self.forge.get(name)
            if fn:
                try:
                    return str(fn(**(args or {})))
                except Exception as e:
                    return f"error: {type(e).__name__}: {e}"
            return f"error: unknown tool '{name}'"
        fn = self._map[name]
        try:
            return fn(**(args or {}))
        except Exception as e:
            return f"error: {type(e).__name__}: {e}"

    def _shell(self, cmd: str) -> str:
        if not cmd or not cmd.strip():
            return "error: empty command"
        for bad in self.SHELL_DENY:
            if bad in cmd:
                return f"error: refused dangerous command ({bad})"
        if self.confirm_shell:
            for ask in self.SHELL_ASK:
                if ask in cmd:
                    ans = input(paint(f"  â  run `{cmd}`? [y/N] ", C.BYELLOW)).strip().lower()
                    if ans not in ("y", "yes"):
                        return "cancelled by user"
                    break
        try:
            r = subprocess.run(cmd, shell=True, cwd=str(self.workspace),
                               capture_output=True, text=True,
                               timeout=self.shell_timeout)
            out = (r.stdout or "") + (r.stderr or "")
            out = out.strip()
            if len(out) > 4000:
                out = out[:4000] + f"\nâ¦[truncated, exit={r.returncode}]"
            return out or f"(no output, exit={r.returncode})"
        except subprocess.TimeoutExpired:
            return f"error: command timed out ({self.shell_timeout}s)"

    def _read_file(self, path: str, max_bytes: int = 16384) -> str:
        p = self._safe_path(path)
        if not p.exists():
            return f"error: not found: {p}"
        if not p.is_file():
            return f"error: not a file: {p}"
        data = p.read_bytes()[:max_bytes]
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("utf-8", errors="replace")

    def _write_file(self, path: str, content: str) -> str:
        p = self._safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"wrote {len(content)} bytes â {p}"

    def _web_fetch(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            return "error: url must start with http(s)://"
        req = urllib.request.Request(url, headers={"User-Agent": "terminal-ai/4.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read(32_000).decode("utf-8", errors="replace")
            text = re.sub(r"<script.*?</script>", "", data, flags=re.S | re.I)
            text = re.sub(r"<style.*?</style>", "", text, flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:8000]
        except Exception as e:
            return f"error: {type(e).__name__}: {e}"

    def _remember(self, key: str, value: str) -> str:
        self.memory.add_fact(key, value, source="agent")
        return f"remembered: {key} = {value}"

    def _forget(self, key: str) -> str:
        n = self.memory.forget(key)
        return f"forgot {n} fact(s) matching '{key}'"

    def _search_memory(self, query: str) -> str:
        items = self.memory.recall(query, top_k=8)
        if not items:
            return "(nothing relevant in memory)"
        lines = []
        for it in items:
            if "k" in it:
                lines.append(f"- {it['k']}: {it['v']}")
            elif "right" in it:
                lines.append(f"- correction: {it['wrong']} â {it['right']}")
        return "\n".join(lines)

    def _add_entity(self, name: str, type: str = "thing") -> str:
        self.graph.add_entity(name, type)
        return f"added entity: {name} ({type})"

    def _add_relation(self, **kwargs) -> str:
        from_e = kwargs.get("from") or kwargs.get("from_e")
        to_e = kwargs.get("to") or kwargs.get("to_e")
        rel = kwargs.get("rel")
        if not all([from_e, to_e, rel]):
            return "error: missing from/to/rel"
        self.graph.add_relation(from_e, to_e, rel)
        return f"added relation: {from_e} â[{rel}]â {to_e}"

    def _query_graph(self, entity: Optional[str] = None, rel: Optional[str] = None) -> str:
        results = self.graph.query(entity, rel)
        if not results:
            return "(no matching relations)"
        return "\n".join(f"- {r['from']} â[{r['rel']}]â {r['to']}" for r in results[:10])

    def _set_goal(self, text: str) -> str:
        g = self.goals.add(text)
        return f"set goal [{g.id}]: {text}"

    def _add_subgoal(self, goal_id: str, subgoal: str) -> str:
        self.goals.add_subgoal(goal_id, subgoal)
        return f"added subgoal to {goal_id}: {subgoal}"

    def _complete_goal(self, goal_id: str) -> str:
        self.goals.complete(goal_id)
        return f"completed goal {goal_id}"

    def _list_goals(self) -> str:
        active = self.goals.active()
        if not active:
            return "(no active goals)"
        lines = []
        for g in active:
            lines.append(f"[{g.id}] {g.text}")
            for s in g.subgoals:
                lines.append(f"  - {s}")
        return "\n".join(lines)

    def _reflect(self, entry: str) -> str:
        self.journal.write(entry)
        return "wrote to journal"

    def _read_journal(self, n: int = 10) -> str:
        return self.journal.read(n)

    def _extract_skill(self, name: str, steps: list[str]) -> str:
        if not isinstance(steps, list):
            return "error: steps must be a list"
        self.skills.add(name, steps)
        return f"extracted skill: {name}"

    def _forge_tool(self, name: str, source: str) -> str:
        if self.forge.forge(name, source):
            return f"forged tool: {name}"
        return "error: tool contains forbidden constructs"

    def _list_forged_tools(self) -> str:
        tools = self.forge.list_tools()
        return "\n".join(f"- {t}" for t in tools) if tools else "(no forged tools)"

    def _dream(self) -> str:
        if self.dreamer is None:
            return "error: dreamer not available"
        return self.dreamer.dream()

    def _done(self, answer: str = "") -> str:
        return answer or "(done)"

    def _safe_path(self, p: str) -> Path:
        path = Path(p).expanduser()
        if not path.is_absolute():
            path = self.workspace / path
        return path.resolve()

    def _list_dir(self, path: str = ".", pattern: str = "*") -> str:
        p = self._safe_path(path)
        if not p.exists():
            return f"error: not found: {p}"
        if not p.is_dir():
            return f"error: not a directory: {p}"
        try:
            entries = sorted(p.glob(pattern or "*"))[:200]
        except Exception as e:
            return f"error: {e}"
        if not entries:
            return f"(no entries matching '{pattern}')"
        out = []
        for e in entries:
            try:
                tag = "d" if e.is_dir() else "f"
                size = "" if e.is_dir() else f"  {e.stat().st_size}B"
                out.append(f"[{tag}] {e.name}{size}")
            except OSError:
                continue
        return "\n".join(out)

    def _edit_file(self, path: str, old: str, new: str) -> str:
        p = self._safe_path(path)
        if not p.exists():
            return f"error: not found: {p}"
        if not p.is_file():
            return f"error: not a file: {p}"
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return "error: not a utf-8 text file"
        if old not in text:
            return f"error: old text not found in {p.name}"
        n = text.count(old)
        if n > 1:
            return f"error: old text found {n} times; add more context to make it unique"
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
        return f"edited {p.name} (replaced 1 occurrence)"

    def _append_file(self, path: str, content: str) -> str:
        p = self._safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"appended {len(content)} bytes â {p}"

    def _delete_file(self, path: str) -> str:
        p = self._safe_path(path)
        if not p.exists():
            return f"error: not found: {p}"
        if p.is_dir():
            return "error: is a directory; refusing (use shell)"
        if self.ask_delete:
            ans = input(paint(f"  â  delete `{p}`? [y/N] ", C.BYELLOW)).strip().lower()
            if ans not in ("y", "yes"):
                return "cancelled by user"
        try:
            p.unlink()
            return f"deleted {p}"
        except OSError as e:
            return f"error: {e}"

    def _copy_file(self, src: str, dst: str) -> str:
        s, d = self._safe_path(src), self._safe_path(dst)
        if not s.exists():
            return f"error: not found: {s}"
        if not s.is_file():
            return f"error: not a file: {s}"
        d.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(s, d)
        except OSError as e:
            return f"error: {e}"
        return f"copied {s.name} â {d}"

    def _grep_files(self, pattern: str, path: str = ".",
                    max_results: int = 50) -> str:
        p = self._safe_path(path)
        if not p.exists():
            return f"error: not found: {p}"
        try:
            rx = re.compile(pattern)
        except re.error as e:
            return f"error: bad regex: {e}"
        results, searched = [], 0
        for f in sorted(p.rglob("*")):
            if len(results) >= max_results or searched >= 200:
                break
            try:
                if not f.is_file() or f.stat().st_size > 1_000_000:
                    continue
            except OSError:
                continue
            searched += 1
            try:
                for i, line in enumerate(
                        f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if rx.search(line):
                        results.append(f"{f}:{i}: {line.strip()[:160]}")
                        if len(results) >= max_results:
                            break
            except OSError:
                continue
        if not results:
            return f"(no matches for /{pattern}/)"
        return "\n".join(results)

    def _web_search(self, query: str) -> str:
        if not query.strip():
            return "error: empty query"
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
        req = urllib.request.Request(url, headers={"User-Agent": "terminal-ai/4.1"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read(100_000).decode("utf-8", errors="replace")
        except Exception as e:
            return f"error: {type(e).__name__}: {e}"
        results = []
        for m in re.finditer(r'class="result__a"[^>]*>(.*?)</a>', html, re.S):
            title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if title:
                results.append(title)
            if len(results) >= 8:
                break
        return "\n".join(f"- {t}" for t in results) or "(no results)"

    def _sys_info(self) -> str:
        """System information: python, platform, cpu, memory, disk."""
        import platform
        lines = [
            f"python   : {platform.python_version()} ({platform.python_implementation()})",
            f"platform : {platform.system()} {platform.release()} ({platform.machine()})",
            f"machine  : {platform.node() or 'unknown'}",
            f"cwd      : {Path.cwd()}",
            f"state    : {STATE_DIR}",
        ]
        try:
            cpu = os.cpu_count()
            lines.append(f"cpus     : {cpu}")
        except Exception:
            pass
        try:
            import shutil as _sh
            du = _sh.disk_usage(str(Path.cwd()))
            lines.append(f"disk     : {du.free // (1024**3)}GB free / {du.total // (1024**3)}GB")
        except Exception:
            pass
        try:
            if hasattr(os, "sysconf"):
                pages = os.sysconf("SC_PHYS_PAGES")
                psize = os.sysconf("SC_PAGE_SIZE")
                lines.append(f"memory   : {pages * psize // (1024**3)}GB total")
        except Exception:
            pass
        lines.append(f"mode     : {sys.executable}")
        return "\n".join(lines)

    def _now(self, format: str = "") -> str:
        """Current date/time. Optional strftime format."""
        if not format:
            return time.strftime("%Y-%m-%d %H:%M:%S %Z").strip()
        try:
            return time.strftime(format)
        except Exception as e:
            return f"error: bad format: {e}"

    def _find_files(self, pattern: str = "*", path: str = ".",
                    max_results: int = 50) -> str:
        """Find files matching a glob pattern recursively."""
        p = self._safe_path(path)
        if not p.exists():
            return f"error: not found: {p}"
        try:
            matches = sorted(p.rglob(pattern))[:max(1, int(max_results))]
        except (TypeError, ValueError) as e:
            return f"error: bad pattern: {e}"
        if not matches:
            return f"(no files matching {pattern})"
        out = []
        for m in matches:
            try:
                kind = "d" if m.is_dir() else "f"
                size = "" if m.is_dir() else f" {m.stat().st_size}B"
                out.append(f"[{kind}] {m}{size}")
            except OSError:
                continue
        return "\n".join(out)

    def _read_lines(self, path: str, start: int = 1, end: int = 0,
                    max_bytes: int = 16384) -> str:
        """Read a file line-by-line (1-indexed). end=0 means 'until EOF'."""
        p = self._safe_path(path)
        if not p.exists():
            return f"error: not found: {p}"
        if not p.is_file():
            return f"error: not a file: {p}"
        start = max(1, int(start))
        end = int(end)
        try:
            text = p.read_bytes()[:max_bytes].decode("utf-8", errors="replace")
        except OSError as e:
            return f"error: {e}"
        lines = text.splitlines()
        if not lines:
            return "(empty file)"
        if end <= 0 or end > len(lines):
            end = len(lines)
        if start > len(lines):
            return f"error: file has only {len(lines)} lines"
        chunk = lines[start - 1:end]
        return "\n".join(f"{i}: {chunk[i - start]}"
                         for i in range(start, start + len(chunk)))

    def _env_tool(self, action: str = "list", key: str = "", value: str = "") -> str:
        """Inspect / modify environment variables (secrets masked)."""
        if self.env is None:
            return "error: env manager not available"
        action = (action or "list").lower().strip()
        if action == "list":
            return self.env.summary()
        if action == "get":
            if not key:
                return "error: missing key"
            return f"{key}={EnvManager.mask(key, self.env.get(key))}"
        if action == "set":
            if not key:
                return "error: missing key"
            if self.env.set(key, value):
                return f"set {key}={EnvManager.mask(key, value)}"
            return "error: invalid key name"
        if action == "unset":
            if not key:
                return "error: missing key"
            return f"unset {key}" if self.env.unset(key) else f"(was not set: {key})"
        if action == "save":
            p = self.env.save()
            return f"saved {p}" if p else "error: could not save .env"
        return f"error: unknown action '{action}' (list/get/set/unset/save)"

    def schema_prompt(self) -> str:
        lines = ["TOOLS (respond with <tool_call>{\"name\":\"...\",\"args\":{...}}</tool_call>):"]
        for t in TOOL_SCHEMA:
            args = ", ".join(f"{k}: {v}" for k, v in t["args"].items())
            lines.append(f"  â¢ {t['name']}({args}) â {t['desc']}")
        forged = self.forge.list_tools()
        if forged:
            lines.append(f"FORGED TOOLS: {', '.join(forged)}")
        lines.append("Call one tool at a time. When complete, call `done` with final answer.")
        return "\n".join(lines)


def parse_tool_calls(text: str) -> list[dict]:
    out = []
    for m in re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.S):
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict) and "name" in obj:
                obj.setdefault("args", {})
                out.append(obj)
        except Exception:
            nm = re.search(r'"name"\s*:\s*"([^"]+)"', m.group(1))
            if nm:
                out.append({"name": nm.group(1), "args": {}})
    return out


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââ  â GEMINI  âââââââââ
class GeminiBackend(Backend):
    supports_tools = True

    def __init__(self, model: str = "gemini-3.8-flash", api_key: Optional[str] = None,
                 temperature: float = 1.0, top_p: float = 0.95,
                 max_tokens: int = 2048, retries: int = 2):
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.retries = max(0, int(retries))
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY")
                        or os.environ.get("GOOGLE_API_KEY"))
        if not self.api_key:
            raise BackendError("no Gemini API key.\n      export GEMINI_API_KEY='...'")
        self._sdk, self._client, self._types = self._connect()
        self.label = f"gemini Â· {model}"

    def _connect(self):
        try:
            from google import genai
            return "genai", genai.Client(api_key=self.api_key), genai.types
        except Exception:
            pass
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            return "legacy", genai, None
        except Exception as e:
            raise BackendError(f"Gemini SDK missing -> pip install google-genai  ({e})")

    def _config(self, system: str):
        T = self._types
        if T is None:
            return None
        kw = {"temperature": self.temperature, "top_p": self.top_p,
              "max_output_tokens": self.max_tokens}
        if system:
            kw["system_instruction"] = system
        while kw:
            try:
                return T.GenerateContentConfig(**kw)
            except Exception:
                kw.pop(list(kw)[-1], None)
        return None

    def _contents(self, history: list[Msg]):
        T, out = self._types, []
        for m in history:
            role = "model" if m.role == "assistant" else m.role
            try:
                out.append(T.Content(role=role, parts=[T.Part.from_text(text=m.text)]))
            except Exception:
                out.append({"role": role, "parts": [{"text": m.text}]})
        return out

    def stream(self, system: str, history: list[Msg],
               tools: Optional[list[dict]] = None) -> Iterator[str]:
        """Stream with automatic retry + exponential backoff on failure."""
        attempt, delay = 0, 1.0
        while True:
            try:
                yield from self._stream_once(system, history, tools)
                return
            except KeyboardInterrupt:
                raise
            except Exception as e:
                attempt += 1
                if attempt > self.retries:
                    raise
                dbg("gemini", f"stream failed ({e}); retry {attempt}/{self.retries} "
                              f"in {delay:.0f}s")
                time.sleep(delay)
                delay *= 2

    def _stream_once(self, system: str, history: list[Msg],
                     tools: Optional[list[dict]] = None) -> Iterator[str]:
        if self._sdk == "genai":
            cfg, contents = self._config(system), self._contents(history)
            try:
                resp = self._client.models.generate_content_stream(
                    model=self.model, contents=contents, config=cfg)
            except TypeError:
                resp = self._client.models.generate_content_stream(
                    model=self.model, contents=contents)
            for chunk in resp:
                txt = getattr(chunk, "text", None)
                if txt:
                    yield txt
        else:
            gm = self._client.GenerativeModel(self.model, system_instruction=system or None)
            hist = [{"role": m.role if m.role != "assistant" else "model",
                     "parts": [m.text]} for m in history]
            for chunk in gm.generate_content(hist, stream=True):
                txt = getattr(chunk, "text", "") or ""
                if txt:
                    yield txt


# âââââââââââââââââââââââââââââââââââââââââââââââ  â¡ LiteRT-LM (1B, local)  ââ
class LiteRTBackend(Backend):
    MODULES = ("litert_lm", "litertlm", "litert_lm.python",
               "ai_edge_litert_lm", "google_litert_lm")
    METHODS = ("GenerateContent", "generate_content", "Generate",
               "generate", "chat", "Chat", "__call__")

    def __init__(self, model_path, device: str = "cpu", temperature: float = 0.8,
                 top_k: int = 64, top_p: float = 0.95, max_tokens: int = 1024,
                 seed: int = 0, style: str = "chatml"):
        self.model_path = Path(model_path).expanduser()
        if not self.model_path.exists():
            raise BackendError(f"model not found: {self.model_path}")
        self.device = device
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.seed = seed
        self.style = style
        self._mod = _import_first(*self.MODULES)
        if self._mod is None:
            raise BackendError("LiteRT-LM bindings not importable -> pip install litert-lm")
        self._cancel = threading.Event()
        self._engine = self._bind()
        self._method = self._pick_method()
        self.label = f"litert Â· {self.model_path.stem} Â· {device}"

    def _bind(self):
        mod = self._mod
        Engine = _find(mod, "Engine", "LiteRTEngine", "LlmEngine", "Model")
        if Engine is None:
            raise BackendError(f"no Engine class inside {mod.__name__}")
        CFG = _find(mod, "EngineConfig", "Config", "EngineOptions")
        attempts = []
        if CFG is not None:
            attempts.append(lambda: Engine(self._mkcfg(CFG)))
        attempts += [lambda: Engine(model_path=str(self.model_path), backend=self.device),
                     lambda: Engine(str(self.model_path), self.device),
                     lambda: Engine(str(self.model_path)),
                     lambda: Engine(model=str(self.model_path))]
        errs = []
        for fn in attempts:
            try:
                eng = fn()
                break
            except Exception as e:
                errs.append(f"{type(e).__name__}: {e}")
        else:
            raise BackendError("could not build Engine:\n      - " + "\n      - ".join(errs))
        for life in ("initialize", "Initialize", "setup", "Setup", "load", "Load"):
            f = getattr(eng, life, None)
            if callable(f):
                try:
                    f()
                except Exception:
                    pass
                break
        return eng

    def _mkcfg(self, CFG):
        try:
            names = set(inspect.signature(CFG).parameters)
        except Exception:
            names = set()
        cand = {"model_path": str(self.model_path), "model": str(self.model_path),
                "backend": self.device, "temperature": self.temperature, "top_k": self.top_k,
                "top_p": self.top_p, "max_tokens": self.max_tokens,
                "max_output_tokens": self.max_tokens, "seed": self.seed, "num_threads": 4}
        kw = {k: v for k, v in cand.items() if not names or k in names}
        for fallback in (lambda: CFG(**kw), lambda: CFG(model_path=str(self.model_path)),
                         lambda: CFG()):
            try:
                return fallback()
            except Exception:
                continue
        raise BackendError("could not build EngineConfig")

    def _pick_method(self):
        for n in self.METHODS:
            m = getattr(self._engine, n, None)
            if callable(m):
                return n, m
        raise BackendError("engine exposes no generation method")

    def _invoke(self, prompt: str, messages: list[dict], cb) -> Any:
        name, meth = self._method
        try:
            params = list(inspect.signature(meth).parameters)
        except Exception:
            params = []
        kwargs, pos_cb = {}, False
        for kw in ("callback", "stream_callback", "on_token", "token_callback", "cb"):
            if kw in params:
                kwargs[kw] = cb
                break
        else:
            pos_cb = len(params) >= 2
        if name.lower().startswith("chat"):
            try:
                return meth(messages, cb) if pos_cb else meth(messages, **kwargs)
            except Exception:
                pass
        try:
            return meth(prompt, cb, **kwargs) if pos_cb else meth(prompt, **kwargs)
        except TypeError:
            try:
                return meth(prompt)
            except Exception:
                return meth()

    def stream(self, system: str, history: list[Msg],
               tools: Optional[list[dict]] = None) -> Iterator[str]:
        prompt = self._render(system, history, tools)
        messages = [{"role": m.role, "content": m.text} for m in history]
        q: "queue.Queue[Any]" = queue.Queue()
        got = [0]
        self._cancel.clear()

        def cb(*a):
            text = ""
            for x in a:
                if isinstance(x, str):
                    text = x
                    break
                if isinstance(x, (bytes, bytearray)):
                    text = x.decode("utf-8", "ignore")
                    break
            if text:
                got[0] += 1
                q.put(text)
            return not self._cancel.is_set()

        def worker():
            try:
                out = self._invoke(prompt, messages, cb)
                if got[0] == 0 and isinstance(out, str) and out:
                    q.put(out)
            except Exception as e:
                q.put(("__err__", e))
            finally:
                q.put(None)

        threading.Thread(target=worker, daemon=True).start()
        while True:
            item = q.get()
            if item is None:
                break
            if isinstance(item, tuple) and item and item[0] == "__err__":
                raise BackendError(str(item[1]))
            yield item

    def _render(self, system: str, history: list[Msg],
                tools: Optional[list[dict]]) -> str:
        style = self.style
        if style == "raw":
            return history[-1].text if history else ""
        if style == "chatml":
            out = []
            full_sys = system or ""
            if tools:
                full_sys += "\n\n" + self._tool_block(tools)
            if full_sys:
                out.append(f"<|im_start|>system\n{full_sys}<|im_end|>\n")
            for m in history:
                role = "assistant" if m.role in ("model", "assistant") else m.role
                out.append(f"<|im_start|>{role}\n{m.text}<|im_end|>\n")
            out.append("<|im_start|>assistant\n")
            return "".join(out)
        out, sys_txt = [], (system or "").strip()
        if tools:
            sys_txt += "\n\n" + self._tool_block(tools)
        for i, m in enumerate(history):
            text = m.text
            if i == 0 and m.role == "user" and sys_txt:
                text = f"{sys_txt}\n\n{text}"
                sys_txt = ""
            role = "user" if m.role == "user" else "model"
            out.append(f"<start_of_turn>{role}\n{text.strip()}<end_of_turn>\n")
        out.append("<start_of_turn>model\n")
        return "".join(out)

    def _tool_block(self, tools: list[dict]) -> str:
        lines = ["You may call tools by emitting <tool_call>{\"name\":\"...\",\"args\":{...}}</tool_call> on its own line.",
                 "Available tools:"]
        for t in tools:
            args = ", ".join(f"{k}: {v}" for k, v in t.get("args", {}).items())
            lines.append(f"  - {t['name']}({args}): {t['desc']}")
        lines.append("After each tool result, think again and either call another tool or call `done`.")
        return "\n".join(lines)

    def cancel(self) -> None:
        self._cancel.set()

    def close(self) -> None:
        for n in ("Destroy", "destroy", "Close", "close", "Release"):
            f = getattr(self._engine, n, None)
            if callable(f):
                try:
                    f()
                except Exception:
                    pass
                break


# âââââââââââââââââââââââââââââââââââââââââââââââââââââ  HYBRID BACKEND  âââââ
class HybridBackend(Backend):
    """Tries cloud first, falls back to local on failure. Online+offline together."""

    def __init__(self, cloud: Optional[Backend], local: Optional[Backend],
                 router: TaskRouter):
        self.cloud = cloud
        self.local = local
        self.router = router
        self._active = cloud or local
        self.label = "hybrid"
        self.supports_tools = True

    def stream(self, system: str, history: list[Msg],
               tools: Optional[list[dict]] = None) -> Iterator[str]:
        prompt = history[-1].text if history else ""
        backend_type, model_name = self.router.select_backend(
            prompt, local_available=self.local is not None)

        # Choose backend
        if backend_type == "local" and self.local:
            self._active = self.local
            self.label = f"hybridâlocal Â· {model_name}"
        elif self.cloud:
            self._active = self.cloud
            self.label = f"hybridâcloud Â· {model_name}"
        elif self.local:
            self._active = self.local
            self.label = f"hybridâlocal Â· {model_name}"
        else:
            raise BackendError("no backend available")

        # Try active backend, fallback on error (only if nothing yielded yet,
        # otherwise a fallback would duplicate already-printed output)
        yielded = False
        try:
            for chunk in self._active.stream(system, history, tools):
                yielded = True
                yield chunk
        except Exception as e:
            if yielded:
                raise
            dbg("hybrid", f"primary failed: {e}")
            # Fallback
            if self._active == self.cloud and self.local:
                warn(f"Cloud failed, falling back to local")
                self._active = self.local
                self.label = f"hybridâlocal (fallback)"
                yield from self.local.stream(system, history, tools)
            elif self._active == self.local and self.cloud:
                warn(f"Local failed, falling back to cloud")
                self._active = self.cloud
                self.label = f"hybridâcloud (fallback)"
                yield from self.cloud.stream(system, history, tools)
            else:
                raise

    def cancel(self) -> None:
        if self._active:
            self._active.cancel()

    def close(self) -> None:
        if self.cloud:
            self.cloud.close()
        if self.local:
            self.local.close()


# âââââââââââââââââââââââââââââââââââââââââââââââââââââ  OBSERVER / CRITIC  ââ
class Observer:
    PROMPT = (
        "You are a silent observer. Given the last user message and assistant reply, "
        "extract facts, corrections, preferences, entities, relations. "
        "Respond ONLY with JSON:\n"
        '{"facts":[{"k":"...","v":"..."}],"corrections":[{"wrong":"...","right":"..."}],'
        '"preferences":{"key":"value"},"entities":[{"name":"...","type":"..."}],'
        '"relations":[{"from":"...","to":"...","rel":"..."}]}\n'
        "If nothing to learn, respond: {}"
    )

    def __init__(self, backend: Backend, memory: Memory, graph: KnowledgeGraph,
                 enabled: bool = True):
        self.backend = backend
        self.memory = memory
        self.graph = graph
        self.enabled = enabled

    def observe(self, user_msg: str, assistant_msg: str) -> None:
        if not self.enabled or not user_msg or not assistant_msg:
            return
        hist = [Msg("user", user_msg), Msg("model", assistant_msg)]
        try:
            buf = []
            for chunk in self.backend.stream(self.PROMPT, hist):
                buf.append(chunk)
                if len("".join(buf)) > 800:
                    break
            raw = "".join(buf).strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.M).strip()
            m = re.search(r"\{.*\}", raw, re.S)
            if not m:
                return
            data = json.loads(m.group(0))
        except Exception as e:
            dbg("observer", f"failed: {e}")
            return
        n_facts = n_corr = n_prefs = n_ent = n_rel = 0
        for f in data.get("facts", []) or []:
            if isinstance(f, dict) and "k" in f and "v" in f:
                self.memory.add_fact(str(f["k"]), str(f["v"]), source="observer")
                n_facts += 1
        for c in data.get("corrections", []) or []:
            if isinstance(c, dict) and "wrong" in c and "right" in c:
                self.memory.add_correction(str(c["wrong"]), str(c["right"]))
                n_corr += 1
        prefs = data.get("preferences") or {}
        if isinstance(prefs, dict):
            for k, v in prefs.items():
                self.memory.set_pref(str(k), str(v))
                n_prefs += 1
        for e in data.get("entities", []) or []:
            if isinstance(e, dict) and "name" in e:
                self.graph.add_entity(str(e["name"]), str(e.get("type", "thing")))
                n_ent += 1
        for r in data.get("relations", []) or []:
            if isinstance(r, dict) and "from" in r and "to" in r and "rel" in r:
                self.graph.add_relation(str(r["from"]), str(r["to"]), str(r["rel"]))
                n_rel += 1
        if any([n_facts, n_corr, n_prefs, n_ent, n_rel]):
            info(paint("    ð learned ", C.DIM) +
                 paint(f"{n_facts} facts Â· {n_corr} corr Â· {n_prefs} prefs Â· "
                       f"{n_ent} entities Â· {n_rel} relations", C.GREY))


class Critic:
    CRITIQUE = (
        "You are a strict self-critic. Given the user question and a draft answer, "
        "list up to 3 concrete issues (factual, incomplete, unclear). If fine, say 'OK'."
    )
    REFINE = (
        "You previously drafted an answer. A critic pointed out issues. "
        "Produce an improved final answer. Do not mention the critique process."
    )

    def __init__(self, backend: Backend, enabled: bool = True):
        self.backend = backend
        self.enabled = enabled

    def refine(self, system: str, user_msg: str, draft: str) -> str:
        if not self.enabled or not draft:
            return draft
        hist1 = [Msg("user", f"Q: {user_msg}\n\nDraft:\n{draft}")]
        try:
            critique = "".join(self.backend.stream(self.CRITIQUE, hist1)).strip()
        except Exception:
            return draft
        if not critique or critique.lower().startswith("ok"):
            return draft
        hist2 = [Msg("user", f"Q: {user_msg}\n\nDraft:\n{draft}\n\nCritique:\n{critique}")]
        try:
            return "".join(self.backend.stream(self.REFINE, hist2)).strip() or draft
        except Exception:
            return draft


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  AGENT LOOP  âââââ
class Agent:
    MAX_TOOL_ROUNDS = 10

    def __init__(self, backend: Backend, memory: Memory, graph: KnowledgeGraph,
                 goals: GoalPlanner, journal: Journal, skills: SkillLibrary,
                 meta: MetaLearner, tools: ToolRegistry, forge: ToolForge,
                 router: TaskRouter, patterns: PatternLearner,
                 system: str, autonomy: int = 3, self_critique: bool = False,
                 proactive: bool = True, max_ctx_chars: int = 24000,
                 stats: Optional[StatsTracker] = None,
                 settings: Optional[SettingsManager] = None,
                 session_mgr: Optional[SessionManager] = None,
                 backup: Optional[AutoBackup] = None,
                 auto_backup_every: int = 0):
        self.backend = backend
        self.memory = memory
        self.graph = graph
        self.goals = goals
        self.journal = journal
        self.skills = skills
        self.meta = meta
        self.tools = tools
        self.forge = forge
        self.router = router
        self.patterns = patterns
        self.base_system = system
        self.autonomy = autonomy
        self.self_critique = self_critique
        self.proactive = proactive
        self.max_ctx_chars = max_ctx_chars
        self.stats = stats
        self.settings = settings
        self.session_mgr = session_mgr
        self.backup = backup
        self.auto_backup_every = max(0, int(auto_backup_every))
        self._turn_count = 0
        self.critic = Critic(backend, enabled=self_critique)
        self.observer = Observer(backend, memory, graph, enabled=autonomy >= 3)
        self.dreamer = Dreamer(backend, memory, journal)
        self.tools.dreamer = self.dreamer
        self.advisor = ProactiveAdvisor(backend, enabled=proactive)
        self.history: list[Msg] = []
        # v4.2: tunable tool rounds + history limit from settings
        self.max_tool_rounds = max(1, int(Agent.MAX_TOOL_ROUNDS))
        self.history_limit = 0
        if settings is not None:
            try:
                self.max_tool_rounds = max(1, int(settings.get("tool_rounds", 10)))
            except (TypeError, ValueError):
                pass
            try:
                self.history_limit = max(0, int(settings.get("history_limit", 40)))
            except (TypeError, ValueError):
                pass

    def _classify_problem(self, query: str) -> str:
        return self.router.classify(query)

    def _system_prompt(self, user_query: str) -> str:
        parts = [self.base_system]
        parts.append(f"Today is {time.strftime('%A, %B %d, %Y')}.")
        problem_type = self._classify_problem(user_query)

        mem = self.memory.context_block(user_query)
        if mem:
            parts.append(mem)
        gctx = self.graph.context_block(user_query)
        if gctx:
            parts.append(gctx)
        gblock = self.goals.context_block()
        if gblock:
            parts.append(gblock)
        jblock = self.journal.context_block()
        if jblock:
            parts.append(jblock)
        sblock = self.skills.context_block(user_query)
        if sblock:
            parts.append(sblock)
        mblock = self.meta.context_block(problem_type)
        if mblock:
            parts.append(mblock)
        if self.autonomy >= 1:
            parts.append(self.tools.schema_prompt())
        if self.autonomy >= 4:
            parts.append(
                "SELF-EVOLUTION MODE: You have goals, journal, and skill extraction. "
                "When you complete a goal, call complete_goal. When you notice a reusable "
                "procedure, call extract_skill. Periodically reflect by calling reflect. "
                "If you need a new capability, call forge_tool with Python source."
            )
        return "\n\n".join(p for p in parts if p)

    def _trim(self) -> None:
        total = sum(len(m.text) for m in self.history)
        while self.history and total > self.max_ctx_chars:
            total -= len(self.history.pop(0).text)
        limit = getattr(self, "history_limit", 0)
        if limit > 0 and len(self.history) > limit:
            del self.history[:len(self.history) - limit]

    def _stream_collect(self, system: str, history: list[Msg]) -> tuple[str, list[dict]]:
        buf: list[str] = []
        spinner = Spinner()
        spinner.start()
        first = True
        try:
            for chunk in self.backend.stream(system, history,
                                             tools=TOOL_SCHEMA if self.autonomy >= 1 else None):
                if first:
                    spinner.stop()
                    sys.stdout.write(paint("â ", C.BCYAN) +
                                     paint(self.backend.label, C.DIM) + " ")
                    sys.stdout.flush()
                    first = False
                buf.append(chunk)
                sys.stdout.write(chunk)
                sys.stdout.flush()
        except KeyboardInterrupt:
            self.backend.cancel()
        finally:
            spinner.stop()
        text = "".join(buf)
        if not first:
            print()
        calls = parse_tool_calls(text) if self.autonomy >= 1 else []
        return text, calls

    def dream(self) -> str:
        return self.dreamer.dream()

    def turn(self, user_msg: str) -> str:
        self.history.append(Msg("user", user_msg))
        self._trim()
        t0 = time.time()
        system = self._system_prompt(user_msg)
        problem_type = self._classify_problem(user_msg)

        # Learn the pattern
        prompt_len = len(user_msg.split())
        model_name = getattr(self.backend, 'model', getattr(self.backend, 'label', 'unknown'))

        final_answer = ""
        rounds = 0
        tool_calls_used = 0
        strategy_used = "direct"
        while rounds < self.max_tool_rounds:
            rounds += 1
            text, calls = self._stream_collect(system, self.history)

            if not calls:
                final_answer = text.strip()
                break

            self.history.append(Msg("model", text))
            strategy_used = "tool_use"

            any_done = False
            for c in calls:
                name = c.get("name", "")
                args = c.get("args", {}) or {}
                sys.stdout.write(paint(f"    â {name}", C.YELLOW) +
                                 paint(f"({json.dumps(args)[:80]})", C.GREY) + "\n")
                result = self.tools.call(name, args)
                tool_calls_used += 1
                sys.stdout.write(paint("      â ", C.GREY) +
                                 paint(result[:200].replace("\n", " "), C.DIM) + "\n")
                self.history.append(Msg("tool", f"[{name}] {result}"))
                if name == "done":
                    final_answer = result.strip()
                    any_done = True
                    break
                if name == "complete_goal":
                    self.meta.record(problem_type, strategy_used, True)

            if any_done:
                break

            if self.autonomy < 2 and any("error:" in h.text for h in self.history[-len(calls):]):
                final_answer = text.strip()
                break
        else:
            final_answer = "(reached max tool rounds)"
            self.meta.record(problem_type, strategy_used, False)

        if self.self_critique and final_answer:
            refined = self.critic.refine(system, user_msg, final_answer)
            if refined != final_answer:
                sys.stdout.write(paint("    ðª refined\n", C.DIM))
                final_answer = refined

        if self.autonomy >= 3:
            self.observer.observe(user_msg, final_answer)

        if final_answer and (not self.history or self.history[-1].text != final_answer):
            self.history.append(Msg("model", final_answer))

        if self.proactive:
            suggestion = self.advisor.suggest(self.history, self.goals.active())
            if suggestion:
                sys.stdout.write(paint("    ð¡ ", C.BYELLOW) +
                                 paint(suggestion, C.GREY) + "\n")

        # Record pattern
        self.patterns.record(problem_type, str(model_name), prompt_len)

        dt = max(time.time() - t0, 1e-6)
        chars = len(final_answer)
        info(f"  â¡ {chars} chars Â· {dt:.1f}s Â· {rounds} round(s) Â· "
             f"task={problem_type} Â· "
             f"mem {len(self.memory.facts)} facts Â· {len(self.goals.active())} goals")
        print()

        # Usage stats
        if self.stats is not None:
            try:
                self.stats.record(getattr(self.backend, "label", "unknown"),
                                  len(user_msg), chars, dt, tool_calls_used)
            except Exception:
                pass

        # Periodic auto-backup
        self._turn_count += 1
        if (self.backup is not None and self.auto_backup_every > 0
                and self._turn_count % self.auto_backup_every == 0):
            try:
                if self.backup.backup("auto"):
                    info(paint("  ð¾ auto-backup created", C.GREY))
            except Exception:
                pass

        self.memory.add_episode(user_msg, final_answer)
        return final_answer

    def reset(self) -> None:
        self.history.clear()


# ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ  CLI  âââââââ
HELP = f"""{paint('commands', C.BOLD+C.BCYAN)}
  /clear            wipe conversation
  /model <name>     switch Gemini model (e.g., gemini-3.8-flash, gemini-3.1-pro)
  /load <file>      switch to local .litertlm
  /cloud            switch back to Gemini
  /hybrid           enable hybrid mode (cloud + local fallback)
  /auto             enable auto mode (task-based routing)
  /local            force local mode
  /route <text>     preview task routing without sending
  /diagnose         run self-diagnostic
  /backup           backup memory
  /patterns         show learned task patterns
  /models           list all available models (cloud + local)
  /download [name]  download a local model from HF
  /system <text>    set system prompt
  /autonomy <0-5>   set autonomy level
  /critique on|off  toggle self-critique
  /proactive on|off toggle proactive suggestions
  /remember <k=v>   persist a fact
  /forget <key>     forget facts matching key
  /memory [kind]    show facts|corrections|prefs|skills|episodes
  /search <query>   keyword search memory
  /goal <text>      set a new goal
  /goals            list active goals
  /complete <id>    mark goal done
  /reflect <text>   write to journal
  /journal [n]      read journal entries
  /skill <name>|<steps...>  extract a skill
  /skills           list skills
  /forge <name> <source>  forge a tool
  /dream            trigger memory consolidation
  /hf-login <token> login to Hugging Face
  /hf-logout        logout from HF
  /hf-status        show HF login status
  /tools            list available tools
  /save <file>      dump transcript
  /stats            show all stats
  /settings         show persistent settings
  /set <k> <v>      change a setting (e.g. /set temperature 0.5)
  /usage            usage stats (turns/chars/time per backend)
  /save-session [n] save current conversation
  /load-session <n> load a saved session
  /sessions         list saved sessions
  /export <file>    export transcript (.md or .json)
  /reset            factory reset memory (backs up first)
  /env [pattern]     list env vars (from .env; secrets masked)
  /env-set <k> <v>  set an env var and persist to .env
  /env-get <k>      show one env var (masked if secret)
  /env-unset <k>    remove an env var (and from .env)
  /env-save         save env vars to the .env file
  /history [n]      show recent messages (default 10)
  /sysinfo          show system info
  /debug on/off     toggle debug logging
  /quit             exit"""


def build_backends(args: argparse.Namespace, registry: ModelRegistry,
                   downloader: AutoDownloader, router: TaskRouter,
                   hf: HFManager) -> Backend:
    """Build the appropriate backend based on mode."""
    mode = args.mode

    # Try to load local model
    local_backend = None
    local_path = None
    if args.auto_download or mode in ("local", "hybrid", "auto"):
        local_path = downloader.find_local_model()
        if not local_path and args.auto_download:
            local_path = downloader.ensure_model()
        if local_path:
            try:
                local_backend = LiteRTBackend(
                    local_path, device=args.device, temperature=args.temperature,
                    top_k=args.top_k, top_p=args.top_p,
                    max_tokens=args.max_tokens, style=args.chat_template)
            except Exception as e:
                dbg("backend", f"local failed to load: {e}")

    # Build cloud backend
    cloud_backend = None
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        try:
            cloud_backend = GeminiBackend(
                args.gemini_model, temperature=args.temperature,
                top_p=args.top_p, max_tokens=args.max_tokens,
                retries=getattr(args, "cloud_retries", 2))
        except Exception as e:
            dbg("backend", f"cloud failed to load: {e}")

    # Select backend based on mode
    if mode == "local":
        if local_backend:
            return local_backend
        raise BackendError("no local model available")
    elif mode == "cloud":
        if cloud_backend:
            return cloud_backend
        raise BackendError("no Gemini API key. Set GEMINI_API_KEY")
    elif mode == "hybrid":
        if cloud_backend or local_backend:
            return HybridBackend(cloud_backend, local_backend, router)
        raise BackendError("no backends available")
    else:  # auto
        if cloud_backend and local_backend:
            return HybridBackend(cloud_backend, local_backend, router)
        elif cloud_backend:
            return cloud_backend
        elif local_backend:
            return local_backend
        raise BackendError(
            "no backends available.\n"
            "      Set GEMINI_API_KEY for cloud, or use --auto-download for local")


def banner(agent: Agent, args: argparse.Namespace, hf: HFManager,
           registry: ModelRegistry, patterns: PatternLearner,
           env_mgr: Optional[EnvManager] = None) -> None:
    print(paint("  â¬¢ terminal-ai", C.BOLD + C.BCYAN) +
          paint(f"  v{__version__}  Â·  hybrid self-evolving agent", C.DIM))
    print(f"    brain     {paint(agent.backend.label, C.BGREEN)}")
    print(f"    mode      {paint(args.mode, C.BCYAN)}" +
          paint("  (auto/cloud/local/hybrid)", C.GREY))
    print(f"    autonomy  {paint(str(args.autonomy), C.BCYAN)}" +
          paint("  (0..5)", C.GREY))
    print(f"    critique  {paint('on' if args.self_critique else 'off', C.GREY)}" +
          f"   proactive {paint('on' if args.proactive else 'off', C.GREY)}")
    hf_status = paint("â logged in", C.BGREEN) if hf.is_logged_in() else paint("â not logged in", C.DIM)
    print(f"    hf        {hf_status}")
    if patterns.total_prompts > 0:
        print(f"    patterns  {paint(f'{patterns.total_prompts} prompts learned', C.GREY)}")
    if env_mgr is not None:
        print(f"    env       {paint(env_mgr.status(), C.DIM)}")
    print(f"    state     {paint(str(STATE_DIR), C.DIM)}")
    print(paint("    /help Â· /route Â· /diagnose Â· /models Â· /download Â· Ctrl-D quits",
                C.GREY) + "\n")


def _export_transcript(agent: "Agent", p: Path) -> None:
    """Export the conversation as .json or markdown."""
    if p.suffix.lower() == ".json":
        payload = [{"role": m.role, "text": m.text} for m in agent.history]
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                     encoding="utf-8")
    else:
        lines = [f"# terminal-ai Â· {agent.backend.label}\n",
                 f"> system: {agent.base_system}\n"]
        for m in agent.history:
            lines.append(f"**{m.role}:** {m.text}\n")
        p.write_text("\n".join(lines), encoding="utf-8")
    ok(f"exported â {p}\n")


def _apply_live_setting(agent: "Agent", args: argparse.Namespace,
                        settings: SettingsManager, key: str) -> None:
    """Apply a live-changeable setting to the running agent immediately."""
    v = settings.get(key)
    if key == "autonomy":
        agent.autonomy = int(v)
        args.autonomy = int(v)
        agent.critic.enabled = agent.self_critique and int(v) >= 3
        agent.observer.enabled = int(v) >= 3
        agent.advisor.enabled = args.proactive and int(v) >= 4
    elif key == "self_critique":
        agent.self_critique = bool(v)
        agent.critic.enabled = bool(v) and agent.autonomy >= 3
    elif key == "proactive":
        agent.proactive = bool(v)
        args.proactive = bool(v)
        agent.advisor.enabled = bool(v) and agent.autonomy >= 4
    elif key == "confirm_shell":
        agent.tools.confirm_shell = bool(v)
    elif key == "shell_timeout":
        agent.tools.shell_timeout = max(1, int(v))
    elif key == "max_ctx_chars":
        agent.max_ctx_chars = int(v)
        args.max_ctx_chars = int(v)
    elif key == "auto_backup_every":
        agent.auto_backup_every = max(0, int(v))
    elif key == "system":
        agent.base_system = str(v)
    elif key == "debug":
        if v:
            os.environ["TERMINAL_AI_DEBUG"] = "1"
        else:
            os.environ.pop("TERMINAL_AI_DEBUG", None)
        info(f"  debug → {'on' if v else 'off'}\n")
    elif key == "tool_rounds":
        agent.max_tool_rounds = max(1, int(v))
    elif key == "ask_delete":
        agent.tools.ask_delete = bool(v)


def handle_cmd(line: str, agent: Agent, args: argparse.Namespace, hf: HFManager,
               registry: ModelRegistry, downloader: AutoDownloader,
               router: TaskRouter, diagnostic: SelfDiagnostic,
               backup: AutoBackup, patterns: PatternLearner,
               env_mgr: Optional[EnvManager] = None) -> bool:
    cmd, _, rest = line[1:].partition(" ")
    cmd, rest = cmd.lower().strip(), rest.strip()
    if cmd in ("quit", "exit", "q"):
        return False
    if cmd in ("help", "h", "?"):
        print(HELP + "\n")
    elif cmd in ("clear", "c"):
        agent.reset()
        info("  history cleared\n")
    elif cmd == "model":
        if not rest:
            err("usage: /model <name>")
        else:
            args.gemini_model = rest
            try:
                new_backend = GeminiBackend(rest, temperature=args.temperature,
                                            top_p=args.top_p, max_tokens=args.max_tokens,
                                            retries=getattr(args, "cloud_retries", 2))
                agent.backend.close()
                agent.backend = new_backend
                agent.critic.backend = new_backend
                agent.observer.backend = new_backend
                agent.dreamer.backend = new_backend
                agent.advisor.backend = new_backend
                ok(f"switched to {new_backend.label}\n")
            except BackendError as e:
                err(str(e))
    elif cmd == "load":
        if not rest:
            err("usage: /load <path.litertlm>")
        else:
            try:
                new_backend = LiteRTBackend(rest, device=args.device,
                                            temperature=args.temperature,
                                            top_k=args.top_k, top_p=args.top_p,
                                            max_tokens=args.max_tokens,
                                            style=args.chat_template)
                agent.backend.close()
                agent.backend = new_backend
                agent.critic.backend = new_backend
                agent.observer.backend = new_backend
                agent.dreamer.backend = new_backend
                agent.advisor.backend = new_backend
                ok(f"switched to {new_backend.label}\n")
            except BackendError as e:
                err(str(e))
    elif cmd == "cloud":
        try:
            new_backend = GeminiBackend(args.gemini_model, temperature=args.temperature,
                                        top_p=args.top_p, max_tokens=args.max_tokens,
                                        retries=getattr(args, "cloud_retries", 2))
            agent.backend.close()
            agent.backend = new_backend
            agent.critic.backend = new_backend
            agent.observer.backend = new_backend
            agent.dreamer.backend = new_backend
            agent.advisor.backend = new_backend
            ok(f"switched to {new_backend.label}\n")
        except BackendError as e:
            err(str(e))
    elif cmd == "hybrid":
        # Rebuild with hybrid mode
        args.mode = "hybrid"
        try:
            new_backend = build_backends(args, registry, downloader, router, hf)
            agent.backend.close()
            agent.backend = new_backend
            agent.critic.backend = new_backend
            agent.observer.backend = new_backend
            agent.dreamer.backend = new_backend
            agent.advisor.backend = new_backend
            ok(f"hybrid mode enabled: {new_backend.label}\n")
        except BackendError as e:
            err(str(e))
    elif cmd == "auto":
        args.mode = "auto"
        try:
            new_backend = build_backends(args, registry, downloader, router, hf)
            agent.backend.close()
            agent.backend = new_backend
            agent.critic.backend = new_backend
            agent.observer.backend = new_backend
            agent.dreamer.backend = new_backend
            agent.advisor.backend = new_backend
            ok(f"auto mode enabled: {new_backend.label}\n")
        except BackendError as e:
            err(str(e))
    elif cmd == "local":
        args.mode = "local"
        try:
            new_backend = build_backends(args, registry, downloader, router, hf)
            agent.backend.close()
            agent.backend = new_backend
            agent.critic.backend = new_backend
            agent.observer.backend = new_backend
            agent.dreamer.backend = new_backend
            agent.advisor.backend = new_backend
            ok(f"local mode enabled: {new_backend.label}\n")
        except BackendError as e:
            err(str(e))
    elif cmd == "route":
        if not rest:
            err("usage: /route <text>")
        else:
            desc = router.describe(rest)
            info(f"  routing preview: {desc}\n")
    elif cmd == "diagnose":
        info("  running self-diagnosticâ¦\n")
        report = diagnostic.run()
        print(diagnostic.format_report(report) + "\n")
    elif cmd == "backup":
        dest = backup.backup("manual")
        if dest:
            ok(f"backed up to {dest}\n")
        else:
            warn("nothing to backup\n")
    elif cmd == "patterns":
        print(paint("  learned patterns:", C.BOLD))
        print(patterns.summary() + "\n")
    elif cmd == "models":
        print(paint("  â Cloud models:", C.BOLD))
        for m in registry.cloud.values():
            strengths = ", ".join(m.strengths[:3])
            print(f"    â¢ {paint(m.name, C.BCYAN)} â {m.display} ({strengths})")
        print(paint("\n  â¡ Local models:", C.BOLD))
        for m in registry.local.values():
            print(f"    â¢ {paint(m.name, C.BGREEN)} â {m.display} ({m.size})")
        print(paint("\n  ð Downloaded:", C.BOLD))
        for f in downloader.list_local_models():
            print(f"    â¢ {f}")
        print()
    elif cmd == "download":
        model_name = rest or "qwen3-0.6b"
        info(f"  ensuring model: {model_name}\n")
        path = downloader.ensure_model(model_name)
        if path:
            ok(f"model ready: {path}\n")
        else:
            err("could not download model\n")
    elif cmd == "system":
        agent.base_system = rest or agent.base_system
        info(f"  system â {agent.base_system[:70]}\n")
    elif cmd == "autonomy":
        try:
            lvl = max(0, min(5, int(rest)))
        except ValueError:
            err("usage: /autonomy <0..5>")
        else:
            args.autonomy = lvl
            agent.autonomy = lvl
            agent.critic.enabled = lvl >= 3 and args.self_critique
            agent.observer.enabled = lvl >= 3
            agent.advisor.enabled = lvl >= 4 and args.proactive
            info(f"  autonomy â {lvl}\n")
    elif cmd == "critique":
        if rest in ("on", "off"):
            args.self_critique = rest == "on"
            agent.critic.enabled = args.self_critique and agent.autonomy >= 3
            info(f"  self-critique â {rest}\n")
        else:
            err("usage: /critique on|off")
    elif cmd == "proactive":
        if rest in ("on", "off"):
            args.proactive = rest == "on"
            agent.advisor.enabled = args.proactive and agent.autonomy >= 4
            info(f"  proactive â {rest}\n")
        else:
            err("usage: /proactive on|off")
    elif cmd == "remember":
        if "=" not in rest:
            err("usage: /remember key=value")
        else:
            k, _, v = rest.partition("=")
            agent.memory.add_fact(k.strip(), v.strip(), source="user")
            ok(f"remembered: {k.strip()} = {v.strip()}\n")
    elif cmd == "forget":
        if not rest:
            err("usage: /forget <key>")
        else:
            n = agent.memory.forget(rest)
            info(f"  forgot {n} fact(s)\n")
    elif cmd == "memory":
        kind = rest or "all"
        m = agent.memory
        if kind in ("all", "facts"):
            print(paint("  facts:", C.BOLD))
            for f in m.facts[-20:]:
                src = f.get("source", "?")
                print(f"    â¢ {f['k']}: {f['v']}  {paint(f'[{src}]', C.DIM)}")
        if kind in ("all", "corrections"):
            print(paint("  corrections:", C.BOLD))
            for c in m.corrections[-10:]:
                print(f"    â¢ {c['wrong']} â {c['right']}")
        if kind in ("all", "prefs", "preferences"):
            print(paint("  preferences:", C.BOLD))
            for k, v in m.preferences.items():
                print(f"    â¢ {k} = {v}")
        if kind in ("all", "episodes"):
            print(paint(f"  episodes ({len(m.episodes)}):", C.BOLD))
            for e in m.episodes[-5:]:
                print(f"    Q: {e['q'][:60]}")
                print(f"    A: {e['a'][:100]}")
        print()
    elif cmd == "search":
        if not rest:
            err("usage: /search <query>")
        else:
            items = agent.memory.recall(rest, top_k=8)
            if not items:
                info("  (nothing relevant)\n")
            else:
                for it in items:
                    print("    â¢", json.dumps(it, default=str)[:160])
                print()
    elif cmd == "goal":
        if not rest:
            err("usage: /goal <text>")
        else:
            g = agent.goals.add(rest)
            ok(f"set goal [{g.id}]: {rest}\n")
    elif cmd == "goals":
        active = agent.goals.active()
        if not active:
            info("  (no active goals)\n")
        else:
            for g in active:
                print(f"  [{g.id}] {g.text}")
                for s in g.subgoals:
                    print(f"      - {s}")
            print()
    elif cmd == "complete":
        if not rest:
            err("usage: /complete <id>")
        elif not any(g.id == rest for g in agent.goals.goals):
            warn(f"no goal with id '{rest}' (see /goals)\n")
        else:
            agent.goals.complete(rest)
            ok(f"completed goal {rest}\n")
    elif cmd == "reflect":
        if not rest:
            err("usage: /reflect <text>")
        else:
            agent.journal.write(rest)
            ok("wrote to journal\n")
    elif cmd == "journal":
        n = 10
        try:
            n = int(rest) if rest else 10
        except ValueError:
            pass
        print(agent.journal.read(n) + "\n")
    elif cmd == "skill":
        parts = rest.split("|")
        if len(parts) < 2:
            err("usage: /skill <name>|<step1>|<step2>|...")
        else:
            name = parts[0].strip()
            steps = [s.strip() for s in parts[1:] if s.strip()]
            agent.skills.add(name, steps)
            ok(f"extracted skill: {name} ({len(steps)} steps)\n")
    elif cmd == "skills":
        if not agent.skills.skills:
            info("  (no skills extracted)\n")
        else:
            for s in agent.skills.skills:
                print(f"  â¢ {s['name']}:")
                for step in s["steps"][:5]:
                    print(f"      {step}")
            print()
    elif cmd == "forge":
        parts = rest.split(maxsplit=1)
        if len(parts) < 2:
            err("usage: /forge <name> <python_source>")
        else:
            name, source = parts[0], parts[1]
            if agent.forge.forge(name, source):
                ok(f"forged tool: {name}\n")
            else:
                err("tool contains forbidden constructs (import/exec/eval)")
    elif cmd == "dream":
        info("  dreamingâ¦\n")
        insights = agent.dream()
        print(paint(insights, C.BCYAN) + "\n")
    elif cmd == "hf-login":
        if not rest:
            err("usage: /hf-login <token>")
            info("  get a token at https://huggingface.co/settings/tokens")
        else:
            hf.login(rest)
    elif cmd == "hf-logout":
        hf.logout()
    elif cmd == "hf-status":
        if hf.is_logged_in():
            ok("logged in to Hugging Face\n")
        else:
            info("  â not logged in\n")
            info("  set HF_TOKEN env var or use /hf-login <token>")
    elif cmd == "tools":
        print(paint("  tools:", C.BOLD))
        for t in TOOL_SCHEMA:
            args_s = ", ".join(f"{k}: {v}" for k, v in t["args"].items())
            print(f"    â¢ {t['name']}({args_s}) â {t['desc']}")
        forged = agent.forge.list_tools()
        if forged:
            print(paint("  forged tools:", C.BOLD))
            for t in forged:
                print(f"    â¢ {t}")
        print()
    elif cmd == "save":
        _export_transcript(agent, Path(rest or "transcript.md"))
    elif cmd == "stats":
        print(paint(f"  backend    : {agent.backend.label}\n"
                    f"  mode       : {args.mode}\n"
                    f"  autonomy   : {agent.autonomy}\n"
                    f"  critique   : {agent.critic.enabled}\n"
                    f"  proactive  : {agent.advisor.enabled}\n"
                    f"  hf         : {'logged in' if hf.is_logged_in() else 'not logged in'}\n"
                    f"  messages   : {len(agent.history)}\n"
                    f"  facts      : {len(agent.memory.facts)}\n"
                    f"  corrections: {len(agent.memory.corrections)}\n"
                    f"  entities   : {len(agent.graph.entities)}\n"
                    f"  relations  : {len(agent.graph.relations)}\n"
                    f"  goals      : {len(agent.goals.active())} active / {len(agent.goals.goals)} total\n"
                    f"  skills     : {len(agent.skills.skills)}\n"
                    f"  episodes   : {len(agent.memory.episodes)}\n"
                    f"  forged     : {len(agent.forge.list_tools())}\n"
                    f"  patterns   : {patterns.total_prompts} prompts learned\n"
                    f"  meta       : {len(agent.meta.strategies)} problem types\n", C.GREY))
    elif cmd == "export":
        _export_transcript(agent, Path(rest or "transcript.md"))
    elif cmd == "settings":
        s = getattr(agent, "settings", None)
        if s is None:
            err("settings not available")
        else:
            print(paint("  settings:", C.BOLD))
            for k in sorted(s.data):
                live = paint("*", C.BGREEN) if k in SettingsManager.LIVE_KEYS else " "
                print(f"   {live} {k} = {s.data[k]}")
            print(paint("  (* = live-changeable via /set; others apply on restart)",
                        C.DIM) + "\n")
    elif cmd == "set":
        s = getattr(agent, "settings", None)
        if s is None:
            err("settings not available")
        elif " " not in rest:
            err("usage: /set <key> <value>  (see /settings)")
        else:
            key, _, value = rest.partition(" ")
            if s.set(key, value):
                _apply_live_setting(agent, args, s, key)
                ok(f"{key} = {s.get(key)}"
                   + ("" if key in SettingsManager.LIVE_KEYS
                      else "  (applies on restart)") + "\n")
            else:
                err(f"unknown/invalid setting '{key}' â see /settings")
    elif cmd == "usage":
        st = getattr(agent, "stats", None)
        if st is None:
            err("usage stats not available")
        else:
            print(paint("  usage:", C.BOLD))
            print("  " + st.summary().replace("\n", "\n  ") + "\n")
    elif cmd in ("save-session", "session-save"):
        sm = getattr(agent, "session_mgr", None)
        if sm is None:
            err("sessions not available")
        else:
            name = rest or "session_" + time.strftime("%Y%m%d_%H%M%S")
            p = sm.save(name, agent.history)
            ok(f"session saved â {p.name} ({len(agent.history)} messages)\n")
    elif cmd in ("load-session", "session-load"):
        sm = getattr(agent, "session_mgr", None)
        if sm is None or not rest:
            err("usage: /load-session <name> (see /sessions)")
        else:
            hist = sm.load(rest)
            if not hist:
                err(f"no session named '{rest}'")
            else:
                agent.history = hist
                ok(f"loaded {len(hist)} messages from '{rest}'\n")
    elif cmd == "sessions":
        sm = getattr(agent, "session_mgr", None)
        if sm is None:
            err("sessions not available")
        else:
            names = sm.list_sessions()
            if not names:
                info("  (no saved sessions)\n")
            else:
                for n2 in names:
                    print(f"    â¢ {n2}")
                print()
    elif cmd in ("env-set", "env_set"):
        if env_mgr is None:
            err("env manager not available")
        elif " " not in rest:
            err("usage: /env-set <KEY> <value>")
        else:
            key, _, value = rest.partition(" ")
            if env_mgr.set(key.strip(), value.strip()):
                ok(f"set {key.strip()}={EnvManager.mask(key.strip(), value.strip())}\n")
            else:
                err("invalid key name (use A-Z_0-9, starting with a letter)")
    elif cmd in ("env-get", "env_get"):
        if env_mgr is None:
            err("env manager not available")
        elif not rest:
            err("usage: /env-get <KEY>")
        else:
            info(f"  {rest}={EnvManager.mask(rest, env_mgr.get(rest))}\n")
    elif cmd in ("env-unset", "env_unset"):
        if env_mgr is None:
            err("env manager not available")
        elif not rest:
            err("usage: /env-unset <KEY>")
        else:
            existed = env_mgr.unset(rest)
            info(f"  {'unset ' + rest if existed else f'(was not set: {rest})'}\n")
    elif cmd in ("env-save", "env_save"):
        if env_mgr is None:
            err("env manager not available")
        else:
            p = env_mgr.save()
            if p:
                ok(f"saved env → {p}\n")
            else:
                err("could not save .env")
    elif cmd == "env":
        if env_mgr is None:
            err("env manager not available")
        else:
            print(paint(f"  env file: {env_mgr.status()}", C.BOLD))
            print(env_mgr.summary(rest) + "\n")
    elif cmd == "history":
        n = 10
        try:
            n = int(rest) if rest else 10
        except ValueError:
            pass
        msgs = agent.history[-n:]
        if not msgs:
            info("  (no history)\n")
        else:
            for m in msgs:
                print(f"  {paint(m.role, C.CYAN)}: {m.text[:120]}")
            print()
    elif cmd == "sysinfo":
        print(paint(agent.tools._sys_info(), C.GREY) + "\n")
    elif cmd == "debug":
        if rest in ("on", "off"):
            s = getattr(agent, "settings", None)
            if s is not None and s.set("debug", rest):
                _apply_live_setting(agent, args, s, "debug")
            else:
                if rest == "on":
                    os.environ["TERMINAL_AI_DEBUG"] = "1"
                else:
                    os.environ.pop("TERMINAL_AI_DEBUG", None)
            info(f"  debug → {rest}\n")
        else:
            err("usage: /debug on|off")
    elif cmd == "reset":
        warn("this wipes memory, graph, goals, skills, patterns and journal")
        ans = input(paint("  â  type RESET to confirm: ", C.BYELLOW)).strip()
        if ans != "RESET":
            info("  cancelled\n")
        else:
            backup.backup("pre-reset")
            for f in (MEMORY_FILE, GRAPH_FILE, GOALS_FILE, JOURNAL_FILE,
                      SKILLS_FILE, META_FILE, PATTERNS_FILE):
                try:
                    f.unlink()
                except OSError:
                    pass
            ok("factory reset done (backup saved). Restart to reload.\n")
    else:
        err(f"unknown command /{cmd} â try /help")
    return True


def repl(agent: Agent, args: argparse.Namespace, hf: HFManager,
         registry: ModelRegistry, downloader: AutoDownloader,
         router: TaskRouter, diagnostic: SelfDiagnostic,
         backup: AutoBackup, patterns: PatternLearner,
         env_mgr: Optional[EnvManager] = None) -> None:
    banner(agent, args, hf, registry, patterns, env_mgr)
    while True:
        try:
            line = input(paint("â¯ ", C.BOLD + C.BCYAN)).strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print(paint("^C", C.GREY))
            continue
        if not line:
            continue
        if line.startswith("/"):
            if not handle_cmd(line, agent, args, hf, registry, downloader,
                              router, diagnostic, backup, patterns, env_mgr):
                break
        else:
            agent.turn(line)
    # autosave the last conversation so --resume last / /load-session last works
    if getattr(agent, "session_mgr", None) is not None and agent.history:
        try:
            agent.session_mgr.save("last", agent.history)
        except Exception:
            pass
    agent.backend.close()
    print(paint("  â¦ bye", C.DIM))


def main(argv: Optional[list[str]] = None) -> int:
    settings = SettingsManager()
    ap = argparse.ArgumentParser(
        prog="terminal_ai.py",
        description="Hybrid self-evolving terminal AI: Gemini â + LiteRT-LM â¡ + HF ð¤")
    ap.add_argument("--no-settings", action="store_true",
                    help="ignore saved settings.json for this run")
    ap.add_argument("--mode", choices=["auto", "cloud", "local", "hybrid"],
                    default=settings.get("mode"),
                    help="auto=task-based routing (default), cloud=Gemini only, "
                         "local=LiteRT only, hybrid=cloud+local fallback")
    ap.add_argument("--gemini-model", default=settings.get("gemini_model"),
                    help="Gemini model ID (e.g., gemini-3.8-flash, gemini-3.1-pro)")
    ap.add_argument("-m", "--model-path", help="local .litertlm 1B model")
    ap.add_argument("--auto-download", action="store_true",
                    help="auto-download local model from HF if missing")
    ap.add_argument("--hf-repo", help="Hugging Face repo (e.g. litert-community/Qwen3-0.6B)")
    ap.add_argument("--hf-file", help="filename in HF repo")
    ap.add_argument("--hf-token", help="Hugging Face token")
    ap.add_argument("--device", default="cpu", choices=["cpu", "gpu", "npu"])
    ap.add_argument("--temperature", type=float, default=settings.get("temperature"))
    ap.add_argument("--top-p", type=float, default=settings.get("top_p"))
    ap.add_argument("--top-k", type=int, default=settings.get("top_k"))
    ap.add_argument("--max-tokens", type=int, default=settings.get("max_tokens"))
    ap.add_argument("--system", default=settings.get("system"))
    ap.add_argument("--chat-template", default=settings.get("chat_template"),
                    choices=["gemma", "chatml", "raw"])
    ap.add_argument("--max-ctx-chars", type=int, default=settings.get("max_ctx_chars"))
    ap.add_argument("--autonomy", type=int, default=settings.get("autonomy"),
                    choices=[0, 1, 2, 3, 4, 5],
                    help="0=chat 1=tools 2=+retry 3=+critique+observer 4=+goals+skills 5=+forge+dream")
    ap.add_argument("--self-critique", action="store_true")
    ap.add_argument("--proactive", action="store_true")
    ap.add_argument("--workspace", default=".", help="working dir for shell/file tools")
    ap.add_argument("--no-confirm-shell", action="store_true")
    ap.add_argument("--shell-timeout", type=int, default=None,
                    help="timeout for the shell tool, seconds (default 30)")
    ap.add_argument("--auto-backup-every", type=int, default=None,
                    help="auto-backup memory every N turns (0=off)")
    ap.add_argument("--cloud-retries", type=int, default=None,
                    help="cloud stream retries with backoff (default 2)")
    ap.add_argument("--resume", help="resume a saved session (see /sessions)")
    ap.add_argument("--env-file", default=None,
                    help="path to a .env file to load (default: workspace/.env)")
    ap.add_argument("--diagnose", action="store_true",
                    help="run self-diagnostic and exit")
    ap.add_argument("-p", "--prompt", help="one-shot prompt, then exit")
    ap.add_argument("-V", "--version", action="version", version=f"terminal-ai {__version__}")
    args = ap.parse_args(argv)

    if args.no_settings:
        settings = SettingsManager.blank()

    # merge persisted settings with CLI flags (flags win)
    args.self_critique = args.self_critique or bool(settings.get("self_critique"))
    args.proactive = args.proactive or bool(settings.get("proactive"))
    args.confirm_shell = (not args.no_confirm_shell) and bool(settings.get("confirm_shell"))
    args.shell_timeout = (args.shell_timeout if args.shell_timeout is not None
                          else int(settings.get("shell_timeout")))
    args.auto_backup_every = (args.auto_backup_every if args.auto_backup_every is not None
                              else int(settings.get("auto_backup_every")))
    args.cloud_retries = (args.cloud_retries if args.cloud_retries is not None
                          else int(settings.get("cloud_retries")))

    # Initialize core systems
    registry = ModelRegistry()
    downloader = AutoDownloader(registry)
    router = TaskRouter(registry)
    hf = HFManager()
    diagnostic = SelfDiagnostic(registry, downloader)
    backup = AutoBackup()
    patterns = PatternLearner.load()
    stats = StatsTracker()
    session_mgr = SessionManager()

    # v4.2: .env file support (autoload into os.environ unless disabled)
    env_mgr = EnvManager(env_file=Path(args.env_file) if args.env_file else None,
                         workspace=Path(args.workspace).resolve())
    if bool(settings.get("env_autoload")):
        n_env = env_mgr.load(apply=True)
        if n_env:
            ok(f"loaded {n_env} env var(s) from {env_mgr.path}")

    if args.diagnose:
        info("  running self-diagnosticâ¦\n")
        report = diagnostic.run()
        print(diagnostic.format_report(report) + "\n")
        return 0

    if args.hf_token:
        hf.login(args.hf_token)

    try:
        backend = build_backends(args, registry, downloader, router, hf)
    except BackendError as e:
        err(str(e))
        return 1

    memory = Memory.load()
    graph = KnowledgeGraph.load()
    goals = GoalPlanner.load()
    journal = Journal()
    skills = SkillLibrary.load()
    meta = MetaLearner.load()
    forge = ToolForge()
    dreamer = Dreamer(backend, memory, journal)
    tools = ToolRegistry(memory, graph, goals, journal, skills, forge,
                         Path(args.workspace).resolve(),
                         confirm_shell=args.confirm_shell,
                         shell_timeout=args.shell_timeout,
                         dreamer=dreamer, env=env_mgr,
                         ask_delete=bool(settings.get("ask_delete")))
    agent = Agent(backend, memory, graph, goals, journal, skills, meta, tools, forge,
                  router, patterns, args.system, autonomy=args.autonomy,
                  self_critique=args.self_critique, proactive=args.proactive,
                  max_ctx_chars=args.max_ctx_chars,
                  stats=stats, settings=settings, session_mgr=session_mgr,
                  backup=backup, auto_backup_every=args.auto_backup_every)

    if args.resume:
        hist = session_mgr.load(args.resume)
        if hist:
            agent.history = hist
            ok(f"resumed session '{args.resume}' ({len(hist)} messages)")
        else:
            warn(f"no session named '{args.resume}'")

    if args.prompt:
        try:
            agent.turn(args.prompt)
        finally:
            backend.close()
        return 0
    repl(agent, args, hf, registry, downloader, router, diagnostic, backup,
         patterns, env_mgr)
    return 0


if __name__ == "__main__":
    print(
        "The terminal interface has been replaced by the Litestar web app.\n"
        "Install dependencies, then run: litestar --app app:app run "
        "--host 127.0.0.1 --port 8000"
    )
    raise SystemExit(2)

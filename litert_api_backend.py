"""Direct adapter for the official LiteRT-LM Python API.

Uses litert_lm.Engine and Engine.create_conversation; it does not invoke the CLI
or guess legacy package/module names. The engine is created per request so
resources are deterministically closed after generation.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import terminal_ai as core


class LiteRTPythonBackend(core.Backend):
    label = "LiteRT-LM Python API"
    supports_tools = False

    def __init__(self, model_path: str | Path, max_output_tokens: int = 1024):
        self.model_path = Path(model_path).expanduser().resolve()
        if not self.model_path.is_file() or self.model_path.suffix.lower() != ".litertlm":
            raise core.BackendError(f"Expected an existing .litertlm model file: {self.model_path}")
        try:
            import litert_lm  # official package exported by litert-lm-api
        except ImportError as exc:
            raise core.BackendError(
                "LiteRT-LM Python API is not installed. Install with: "
                "python -m pip install litert-lm-api"
            ) from exc
        self._litert_lm = litert_lm
        self.max_output_tokens = max(32, min(int(max_output_tokens), 8192))

    @staticmethod
    def _message(role: str, text: str) -> dict[str, str]:
        role = role if role in {"user", "assistant"} else "user"
        return {"role": role, "content": text}

    @staticmethod
    def _chunk_text(chunk: Any) -> str:
        if isinstance(chunk, str):
            return chunk
        if not isinstance(chunk, dict):
            return ""
        content = chunk.get("content", [])
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "".join(parts)
        return ""

    def stream(self, system: str, history: list[core.Msg],
               tools: list[dict] | None = None) -> Iterator[str]:
        # The app intentionally does not pass executable agent tools to local inference.
        del tools
        lm = self._litert_lm
        messages = [
            self._message(item.role, item.text)
            for item in history[:-1]
            if item.role in {"user", "assistant"} and item.text
        ]
        latest_user_message = next(
            (item.text for item in reversed(history) if item.role == "user" and item.text),
            "",
        )
        try:
            with lm.Engine(str(self.model_path), backend=lm.Backend.CPU()) as engine:
                with engine.create_conversation(
                    messages=messages or None,
                    system_message=system or None,
                    max_output_tokens=self.max_output_tokens,
                ) as conversation:
                    for chunk in conversation.send_message_async(latest_user_message):
                        text = self._chunk_text(chunk)
                        if text:
                            yield text
        except Exception as exc:
            raise core.BackendError(f"LiteRT-LM Python API inference failed: {exc}") from exc

    def close(self) -> None:
        # Engine and Conversation lifetimes are scoped to stream() and closed there.
        return None

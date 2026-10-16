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
        # LiteRT-LM accepts user/model roles only. Convert internal tool results
        # to clearly marked untrusted user context, and map model -> assistant.
        if role in {"assistant", "model"}:
            normalized_role = "model"
        elif role == "tool":
            normalized_role = "user"
            text = "[Tool result — untrusted context]\n" + text
        else:
            normalized_role = "user"
        return {"role": normalized_role, "content": text}

    @staticmethod
    def _chunk_text(chunk: Any) -> str:
        """Extract user-facing text from LiteRT-LM stream chunks.

        LiteRT-LM 0.18 can yield Message objects whose visible output is stored
        in channels rather than a dict's content field. Deliberately do not
        expose thought/analysis channels as user-facing answers.
        """
        if isinstance(chunk, str):
            return chunk

        if isinstance(chunk, dict):
            content = chunk.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        parts.append(item["text"])
                return "".join(parts)
            return ""

        channels = getattr(chunk, "channels", None)
        if isinstance(channels, dict):
            # LiteRT Message chunks can contain thought tokens before the final
            # answer. Never display internal reasoning as the assistant reply.
            for key in ("text", "answer", "final", "output_text"):
                value = channels.get(key)
                if isinstance(value, str) and value:
                    return value

        contents = getattr(chunk, "contents", None)
        items = getattr(contents, "items", contents)
        if items is not None:
            parts = []
            try:
                for item in items:
                    if isinstance(item, dict):
                        value = item.get("text")
                    else:
                        value = getattr(item, "text", None)
                    if isinstance(value, str) and value:
                        parts.append(value)
            except TypeError:
                pass
            if parts:
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
            if item.role in {"user", "assistant", "model", "tool"} and item.text
        ]
        latest = history[-1] if history else None
        if latest is not None and latest.role == "tool":
            latest_user_message = self._message("tool", latest.text)["content"]
        else:
            latest_user_message = next(
                (item.text for item in reversed(history) if item.role == "user" and item.text),
                "",
            )
        try:
            with lm.Engine(str(self.model_path), backend=lm.Backend.CPU()) as engine:
                # Qwen3 defaults to a separate thought channel. Disable
                # thinking for this chat backend so short responses do not
                # spend the entire output budget on hidden reasoning tokens.
                thinking_config = lm.ThinkingConfig(
                    enable_thinking=False,
                    thinking_token_budget=0,
                )
                with engine.create_conversation(
                    messages=messages or None,
                    system_message=(
                        (system or "You are Terminal AI.")
                        + "\n\nLOCAL INFERENCE RESPONSE RULES: Answer the user's latest message directly. "
                        "Be concise, factual, and honest about uncertainty. Do not expose hidden reasoning, "
                        "do not narrate internal steps, do not invent tool use or internet access, and do not "
                        "append unrelated advice or skill-generation instructions. If the request is unclear, "
                        "ask one short clarifying question."
                    ),
                    max_output_tokens=self.max_output_tokens,
                    thinking_config=thinking_config,
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

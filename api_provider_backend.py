"""OpenAI-compatible and Anthropic API adapters for Terminal AI.

API keys are read from environment variables; this module never stores or logs them.
Streaming uses server-sent events and yields only generated text.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

import terminal_ai as core


PROVIDERS: dict[str, dict[str, str]] = {
    "openai": {"label": "OpenAI", "env": "OPENAI_API_KEY", "base_url": "https://api.openai.com/v1", "model_env": "TERMINAL_AI_OPENAI_MODEL", "default_model": "gpt-4.1-mini", "protocol": "openai"},
    "openrouter": {"label": "OpenRouter", "env": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1", "model_env": "TERMINAL_AI_OPENROUTER_MODEL", "default_model": "openai/gpt-4.1-mini", "protocol": "openai"},
    "groq": {"label": "Groq", "env": "GROQ_API_KEY", "base_url": "https://api.groq.com/openai/v1", "model_env": "TERMINAL_AI_GROQ_MODEL", "default_model": "llama-3.3-70b-versatile", "protocol": "openai"},
    "deepseek": {"label": "DeepSeek", "env": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com/v1", "model_env": "TERMINAL_AI_DEEPSEEK_MODEL", "default_model": "deepseek-chat", "protocol": "openai"},
    "together": {"label": "Together AI", "env": "TOGETHER_API_KEY", "base_url": "https://api.together.xyz/v1", "model_env": "TERMINAL_AI_TOGETHER_MODEL", "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "protocol": "openai"},
    "mistral": {"label": "Mistral AI", "env": "MISTRAL_API_KEY", "base_url": "https://api.mistral.ai/v1", "model_env": "TERMINAL_AI_MISTRAL_MODEL", "default_model": "mistral-small-latest", "protocol": "openai"},
    "xai": {"label": "xAI", "env": "XAI_API_KEY", "base_url": "https://api.x.ai/v1", "model_env": "TERMINAL_AI_XAI_MODEL", "default_model": "grok-3-mini", "protocol": "openai"},
    "fireworks": {"label": "Fireworks AI", "env": "FIREWORKS_API_KEY", "base_url": "https://api.fireworks.ai/inference/v1", "model_env": "TERMINAL_AI_FIREWORKS_MODEL", "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct", "protocol": "openai"},
    "cerebras": {"label": "Cerebras", "env": "CEREBRAS_API_KEY", "base_url": "https://api.cerebras.ai/v1", "model_env": "TERMINAL_AI_CEREBRAS_MODEL", "default_model": "llama-3.3-70b", "protocol": "openai"},
    "anthropic": {"label": "Anthropic Claude", "env": "ANTHROPIC_API_KEY", "base_url": "https://api.anthropic.com/v1", "model_env": "TERMINAL_AI_ANTHROPIC_MODEL", "default_model": "claude-3-7-sonnet-latest", "protocol": "anthropic"},
    "custom-openai": {"label": "Custom OpenAI-compatible endpoint", "env": "TERMINAL_AI_CUSTOM_API_KEY", "base_url": "", "model_env": "TERMINAL_AI_CUSTOM_MODEL", "default_model": "", "protocol": "openai"},
}


class APIProviderBackend(core.Backend):
    supports_tools = False

    def __init__(self, provider_id: str, api_key: str, model: str | None = None,
                 base_url: str | None = None, timeout: int = 90):
        if provider_id not in PROVIDERS:
            raise core.BackendError(f"Unsupported API provider: {provider_id}")
        self.provider_id = provider_id
        self.config = PROVIDERS[provider_id]
        self.api_key = (api_key or "").strip()
        if not self.api_key:
            raise core.BackendError(f"Missing API key for {self.config['label']}; configure it in Settings.")
        self.model = (model or os.environ.get(self.config["model_env"]) or self.config["default_model"]).strip()
        self.base_url = (base_url or os.environ.get("TERMINAL_AI_CUSTOM_BASE_URL") or self.config["base_url"]).rstrip("/")
        if not self.base_url or not self.model:
            raise core.BackendError("Custom API provider requires both a base URL and model ID.")
        self.timeout = max(10, min(int(timeout), 300))
        self.label = f"{self.config['label']} · {self.model}"

    def _request(self, payload: dict[str, Any], system: str,
                 history: list[core.Msg]) -> tuple[str, bytes]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend({"role": m.role, "content": m.text}
                        for m in history if m.role in {"user", "assistant"} and m.text)
        if self.config["protocol"] == "anthropic":
            url = self.base_url + "/messages"
            body = {"model": self.model, "max_tokens": 2048, "stream": True, "messages":
                    [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]}
            if system:
                body["system"] = system
            headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                       "content-type": "application/json"}
        else:
            url = self.base_url + "/chat/completions"
            body = {"model": self.model, "messages": messages, "stream": True,
                    "temperature": 0.7}
            headers = {"Authorization": "Bearer " + self.api_key, "content-type": "application/json"}
            if self.provider_id == "openrouter":
                headers["HTTP-Referer"] = "http://localhost"
                headers["X-Title"] = "Terminal AI"
        request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                         headers=headers, method="POST")
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
            return "ok", response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read(3000).decode("utf-8", "replace")
            raise core.BackendError(f"{self.config['label']} API returned HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            raise core.BackendError(f"{self.config['label']} API request failed: {exc}") from exc

    def stream(self, system: str, history: list[core.Msg],
               tools: list[dict] | None = None) -> Iterator[str]:
        del tools
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend({"role": m.role, "content": m.text}
                        for m in history if m.role in {"user", "assistant"} and m.text)
        if not messages:
            return
        if self.config["protocol"] == "anthropic":
            body = {"model": self.model, "max_tokens": 2048, "stream": True,
                    "messages": [m for m in messages if m["role"] != "system"]}
            if system:
                body["system"] = system
            url = self.base_url + "/messages"
            headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                       "content-type": "application/json"}
        else:
            body = {"model": self.model, "messages": messages, "stream": True, "temperature": 0.7}
            url = self.base_url + "/chat/completions"
            headers = {"Authorization": "Bearer " + self.api_key, "content-type": "application/json"}
            if self.provider_id == "openrouter":
                headers["HTTP-Referer"] = "http://localhost"
                headers["X-Title"] = "Terminal AI"
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                for raw in response:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if self.config["protocol"] == "anthropic":
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta" and delta.get("text"):
                                yield delta["text"]
                    else:
                        choices = event.get("choices") or []
                        if choices:
                            text = (choices[0].get("delta") or {}).get("content")
                            if isinstance(text, str) and text:
                                yield text
        except urllib.error.HTTPError as exc:
            detail = exc.read(3000).decode("utf-8", "replace")
            raise core.BackendError(f"{self.config['label']} API returned HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            if isinstance(exc, core.BackendError):
                raise
            raise core.BackendError(f"{self.config['label']} API request failed: {exc}") from exc

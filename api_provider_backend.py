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
from application.settings_validation import SettingsValidationError, validate_custom_base_url


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
    "custom-openai": {"label": "Custom OpenAI-compatible endpoint", "env": "TERMINAL_AI_CUSTOM_API_KEY", "base_url": "", "model_env": "TERMINAL_AI_CUSTOM_MODEL", "default_model": "", "protocol": "openai", "endpoint_configurable": "true"},
    "ollama": {"label": "Ollama (local)", "env": "OLLAMA_API_KEY", "base_url": "http://localhost:11434/v1", "model_env": "TERMINAL_AI_OLLAMA_MODEL", "default_model": "", "protocol": "openai", "auth": "none", "endpoint_configurable": "true", "requires_network": "false"},
    "lm-studio": {"label": "LM Studio (local)", "env": "LM_STUDIO_API_KEY", "base_url": "http://localhost:1234/v1", "model_env": "TERMINAL_AI_LM_STUDIO_MODEL", "default_model": "", "protocol": "openai", "auth": "none", "endpoint_configurable": "true", "requires_network": "false"},
    "vllm": {"label": "vLLM / local OpenAI-compatible server", "env": "VLLM_API_KEY", "base_url": "http://localhost:8000/v1", "model_env": "TERMINAL_AI_VLLM_MODEL", "default_model": "", "protocol": "openai", "auth": "none", "endpoint_configurable": "true", "requires_network": "false"},
}


class APIProviderBackend(core.Backend):
    supports_tools = False

    def __init__(self, provider_id: str, api_key: str, model: str | None = None,
                 base_url: str | None = None, timeout: int = 90,
                 temperature: float = 0.7, top_p: float = 0.95,
                 max_tokens: int = 2048):
        if provider_id not in PROVIDERS:
            raise core.BackendError(f"Unsupported API provider: {provider_id}")
        self.provider_id = provider_id
        self.config = PROVIDERS[provider_id]
        self.api_key = (api_key or "").strip()
        if not self.api_key and self.config.get("auth") != "none":
            raise core.BackendError(f"Missing API key for {self.config['label']}; configure it in Settings.")
        self.model = (model or os.environ.get(self.config["model_env"]) or self.config["default_model"]).strip()
        configured_base_url = (
            base_url
            or os.environ.get("TERMINAL_AI_CUSTOM_BASE_URL") if provider_id == "custom-openai"
            else base_url or self.config["base_url"]
        )
        if self.config.get("endpoint_configurable") == "true":
            try:
                configured_base_url = validate_custom_base_url(configured_base_url)
            except SettingsValidationError as exc:
                raise core.BackendError(str(exc)) from exc
        self.base_url = configured_base_url.rstrip("/")
        if not self.base_url or not self.model:
            raise core.BackendError("Custom API provider requires both a base URL and model ID.")
        self.timeout = max(5, min(int(timeout), 180))
        self.temperature = max(0.0, min(2.0, float(temperature)))
        self.top_p = max(0.0, min(1.0, float(top_p)))
        self.max_tokens = max(64, min(32768, int(max_tokens)))
        self.label = f"{self.config['label']} · {self.model}"

    @staticmethod
    def _history_messages(history: list[core.Msg]) -> list[dict[str, str]]:
        """Normalize internal roles to API chat roles and preserve tool results."""
        messages: list[dict[str, str]] = []
        for item in history:
            if not item.text:
                continue
            if item.role in {"user", "assistant"}:
                messages.append({"role": item.role, "content": item.text})
            elif item.role == "model":
                messages.append({"role": "assistant", "content": item.text})
            elif item.role == "tool":
                messages.append({"role": "user", "content": "[Tool result — untrusted context]\n" + item.text})
        return messages
    def _request(self, payload: dict[str, Any], system: str,
                 history: list[core.Msg]) -> tuple[str, bytes]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(self._history_messages(history))
        if self.config["protocol"] == "anthropic":
            url = self.base_url + "/messages"
            body = {"model": self.model, "max_tokens": self.max_tokens, "temperature": self.temperature, "stream": True, "messages":
                    [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]}
            if system:
                body["system"] = system
            headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                       "content-type": "application/json"}
        else:
            url = self.base_url + "/chat/completions"
            body = {"model": self.model, "messages": messages, "stream": True,
                    "temperature": self.temperature, "top_p": self.top_p,
                    "max_tokens": self.max_tokens}
            headers = {"content-type": "application/json"}
            if self.api_key:
                headers["Authorization"] = "Bearer " + self.api_key
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
        messages.extend(self._history_messages(history))
        if not messages:
            return
        if self.config["protocol"] == "anthropic":
            body = {"model": self.model, "max_tokens": self.max_tokens, "stream": True,
                    "messages": [m for m in messages if m["role"] != "system"]}
            if system:
                body["system"] = system
            url = self.base_url + "/messages"
            headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                       "content-type": "application/json"}
        else:
            body = {"model": self.model, "messages": messages, "stream": True,
                    "temperature": self.temperature, "top_p": self.top_p,
                    "max_tokens": self.max_tokens}
            url = self.base_url + "/chat/completions"
            headers = {"content-type": "application/json"}
            if self.api_key:
                headers["Authorization"] = "Bearer " + self.api_key
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

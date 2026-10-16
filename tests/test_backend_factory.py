from __future__ import annotations

import logging

import api_provider_backend
import terminal_ai as core
from application.backend_factory import build_cloud_backends


class FakeAPIBackend:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.label = kwargs["provider_id"]


class FakeGeminiBackend:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.label = "gemini"


def test_cloud_factory_uses_selected_provider_first_and_skips_missing_keys(monkeypatch):
    providers = {
        "openai": {
            "label": "OpenAI", "env": "OPENAI_API_KEY", "base_url": "https://api.example/v1",
            "model_env": "OPENAI_MODEL", "default_model": "default-openai", "protocol": "openai",
        },
        "custom-openai": {
            "label": "Custom", "env": "CUSTOM_KEY", "base_url": "",
            "model_env": "CUSTOM_MODEL", "default_model": "", "protocol": "openai",
        },
        "anthropic": {
            "label": "Anthropic", "env": "ANTHROPIC_API_KEY", "base_url": "https://anthropic.example/v1",
            "model_env": "ANTHROPIC_MODEL", "default_model": "default-anthropic", "protocol": "anthropic",
        },
    }
    monkeypatch.setattr(api_provider_backend, "PROVIDERS", providers)
    monkeypatch.setattr(api_provider_backend, "APIProviderBackend", FakeAPIBackend)
    monkeypatch.setattr(core, "GeminiBackend", FakeGeminiBackend)
    built = build_cloud_backends(
        {"mode": "auto", "active_provider": "openai", "provider_model": "selected-model",
         "custom_base_url": "https://custom.example/v1"},
        gemini_key=lambda: "gemini-key",
        environ={"OPENAI_API_KEY": "open-key", "CUSTOM_KEY": "custom-key",
                 "TERMINAL_AI_GEMINI_MODEL": "gemini-default"},
    )

    assert [item.label for item in built] == ["openai", "gemini", "custom-openai"]
    assert built[0].kwargs["model"] == "selected-model"
    assert built[1].kwargs["model"] == "gemini-default"
    assert built[2].kwargs["base_url"] == "https://custom.example/v1"
    assert all(item.label != "anthropic" for item in built)


def test_cloud_factory_skips_when_mode_does_not_allow_cloud(monkeypatch):
    monkeypatch.setattr(core, "GeminiBackend", lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not initialize")))
    built = build_cloud_backends(
        {"mode": "local", "active_provider": "gemini"},
        gemini_key=lambda: "unused",
        environ={},
    )
    assert built == []


def test_cloud_factory_does_not_log_provider_exception_details(monkeypatch, caplog):
    monkeypatch.setattr(
        api_provider_backend, "PROVIDERS",
        {"openai": {"label": "OpenAI", "env": "OPENAI_API_KEY", "base_url": "https://api.example/v1",
                    "model_env": "OPENAI_MODEL", "default_model": "default", "protocol": "openai"}},
    )

    class BrokenBackend:
        def __init__(self, **kwargs):
            raise RuntimeError("private-test-secret must not be logged")

    monkeypatch.setattr(api_provider_backend, "APIProviderBackend", BrokenBackend)
    with caplog.at_level(logging.WARNING):
        built = build_cloud_backends(
            {"mode": "cloud", "active_provider": "openai"},
            gemini_key=lambda: None,
            environ={"OPENAI_API_KEY": "test-key"},
        )
    assert built == []
    assert "RuntimeError" in caplog.text
    assert "private-test-secret" not in caplog.text

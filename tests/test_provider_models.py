from __future__ import annotations

import io
import json
import urllib.error

import pytest

from application.provider_models import ModelDiscoveryError, fetch_provider_models


class FakeResponse:
    def __init__(self, payload: dict):
        self.raw = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        return self.raw[:size]


def test_openai_compatible_model_list_returns_ids_and_default(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        return FakeResponse({"data": [{"id": "z-model"}, {"id": "a-model"}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = fetch_provider_models(
        "openai", api_key="test-key",
        environ={"OPENAI_API_KEY": "", "TERMINAL_AI_OPENAI_MODEL": "a-model"},
    )
    assert captured["url"] == "https://api.openai.com/v1/models"
    assert captured["authorization"] == "Bearer test-key"
    assert [item["id"] for item in result["models"]] == ["a-model", "z-model"]
    assert result["default_model"] == "a-model"


def test_gemini_model_list_filters_non_generation_models(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["api_key"] = request.get_header("X-goog-api-key")
        return FakeResponse({"models": [
            {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]},
        ]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = fetch_provider_models("gemini", api_key="gemini-test", environ={})
    assert captured["api_key"] == "gemini-test"
    assert [item["id"] for item in result["models"]] == ["gemini-2.0-flash"]


def test_model_discovery_requires_credentials():
    with pytest.raises(ModelDiscoveryError, match="API key"):
        fetch_provider_models("openai", environ={"OPENAI_API_KEY": ""})


def test_custom_endpoint_uses_validation_and_model_list(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse({"data": [{"id": "local-model"}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = fetch_provider_models(
        "custom-openai", api_key="custom-test",
        base_url="http://localhost:8000/v1", environ={"TERMINAL_AI_CUSTOM_API_KEY": ""},
    )
    assert captured["url"] == "http://localhost:8000/v1/models"
    assert result["default_model"] == "local-model"


def test_custom_endpoint_rejects_non_loopback_http():
    with pytest.raises(ModelDiscoveryError, match="Plain HTTP"):
        fetch_provider_models(
            "custom-openai", api_key="test",
            base_url="http://example.com/v1", environ={},
        )


def test_provider_http_error_does_not_expose_response_body(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"secret response"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(ModelDiscoveryError, match="HTTP 401") as exc:
        fetch_provider_models("openai", api_key="test", environ={})
    assert "secret response" not in str(exc.value)

from __future__ import annotations

import json

import terminal_ai as core
from api_provider_backend import APIProviderBackend


class FakeStreamResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        yield b'data: {"choices":[{"delta":{"content":"OK"}}]}\n'
        yield b'data: [DONE]\n'


def test_openai_compatible_backend_uses_saved_generation_settings(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeStreamResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    backend = APIProviderBackend(
        "openai", "test-key", model="example-model",
        temperature=0.25, top_p=0.8, max_tokens=900, timeout=23,
    )

    assert list(backend.stream("", [core.Msg("user", "hello")])) == ["OK"]
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["timeout"] == 23
    assert captured["body"]["temperature"] == 0.25
    assert captured["body"]["top_p"] == 0.8
    assert captured["body"]["max_tokens"] == 900


def test_anthropic_backend_uses_saved_output_limit(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeStreamResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    backend = APIProviderBackend(
        "anthropic", "test-key", model="claude-example",
        max_tokens=1234, timeout=17,
    )
    list(backend.stream("", [core.Msg("user", "hello")]))

    assert captured["body"]["max_tokens"] == 1234
    assert captured["timeout"] == 17


def test_provider_generation_settings_are_bounded():
    backend = APIProviderBackend(
        "openai", "test-key", temperature=9, top_p=-1,
        max_tokens=999999, timeout=999,
    )
    assert backend.temperature == 2
    assert backend.top_p == 0
    assert backend.max_tokens == 32768
    assert backend.timeout == 180



def test_ollama_backend_does_not_send_bearer_auth_when_key_is_optional(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["authorization"] = request.get_header("Authorization")
        captured["url"] = request.full_url
        return FakeStreamResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    backend = APIProviderBackend(
        "ollama", "", model="local-qwen", base_url="http://localhost:11434/v1",
    )
    list(backend.stream("", [core.Msg("user", "hello")]))
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert captured["authorization"] is None

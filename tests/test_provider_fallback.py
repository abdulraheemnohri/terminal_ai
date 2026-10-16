import pytest

import terminal_ai as core
from application.provider_fallback import CloudFirstFallbackBackend


class FakeBackend(core.Backend):
    def __init__(self, label, chunks=None, error=None):
        self.label = label
        self.chunks = list(chunks or [])
        self.error = error
        self.calls = 0

    def stream(self, system, history, tools=None):
        self.calls += 1
        if self.error and not self.chunks:
            raise self.error
        for chunk in self.chunks:
            yield chunk
        if self.error:
            raise self.error


def test_cloud_fallback_tries_primary_then_secondary_before_local():
    primary = FakeBackend("primary", error=RuntimeError("offline"))
    secondary = FakeBackend("secondary", chunks=["cloud answer"])
    local = FakeBackend("local", chunks=["local answer"])
    backend = CloudFirstFallbackBackend([primary, secondary], local)

    assert list(backend.stream("", [core.Msg("user", "hello")])) == ["cloud answer"]
    assert primary.calls == 1
    assert secondary.calls == 1
    assert local.calls == 0
    assert backend.label == "secondary"


def test_cloud_fallback_uses_local_only_after_every_cloud_fails():
    primary = FakeBackend("primary", error=RuntimeError("offline"))
    secondary = FakeBackend("secondary", error=RuntimeError("offline"))
    local = FakeBackend("local", chunks=["offline answer"])
    backend = CloudFirstFallbackBackend([primary, secondary], local)

    assert list(backend.stream("", [core.Msg("user", "hello")])) == ["offline answer"]
    assert primary.calls == secondary.calls == local.calls == 1
    assert backend.label == "local"


def test_cloud_fallback_skips_empty_cloud_responses():
    primary = FakeBackend("empty")
    secondary = FakeBackend("secondary", chunks=["answer"])
    backend = CloudFirstFallbackBackend([primary, secondary], None)

    assert list(backend.stream("", [core.Msg("user", "hello")])) == ["answer"]
    assert primary.calls == secondary.calls == 1


def test_cloud_fallback_does_not_switch_after_partial_output():
    primary = FakeBackend("primary", chunks=["partial"], error=RuntimeError("stream broke"))
    secondary = FakeBackend("secondary", chunks=["duplicate"])
    backend = CloudFirstFallbackBackend([primary, secondary], None)

    with pytest.raises(core.BackendError, match="partial output"):
        list(backend.stream("", [core.Msg("user", "hello")]))
    assert secondary.calls == 0


def test_cloud_fallback_reports_when_every_backend_fails():
    primary = FakeBackend("primary", error=RuntimeError("offline"))
    local = FakeBackend("local", error=RuntimeError("not installed"))
    backend = CloudFirstFallbackBackend([primary], local)

    with pytest.raises(core.BackendError, match="All cloud providers and local inference failed"):
        list(backend.stream("", [core.Msg("user", "hello")]))


def test_local_model_roles_never_include_tool_role():
    backend = core.LiteRTBackend.__new__(core.LiteRTBackend)
    backend.style = "chatml"
    history = [
        core.Msg("user", "Question"),
        core.Msg("model", "I'll check."),
        core.Msg("tool", "[lookup] result"),
    ]

    rendered = backend._render("System", history, None)
    assert "<|im_start|>tool" not in rendered
    assert "<|im_start|>assistant" in rendered
    assert "<|im_start|>user\n[Tool result — untrusted context]" in rendered

    normalized = [backend._normalize_local_message(item)["role"] for item in history]
    assert normalized == ["user", "model", "user"]


def test_litert_python_adapter_maps_tool_results_to_user_context():
    from litert_api_backend import LiteRTPythonBackend

    message = LiteRTPythonBackend._message("tool", "result")
    assert message["role"] == "user"
    assert message["content"].startswith("[Tool result — untrusted context]")
    assert LiteRTPythonBackend._message("model", "answer")["role"] == "model"



def test_cloud_provider_history_normalizes_model_and_tool_roles():
    from api_provider_backend import APIProviderBackend

    messages = APIProviderBackend._history_messages([
        core.Msg("user", "Question"),
        core.Msg("model", "I will check."),
        core.Msg("tool", "lookup result"),
    ])
    assert [item["role"] for item in messages] == ["user", "assistant", "user"]
    assert messages[-1]["content"].startswith("[Tool result — untrusted context]\n")

from __future__ import annotations

from pathlib import Path

from application.security import security_status


def test_security_status_reports_local_only_without_credentials(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("TERMINAL_AI_AUTH_USER", raising=False)
    monkeypatch.delenv("TERMINAL_AI_AUTH_PASSWORD", raising=False)
    status = security_status(tmp_path)
    assert status["state"] == "local-only"
    assert status["authentication_configured"] is False
    assert status["remote_bind_requires_auth"] is True
    assert status["credentials_exposed"] is False


def test_security_status_detects_partial_credentials_fail_closed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TERMINAL_AI_AUTH_USER", "operator")
    monkeypatch.delenv("TERMINAL_AI_AUTH_PASSWORD", raising=False)
    status = security_status(tmp_path)
    assert status["state"] == "misconfigured"
    assert status["configuration_error"] is True
    assert "fail closed" in status["message"]


def test_security_status_never_returns_credential_values(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TERMINAL_AI_AUTH_USER", "operator-private-name")
    monkeypatch.setenv("TERMINAL_AI_AUTH_PASSWORD", "private-password-value")
    status = security_status(tmp_path)
    assert status["state"] == "protected"
    serialized = repr(status)
    assert "operator-private-name" not in serialized
    assert "private-password-value" not in serialized
    assert status["credential_source"] == "environment"

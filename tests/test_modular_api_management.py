from __future__ import annotations

import os
import re
from pathlib import Path

from litestar.testing import TestClient

import app as app_module


class FakeEnvManager:
    """Keep credential API tests isolated from the repository's real .env file."""

    def __init__(self, *, env_file: Path, workspace: Path) -> None:
        self.env_file = env_file
        self.workspace = workspace

    def load(self, *, apply: bool = False) -> None:
        return None

    def set(self, name: str, value: str, *, persist: bool = False) -> bool:
        os.environ[name] = value
        return True

    def unset(self, name: str, *, persist: bool = False) -> bool:
        os.environ.pop(name, None)
        return True


def test_provider_credentials_can_be_saved_and_removed_without_echoing_secret(monkeypatch):
    monkeypatch.setattr(app_module.core, "EnvManager", FakeEnvManager)
    monkeypatch.setattr(app_module, "_AGENT", None)
    monkeypatch.setattr(app_module, "_BACKEND", None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with TestClient(app=app_module.app) as client:
        saved = client.post(
            "/api/providers/credentials",
            json={"provider_id": "openai", "api_key": "test-secret-do-not-return"},
        )
        assert saved.status_code == 200
        assert saved.json()["provider_id"] == "openai"
        assert saved.json()["configured"] is True
        assert saved.json()["secret_returned"] is False
        assert "test-secret-do-not-return" not in saved.text
        assert os.environ["OPENAI_API_KEY"] == "test-secret-do-not-return"

        removed = client.post(
            "/api/providers/credentials",
            json={"provider_id": "openai", "clear": True},
        )
        assert removed.status_code == 200
        assert removed.json()["cleared"] is True
        assert removed.json()["configured"] is False
        assert "test-secret-do-not-return" not in removed.text
        assert "OPENAI_API_KEY" not in os.environ


def test_provider_credentials_reject_unknown_provider_and_malformed_requests():
    with TestClient(app=app_module.app) as client:
        unknown = client.post(
            "/api/providers/credentials",
            json={"provider_id": "not-a-provider", "api_key": "test"},
        )
        assert unknown.status_code == 400

        empty = client.post(
            "/api/providers/credentials",
            json={"provider_id": "openai", "api_key": "   "},
        )
        assert empty.status_code == 400

        conflict = client.post(
            "/api/providers/credentials",
            json={"provider_id": "openai", "api_key": "test", "clear": True},
        )
        assert conflict.status_code == 400


def test_standalone_section_pages_have_separate_assets_and_valid_local_links():
    root = Path(__file__).resolve().parents[1]
    sections = {
        "api-management": ("web/pages/api-management.html", "web/css/api-management.css", "web/js/api-management.js"),
        "chat-model-lab": ("web/pages/chat-model-lab.html", "web/css/chat-model-lab.css", "web/js/chat-model-lab.js"),
        "whatsapp-agent": ("web/pages/whatsapp-agent.html", "web/css/whatsapp-agent.css", "web/js/whatsapp-agent.js"),
    }
    for name, (html_path, css_path, js_path) in sections.items():
        html = (root / html_path).read_text(encoding="utf-8")
        assert f"/static/{css_path.removeprefix('web/')}" in html, f"{name} must load its own CSS"
        assert f"/static/{js_path.removeprefix('web/')}" in html, f"{name} must load its own JavaScript"
        assert (root / css_path).is_file()
        assert (root / js_path).is_file()
        assert "<!doctype html>" in html.lower()
        assert 'href="/"' in html
        assert "API Management" in html or name == "api-management"
    index = (root / "web/index.html").read_text(encoding="utf-8")
    for slug in sections:
        assert f"/static/pages/{slug}.html" in index

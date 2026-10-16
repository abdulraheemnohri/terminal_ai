"""Regression checks for provider profile dashboard controls."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_provider_profile_editor_exposes_model_discovery_controls():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert 'id="profile-fetch-models"' in html
    assert 'id="profile-model-options"' in html
    assert 'id="profile-model-count"' in html
    assert 'id="profile-model-error"' in html


def test_saved_provider_profiles_expose_edit_test_and_remove_actions():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "data-edit-provider-profile=" in script
    assert "data-test-provider-profile=" in script
    assert "data-delete-provider-profile=" in script
    assert 'api("/api/providers/test"' in script
    assert 'api("/api/providers/models"' in script
    assert 'api("/api/settings"' in script


def test_profile_connection_test_uses_saved_credentials_not_browser_key_values():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    start = script.index("async function testProviderProfile")
    end = script.index('\n$("provider-profile-list")', start)
    function_body = script[start:end]
    assert "provider_id:id" in function_body
    assert "model:profile.model" in function_body
    assert "api_key:" not in function_body

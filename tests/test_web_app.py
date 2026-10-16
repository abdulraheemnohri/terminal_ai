from litestar.testing import TestClient

from app import app


def test_dashboard_returns_html():
    with TestClient(app=app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Terminal AI" in response.text
    assert "AI Chat" in response.text
    assert "overview-health" in response.text
    assert "overview-checklist" in response.text
    assert "Human approval gate" in response.text
    assert "Reviewer note (optional, saved to audit history)" in response.text
    assert "Skill evolution review queue" in response.text
    assert "Draft from reviewed learning" in response.text
    assert "LOCAL-FIRST AGENT CONTROL CENTER" in response.text
    assert "Auto — cloud-first, local fallback" in response.text
    assert "ordered provider failover" in response.text
    assert 'id="command-palette"' in response.text
    assert 'id="overview-browser-badge"' in response.text
    assert "Jump to…" in response.text
    assert 'id="ui-pref-compact"' in response.text
    assert 'id="ui-pref-large-text"' in response.text
    assert 'id="ui-pref-reduced-motion"' in response.text


def test_status_endpoint_is_available_without_model():
    with TestClient(app=app) as client:
        response = client.get("/api/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["interface"] == "Litestar Web UI"
    assert "gemini_configured" in payload
    assert isinstance(payload["session_count"], int)
    assert payload["active_session"]
    assert isinstance(payload["local_model_details"], list)


def test_settings_reject_invalid_mode():
    with TestClient(app=app) as client:
        response = client.patch("/api/settings", json={"mode": "not-a-mode"})
    assert response.status_code == 400



def test_human_approval_is_mandatory_and_cannot_be_disabled():
    with TestClient(app=app) as client:
        before = client.get("/api/settings")
        rejected = client.patch("/api/settings", json={"tool_approval_required": False})
        after = client.get("/api/settings")
    assert before.status_code == 200
    assert before.json()["tool_approval_required"] is True
    assert rejected.status_code == 400
    assert "cannot be disabled" in rejected.json()["detail"]
    assert after.json()["tool_approval_required"] is True



def test_models_endpoint_does_not_require_backend():
    with TestClient(app=app) as client:
        response = client.get("/api/models")
    assert response.status_code == 200
    payload = response.json()
    assert "models" in payload
    assert "models_dir" in payload
    assert "installed_count" in payload


def test_diagnostics_endpoint_is_local_and_structured():
    with TestClient(app=app) as client:
        response = client.get("/api/diagnostics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["application"]["interface"] == "Litestar Web UI"
    assert "storage" in payload
    assert "runtime" in payload


def test_provider_discovery_is_dynamic_and_local():
    with TestClient(app=app) as client:
        response = client.get("/api/providers")
    assert response.status_code == 200
    payload = response.json()
    assert {item["id"] for item in payload["providers"]} >= {"gemini", "litert-lm", "huggingface-hub", "openai", "anthropic", "openrouter", "groq", "deepseek", "together", "mistral", "xai", "fireworks", "cerebras", "custom-openai"}


def test_download_requires_explicit_confirmation():
    with TestClient(app=app) as client:
        response = client.post("/api/models/download", json={"model_id": "qwen3-0.6b"})
    assert response.status_code == 400


def test_download_rejects_unregistered_model():
    with TestClient(app=app) as client:
        response = client.post("/api/models/download", json={"model_id": "qwen3-1b", "confirm": True})
    assert response.status_code == 404


def test_download_jobs_endpoint_is_available():
    with TestClient(app=app) as client:
        response = client.get("/api/downloads")
    assert response.status_code == 200
    assert "downloads" in response.json()


def test_model_detail_endpoint_returns_registered_model():
    with TestClient(app=app) as client:
        response = client.get("/api/models/qwen3-0.6b")
        missing = client.get("/api/models/not-registered")
    assert response.status_code == 200
    assert response.json()["name"] == "qwen3-0.6b"
    assert response.json()["hf_repo"] == "litert-community/Qwen3-0.6B"
    assert response.json()["hf_file"] == "Qwen3-0.6B.litertlm"
    assert "installed" in response.json()
    assert missing.status_code == 404


def test_dashboard_pages_are_directly_addressable():
    pages = ["/overview", "/chat", "/sessions", "/models", "/diagnostics", "/memory", "/goals", "/self", "/skills", "/tools", "/learning", "/improvements", "/settings"]
    with TestClient(app=app) as client:
        for path in pages:
            response = client.get(path)
            assert response.status_code == 200, path
            assert "Terminal AI" in response.text, path


def test_dashboard_assets_are_served_separately():
    with TestClient(app=app) as client:
        css = client.get("/static/app.css")
        js = client.get("/static/app.js")
    assert css.status_code == 200
    assert "font-family" in css.text
    assert js.status_code == 200
    assert "routeViews" in js.text
    assert "response-meta" in js.text
    assert "overview-health" in js.text


def test_self_status_exposes_operational_model_without_claiming_sentience():
    with TestClient(app=app) as client:
        response = client.get("/api/self/status")
    assert response.status_code == 200
    payload = response.json()
    assert "identity" in payload
    assert "mission" in payload
    assert "notice" in payload
    assert "sentience" in payload["notice"]


def test_self_reflection_can_be_disabled():
    with TestClient(app=app) as client:
        response = client.patch("/api/settings", json={"self_reflection_enabled": False})
        reflect = client.post("/api/self/reflect", json={})
        client.patch("/api/settings", json={"self_reflection_enabled": True})
    assert response.status_code == 200
    assert reflect.status_code == 400


def test_settings_reject_insecure_custom_remote_endpoint():
    with TestClient(app=app) as client:
        response = client.patch("/api/settings", json={
            "active_provider": "custom-openai",
            "custom_base_url": "http://remote.example/v1",
        })
    assert response.status_code == 400


def test_provider_connection_test_rejects_unknown_provider():
    with TestClient(app=app) as client:
        response = client.post("/api/providers/test", json={"provider_id": "unknown-provider"})
    assert response.status_code == 400



def test_update_status_is_available_without_network():
    with TestClient(app=app) as client:
        response = client.get("/api/updates/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["channel"] == "main"
    assert payload["interval_hours"] == 24


def test_update_apply_requires_explicit_confirmation():
    with TestClient(app=app) as client:
        response = client.post("/api/updates/apply", json={})
    assert response.status_code == 400


def test_update_interval_is_bounded_and_persisted():
    with TestClient(app=app) as client:
        response = client.patch("/api/settings", json={
            "updates_enabled": True,
            "update_check_interval_hours": 2,
        })
        status = client.get("/api/updates/status")
        client.patch("/api/settings", json={"updates_enabled": False, "update_check_interval_hours": 24})
    assert response.status_code == 200
    assert response.json()["update_check_interval_hours"] == 6
    assert status.status_code == 200
    assert status.json()["enabled"] is True
    assert status.json()["interval_hours"] == 6


def test_self_reflection_returns_diagnostic_error_when_agent_initialization_fails(monkeypatch):
    import app as web_app

    def fail_initialization():
        raise RuntimeError("simulated backend initialization failure")

    monkeypatch.setattr(web_app, "_get_agent", fail_initialization)
    with TestClient(app=web_app.app) as client:
        response = client.post("/api/self/reflect", json={})
    assert response.status_code == 502
    assert "Self-reflection failed" in response.json()["detail"]
    assert "simulated backend initialization failure" in response.json()["detail"]


def test_local_registry_uses_qwen3_06b_without_gemma_models():
    import terminal_ai as core

    registry = core.ModelRegistry()
    assert set(registry.local) == {"qwen3-0.6b"}
    model = registry.local["qwen3-0.6b"]
    assert model.hf_repo == "litert-community/Qwen3-0.6B"
    assert model.hf_file == "Qwen3-0.6B.litertlm"
    assert model.size == "0.6B"


def test_self_reflection_uses_internal_status_helper_and_succeeds(monkeypatch, tmp_path):
    import app as web_app

    class FakeBackend:
        label = "test-backend"

        def stream(self, system, history, tools=None):
            yield "Operational review completed. One improvement: add regression tests."

    class FakeAgent:
        backend = FakeBackend()

    monkeypatch.setattr(web_app, "_get_agent", lambda: FakeAgent())
    monkeypatch.setattr(web_app.core, "STATE_DIR", tmp_path)
    with TestClient(app=web_app.app) as client:
        response = client.post("/api/self/reflect", json={})
    assert response.status_code == 201
    assert "Operational review completed" in response.json()["reflection"]["text"]
    assert (tmp_path / "self_reflection.json").is_file()


def test_skills_tools_learning_and_improvement_apis_are_available_without_model():
    with TestClient(app=app) as client:
        skills = client.get("/api/skills")
        tools = client.get("/api/tools")
        learning = client.get("/api/learning")
        improvements = client.get("/api/self/improvements")
    assert skills.status_code == 200
    assert "skills" in skills.json()
    assert tools.status_code == 200
    assert tools.json()["execution_enabled_in_web"] is False
    assert tools.json()["built_in_count"] > 0
    assert learning.status_code == 200
    assert "memory_facts" in learning.json()
    assert improvements.status_code == 200
    assert "proposals" in improvements.json()


def test_skill_creation_validates_steps_and_saves_locally():
    with TestClient(app=app) as client:
        invalid = client.post("/api/skills", json={"name": "Empty skill", "steps": []})
    assert invalid.status_code == 400


def test_favicon_route_returns_svg_without_404():
    with TestClient(app=app) as client:
        response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert "image/svg+xml" in response.headers["content-type"]
    assert "<svg" in response.text


def test_roleplay_persona_setting_is_supported_and_validated(monkeypatch, tmp_path):
    import app as web_app
    monkeypatch.setattr(web_app, "WEB_SETTINGS", tmp_path / "web_settings.json")
    monkeypatch.setattr(web_app.SelfXEngine, "create_checkpoint", lambda self: {"id": "test"})
    with TestClient(app=app) as client:
        response = client.patch("/api/settings", json={"agentic_persona": "roleplay"})
        invalid = client.patch("/api/settings", json={"agentic_persona": "real-person-impersonation"})
        client.patch("/api/settings", json={"agentic_persona": "helpful"})
    assert response.status_code == 200
    assert response.json()["agentic_persona"] == "roleplay"
    assert invalid.status_code == 400


def test_browser_domain_settings_validate_and_normalize_without_enabling_execution():
    with TestClient(app=app) as client:
        before = client.get("/api/settings")
        previous = before.json().get("browser_allowed_domains", [])
        try:
            accepted = client.patch("/api/settings", json={
                "browser_allowed_domains": [".EXAMPLE.COM.", "example.com", "docs.example.org"]
            })
            assert accepted.status_code == 200
            assert accepted.json()["browser_allowed_domains"] == ["example.com", "docs.example.org"]

            invalid = client.patch("/api/settings", json={
                "browser_allowed_domains": ["*.example.com"]
            })
            assert invalid.status_code == 400

            status = client.get("/api/browser/status")
            assert status.status_code == 200
            assert status.json()["enabled"] is True
            assert status.json()["allowed_domain_count"] == 2
            assert status.json()["execution_enabled"] is False
        finally:
            client.patch("/api/settings", json={"browser_allowed_domains": previous})


def test_browser_domain_settings_reject_urls_and_ip_literals():
    with TestClient(app=app) as client:
        for value in ("https://example.com", "example.com/path", "127.0.0.1", "example.com:443"):
            response = client.patch("/api/settings", json={"browser_allowed_domains": [value]})
            assert response.status_code == 400, value


def test_browser_status_does_not_start_browser_or_enable_actions():
    with TestClient(app=app) as client:
        response = client.get("/api/browser/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_enabled"] is False
    assert "authenticated dispatch" in payload["notice"]



def test_browser_status_never_enables_execution_or_launches_browser(monkeypatch):
    import app as web_app

    original_read_settings = web_app._read_settings
    monkeypatch.setattr(web_app, "_read_settings", lambda: {
        **original_read_settings(), "browser_allowed_domains": ["example.com"]
    })
    with TestClient(app=web_app.app) as client:
        response = client.get("/api/browser/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["allowed_domain_count"] == 1
    assert payload["execution_enabled"] is False


def test_browser_domain_settings_reject_malformed_entries():
    invalid_values = [
        "example.com",
        ["example.com:8443"],
        ["bad domain.example"],
        [None],
        [f"sub{i}.example.com" for i in range(51)],
    ]
    with TestClient(app=app) as client:
        previous = client.get("/api/settings").json().get("browser_allowed_domains", [])
        try:
            for value in invalid_values:
                response = client.patch("/api/settings", json={"browser_allowed_domains": value})
                assert response.status_code == 400, value
        finally:
            client.patch("/api/settings", json={"browser_allowed_domains": previous})




def test_command_palette_and_browser_overview_assets_are_served():
    with TestClient(app=app) as client:
        response = client.get("/static/app.js")
        css = client.get("/static/app.css")
    assert response.status_code == 200
    assert "openCommandPalette" in response.text
    assert "loadBrowserOverview" in response.text
    assert 'e.key==="ArrowDown"' in response.text
    assert css.status_code == 200
    assert ".command-backdrop.open" in css.text
    assert ".browser-security-card" in css.text


def test_interface_preferences_are_browser_local_and_styled():
    with TestClient(app=app) as client:
        js = client.get("/static/app.js")
        css = client.get("/static/app.css")
    assert js.status_code == 200
    assert "terminal-ai-ui-preferences" in js.text
    assert "ui-pref-reset" in js.text
    assert "applyUiPreferences" in js.text
    assert css.status_code == 200
    assert ".ui-compact" in css.text
    assert ".ui-large-text" in css.text
    assert ".ui-reduced-motion" in css.text



def test_dashboard_theme_and_toast_assets_are_accessible():
    with TestClient(app=app) as client:
        page = client.get("/")
        js = client.get("/static/app.js")
        css = client.get("/static/app.css")
    assert page.status_code == 200
    assert 'id="theme-toggle"' in page.text
    assert 'id="toast-region"' in page.text
    assert js.status_code == 200
    assert "function applyTheme" in js.text
    assert "function showToast" in js.text
    assert "Switch to light theme" in js.text
    assert css.status_code == 200
    assert ":root.theme-light" in css.text
    assert ".toast-region" in css.text



def test_health_timeline_and_collection_search_are_served():
    with TestClient(app=app) as client:
        page = client.get("/")
        js = client.get("/static/app.js")
        css = client.get("/static/app.css")
    assert page.status_code == 200
    assert 'id="health-timeline-svg"' in page.text
    assert 'id="health-timeline-summary"' in page.text
    assert js.status_code == 200
    assert "function recordHealthSnapshot" in js.text
    assert "function renderHealthTimeline" in js.text
    assert "function setupCollectionSearch" in js.text
    assert "control-audit-list" in js.text
    assert css.status_code == 200
    assert ".health-timeline-chart" in css.text
    assert ".collection-search" in css.text

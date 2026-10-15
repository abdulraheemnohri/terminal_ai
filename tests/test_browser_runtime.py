from application.browser_runtime import create_browser_runtime


def test_playwright_adapter_registers_only_implemented_browser_tools():
    runtime = create_browser_runtime(["example.com"])
    try:
        assert runtime.registered_tools == [
            "browser.read_page",
            "browser.screenshot",
            "browser.click",
            "browser.fill_form",
            "browser.submit_form",
        ]
        catalog = {item["name"]: item for item in runtime.registry.describe()}
        assert catalog["browser.read_page"]["requires_approval"] is False
        assert catalog["browser.screenshot"]["requires_approval"] is True
        assert catalog["browser.click"]["requires_approval"] is True
        assert catalog["browser.fill_form"]["requires_approval"] is True
        assert catalog["browser.submit_form"]["requires_approval"] is True
    finally:
        runtime.close()


def test_state_changing_browser_tools_cannot_run_without_approval():
    runtime = create_browser_runtime(["example.com"])
    try:
        result = runtime.registry.execute(
            "browser.submit_form",
            {"page_id": "missing", "selector": "button[type=submit]"},
        )
        assert result.ok is False
        assert "Approval required" in result.error
    finally:
        runtime.close()

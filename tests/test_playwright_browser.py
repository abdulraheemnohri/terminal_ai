import pytest

from agent.playwright_browser import BrowserPolicyError, validate_public_url


def test_browser_requires_explicit_allowlist():
    with pytest.raises(BrowserPolicyError, match="allowlist"):
        validate_public_url("https://example.com", [])


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "javascript:alert(1)",
    "http://localhost/admin",
    "http://127.0.0.1/",
    "http://192.168.1.1/",
    "https://user:password@example.com/",
])
def test_browser_rejects_unsafe_urls_before_network_access(url):
    with pytest.raises(BrowserPolicyError):
        validate_public_url(url, ["example.com"])


def test_browser_rejects_unlisted_host_before_dns_lookup():
    with pytest.raises(BrowserPolicyError, match="allowlist"):
        validate_public_url("https://not-allowed.invalid", ["example.com"])


def test_browser_constructor_requires_domain_allowlist():
    from agent.playwright_browser import PlaywrightBrowser

    with pytest.raises(BrowserPolicyError, match="allowed_domains"):
        PlaywrightBrowser([])

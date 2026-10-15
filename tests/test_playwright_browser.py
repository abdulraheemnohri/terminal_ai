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


@pytest.mark.parametrize("domains", [
    ["*.example.com"],
    ["https://example.com"],
    ["example.com/path"],
    ["127.0.0.1"],
    "example.com",
])
def test_browser_rejects_malformed_allowlist_entries_before_dns(domains, monkeypatch):
    def unexpected_dns(*args, **kwargs):
        raise AssertionError("DNS must not run for malformed allowlist entries")

    monkeypatch.setattr("agent.playwright_browser.socket.getaddrinfo", unexpected_dns)
    with pytest.raises(BrowserPolicyError):
        validate_public_url("https://example.com", domains)


@pytest.mark.parametrize("url", [
    "https://example.com:99999/",
    "https://example.com:notaport/",
    "https://[not-an-ipv6-address]/",
])
def test_browser_rejects_malformed_authority(url, monkeypatch):
    def unexpected_dns(*args, **kwargs):
        raise AssertionError("DNS must not run for malformed URLs")

    monkeypatch.setattr("agent.playwright_browser.socket.getaddrinfo", unexpected_dns)
    with pytest.raises(BrowserPolicyError):
        validate_public_url(url, ["example.com"])


def test_browser_normalizes_domains_and_rejects_private_dns_answers(monkeypatch):
    def private_dns(host, port, **kwargs):
        return [(None, None, None, None, ("10.0.0.7", port))]

    monkeypatch.setattr("agent.playwright_browser.socket.getaddrinfo", private_dns)
    with pytest.raises(BrowserPolicyError, match="non-public"):
        validate_public_url("https://docs.example.com/", [".EXAMPLE.COM."])


def test_browser_accepts_allowlisted_public_domain(monkeypatch):
    def public_dns(host, port, **kwargs):
        return [(None, None, None, None, ("93.184.216.34", port))]

    monkeypatch.setattr("agent.playwright_browser.socket.getaddrinfo", public_dns)
    assert validate_public_url("https://docs.example.com:8443/page", [".EXAMPLE.COM."]) == "https://docs.example.com:8443/page"

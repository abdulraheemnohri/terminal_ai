"""Optional, allowlisted Playwright browser adapter for Terminal AI.

Install the optional dependency with: pip install playwright && playwright install chromium.
This adapter is intentionally disabled until an explicit domain allowlist is supplied.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import threading
import uuid
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit


class BrowserPolicyError(ValueError):
    """Raised when a navigation violates the configured browser boundary."""


def _normalize_domain(value: str) -> str:
    """Normalize a configured DNS name and reject wildcard/URL-shaped entries."""
    if not isinstance(value, str):
        raise BrowserPolicyError("Allowed domains must be DNS names.")
    domain = value.strip().lower().lstrip(".").rstrip(".")
    if not domain or any(char in domain for char in "*/:@\\\\") or "%" in domain:
        raise BrowserPolicyError("Allowed domains must be plain DNS names without wildcards or URLs.")
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise BrowserPolicyError("Allowed domain is not a valid internationalized DNS name.") from exc
    if len(domain) > 253:
        raise BrowserPolicyError("Allowed domain is too long.")
    labels = domain.split(".")
    if any(
        not label or len(label) > 63
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
        for label in labels
    ):
        raise BrowserPolicyError("Allowed domain contains an invalid DNS label.")
    try:
        ipaddress.ip_address(domain)
    except ValueError:
        return domain
    raise BrowserPolicyError("Configure DNS names, not IP addresses, in the domain allowlist.")


def validate_public_url(url: str, allowed_domains: Iterable[str]) -> str:
    """Accept HTTP(S) URLs on an explicit DNS allowlist and reject local/private targets."""
    if not isinstance(url, str) or len(url) > 3000:
        raise BrowserPolicyError("URL must be a string no longer than 3000 characters.")
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except ValueError as exc:
        raise BrowserPolicyError("URL has an invalid host or port.") from exc
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise BrowserPolicyError("Only http and https URLs are allowed.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise BrowserPolicyError("URL must include a host and cannot contain embedded credentials.")
    raw_host = parsed.hostname.rstrip(".").lower()
    if raw_host == "localhost" or raw_host.endswith(".localhost") or raw_host.endswith(".local"):
        raise BrowserPolicyError("Local hostnames are blocked.")
    try:
        address = ipaddress.ip_address(raw_host)
        host = raw_host
    except ValueError:
        host = _normalize_domain(raw_host)
        address = None
    if address is not None and (not address.is_global or address.is_multicast or address.is_reserved):
        raise BrowserPolicyError("Private, loopback, link-local, and reserved IP addresses are blocked.")

    if isinstance(allowed_domains, (str, bytes)):
        raise BrowserPolicyError("allowed_domains must be a collection of DNS names, not a string.")
    try:
        allow = {_normalize_domain(item) for item in allowed_domains}
    except TypeError as exc:
        raise BrowserPolicyError("allowed_domains must be a collection of DNS names.") from exc
    if not allow:
        raise BrowserPolicyError("Browser access is disabled until allowed_domains is configured.")
    if not any(host == domain or host.endswith("." + domain) for domain in allow):
        raise BrowserPolicyError("Host is not in the configured browser domain allowlist.")

    # Resolve hostnames before navigation and reject any non-public answer.
    # Network-level egress restrictions are still needed to defend against DNS rebinding.
    if address is None:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(
                host, port or (443 if scheme == "https" else 80), type=socket.SOCK_STREAM
            )}
        except OSError as exc:
            raise BrowserPolicyError("Host could not be resolved safely.") from exc
    else:
        addresses = {str(address)}
    if not addresses:
        raise BrowserPolicyError("Host did not resolve to an address.")
    for raw in addresses:
        try:
            ip = ipaddress.ip_address(raw.split("%", 1)[0])
        except ValueError as exc:
            raise BrowserPolicyError("Host returned an invalid address.") from exc
        if not ip.is_global or ip.is_multicast or ip.is_reserved:
            raise BrowserPolicyError("Host resolves to a non-public address.")
    return url.strip()


class PlaywrightBrowser:
    """Isolated browser pages exposed as opaque IDs; no cookies or page internals exported."""

    def __init__(self, allowed_domains: Iterable[str], *, headless: bool = True,
                 timeout_ms: int = 15000, max_pages: int = 5) -> None:
        self.allowed_domains = tuple(allowed_domains)
        if not self.allowed_domains:
            raise BrowserPolicyError("Configure at least one allowed domain to enable browsing.")
        self.timeout_ms = max(1000, min(int(timeout_ms), 60000))
        self.max_pages = max(1, min(int(max_pages), 10))
        self._lock = threading.RLock()
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._pages: dict[str, Any] = {}

    def _ensure_context(self) -> Any:
        if self._context is not None:
            return self._context
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Browser support requires the optional 'playwright' package and Chromium.") from exc
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=True)
            self._context = self._browser.new_context(accept_downloads=False, service_workers="block")
            self._context.set_default_timeout(self.timeout_ms)
            # All subresources and redirects must also remain on explicitly allowed public hosts.
            self._context.route("**/*", self._guard_route)
            return self._context
        except Exception:
            self.close()
            raise

    def _guard_route(self, route: Any) -> None:
        try:
            validate_public_url(route.request.url, self.allowed_domains)
            route.continue_()
        except Exception:
            route.abort("blockedbyclient")

    def _page(self, page_id: str) -> Any:
        page = self._pages.get(page_id)
        if page is None or page.is_closed():
            raise BrowserPolicyError("Unknown or closed browser page.")
        return page

    def open_page(self, url: str) -> dict[str, Any]:
        safe_url = validate_public_url(url, self.allowed_domains)
        with self._lock:
            if len(self._pages) >= self.max_pages:
                raise BrowserPolicyError("Browser page limit reached.")
            context = self._ensure_context()
            page = context.new_page()
            page.goto(safe_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            page_id = uuid.uuid4().hex
            self._pages[page_id] = page
            return {"page_id": page_id, "url": page.url, "title": page.title()[:300]}

    def read_page(self, url: str) -> dict[str, Any]:
        opened = self.open_page(url)
        with self._lock:
            page = self._page(opened["page_id"])
            text = page.locator("body").inner_text(timeout=self.timeout_ms)
            return {**opened, "text": text[:20000]}

    def screenshot(self, page_id: str) -> dict[str, Any]:
        with self._lock:
            page = self._page(page_id)
            data = page.screenshot(type="png", full_page=False, timeout=self.timeout_ms)
            if len(data) > 1_500_000:
                raise BrowserPolicyError("Screenshot exceeds the 1.5 MB response limit.")
            return {"page_id": page_id, "mime_type": "image/png",
                    "bytes": len(data), "base64": __import__("base64").b64encode(data).decode("ascii")}

    def click(self, page_id: str, selector: str) -> dict[str, Any]:
        if not isinstance(selector, str) or not selector.strip() or len(selector) > 1000:
            raise BrowserPolicyError("Invalid selector.")
        with self._lock:
            page = self._page(page_id)
            page.locator(selector).first.click(timeout=self.timeout_ms)
            return {"page_id": page_id, "url": page.url, "title": page.title()[:300]}

    def fill_form(self, page_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(fields, dict) or not 1 <= len(fields) <= 50:
            raise BrowserPolicyError("fields must contain between 1 and 50 entries.")
        with self._lock:
            page = self._page(page_id)
            filled = 0
            for selector, value in fields.items():
                if not isinstance(selector, str) or not selector.strip() or len(selector) > 1000:
                    raise BrowserPolicyError("Invalid form selector.")
                if not isinstance(value, (str, int, float, bool)) or len(str(value)) > 4000:
                    raise BrowserPolicyError("Form values must be short scalar values.")
                page.locator(selector).first.fill(str(value), timeout=self.timeout_ms)
                filled += 1
            return {"page_id": page_id, "fields_filled": filled, "submitted": False}

    def submit_form(self, page_id: str, selector: str) -> dict[str, Any]:
        if not isinstance(selector, str) or not selector.strip() or len(selector) > 1000:
            raise BrowserPolicyError("Invalid selector.")
        with self._lock:
            page = self._page(page_id)
            page.locator(selector).first.click(timeout=self.timeout_ms)
            return {"page_id": page_id, "url": page.url, "title": page.title()[:300],
                    "notice": "Action performed; verify the resulting state."}

    def close(self) -> None:
        with self._lock:
            self._pages.clear()
            for resource in (self._context, self._browser):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:
                        pass
            self._context = self._browser = None
            if self._playwright is not None:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None

    def handlers(self) -> dict[str, Any]:
        """Return handlers keyed to the approval-aware browser tool catalog."""
        return {
            "browser.read_page": self.read_page,
            "browser.screenshot": self.screenshot,
            "browser.click": self.click,
            "browser.fill_form": self.fill_form,
            "browser.submit_form": self.submit_form,
        }

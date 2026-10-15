"""Factory that wires the optional Playwright adapter into the strict tool registry.

Construction does not launch Chromium; the browser starts lazily on the first call.
The caller owns lifecycle and must route side effects through Command Control.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from agent.browser_tools import register_browser_tools
from agent.playwright_browser import PlaywrightBrowser
from agentic_runtime import ToolRegistry


@dataclass
class BrowserRuntime:
    """Browser adapter plus the subset of its tools that are actually available."""

    browser: PlaywrightBrowser
    registry: ToolRegistry
    registered_tools: list[str]

    def close(self) -> None:
        """Release browser resources; safe even when Chromium was never started."""
        self.browser.close()


def create_browser_runtime(
    allowed_domains: Iterable[str],
    *,
    timeout_ms: int = 15000,
    max_pages: int = 5,
) -> BrowserRuntime:
    """Create a lazy, allowlisted browser and register only implemented handlers."""
    browser = PlaywrightBrowser(
        allowed_domains, timeout_ms=timeout_ms, max_pages=max_pages
    )
    registry = ToolRegistry()
    registered = register_browser_tools(registry, browser.handlers())
    if not registered:
        browser.close()
        raise RuntimeError("No browser handlers were registered.")
    return BrowserRuntime(browser=browser, registry=registry, registered_tools=registered)

"""Explicit local-only browser dispatch for already-approved Command Control operations."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agent.approved_dispatch import execute_approved_operation
from application.browser_runtime import BrowserRuntime, create_browser_runtime
from command_control import CommandControl

BROWSER_TOOL_NAMES = frozenset({
    "browser.read_page",
    "browser.screenshot",
    "browser.click",
    "browser.fill_form",
    "browser.submit_form",
})


def execute_approved_browser_operation(
    control: CommandControl,
    settings: dict[str, Any],
    operation_id: str,
    *,
    confirmed: bool,
    runtime_factory: Callable[..., BrowserRuntime] = create_browser_runtime,
) -> dict[str, Any]:
    """Dispatch one explicitly confirmed, approved browser operation from a local host.

    This function is not an HTTP handler. Callers must be trusted local operator
    workflows; the web API intentionally does not expose browser execution.
    """
    if confirmed is not True:
        raise ValueError("Explicit confirmation is required; no browser action was executed.")
    domains = settings.get("browser_allowed_domains", [])
    if not isinstance(domains, list) or not domains:
        raise ValueError("Browser execution is disabled until a domain allowlist is configured.")
    if len(domains) > 50 or any(not isinstance(domain, str) for domain in domains):
        raise ValueError("Browser domain settings are invalid; update Settings before dispatch.")

    operation = control.get_operation(operation_id)
    if operation is None:
        raise ValueError("Operation not found.")
    if operation.get("status") != "approved":
        raise ValueError("Operation must have an unused approval; an unused human approval is required.")
    if operation.get("tool") not in BROWSER_TOOL_NAMES:
        raise ValueError("This local dispatcher accepts browser tools only.")

    runtime = runtime_factory(domains)
    try:
        return execute_approved_operation(
            control, runtime.registry, operation_id, max_output_chars=4000
        )
    finally:
        runtime.close()

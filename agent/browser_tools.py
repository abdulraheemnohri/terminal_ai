"""Approval-aware browser tool registration; provider handlers are injected by the host."""
from __future__ import annotations
from collections.abc import Callable, Mapping
from typing import Any

from agentic_runtime import ToolRegistry, ToolSpec

# The registry never invents a browser implementation. A Playwright or remote
# browser adapter must supply each handler explicitly.
_BROWSER_TOOLS = {
    "browser.search": {
        "description": "Search the web and return bounded result metadata.",
        "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 1000}},
        "required": ["query"], "approval": False, "timeout": 20.0,
    },
    "browser.read_page": {
        "description": "Read a public page and return bounded, untrusted text.",
        "properties": {"url": {"type": "string", "minLength": 8, "maxLength": 3000}},
        "required": ["url"], "approval": False, "timeout": 20.0,
    },
    "browser.screenshot": {
        "description": "Capture a screenshot of an approved browser tab.",
        "properties": {"page_id": {"type": "string", "minLength": 1, "maxLength": 200}},
        "required": ["page_id"], "approval": True, "timeout": 20.0,
    },
    "browser.click": {
        "description": "Click a page element; may change remote state.",
        "properties": {"page_id": {"type": "string", "minLength": 1, "maxLength": 200},
                       "selector": {"type": "string", "minLength": 1, "maxLength": 1000}},
        "required": ["page_id", "selector"], "approval": True, "timeout": 20.0,
    },
    "browser.fill_form": {
        "description": "Fill form fields without submitting the form.",
        "properties": {"page_id": {"type": "string", "minLength": 1, "maxLength": 200},
                       "fields": {"type": "object"}},
        "required": ["page_id", "fields"], "approval": True, "timeout": 20.0,
    },
    "browser.submit_form": {
        "description": "Submit a form; may send data or cause an external side effect.",
        "properties": {"page_id": {"type": "string", "minLength": 1, "maxLength": 200},
                       "selector": {"type": "string", "minLength": 1, "maxLength": 1000}},
        "required": ["page_id", "selector"], "approval": True, "timeout": 20.0,
    },
    "browser.download_file": {
        "description": "Download a file to a configured, sandboxed download directory.",
        "properties": {"url": {"type": "string", "minLength": 8, "maxLength": 3000}},
        "required": ["url"], "approval": True, "timeout": 60.0,
    },
}

def register_browser_tools(registry: ToolRegistry, handlers: Mapping[str, Callable[..., Any]]) -> list[str]:
    """Register only injected handlers; missing handlers stay unavailable.

    State-changing actions and downloads require approval in ToolRegistry. The
    host must still enforce URL/domain policy, SSRF protection, download limits,
    credential isolation, and the persistent approval/audit workflow.
    """
    registered: list[str] = []
    for name, definition in _BROWSER_TOOLS.items():
        handler = handlers.get(name)
        if not callable(handler):
            continue
        schema = {"type": "object", "properties": definition["properties"],
                  "required": definition["required"], "additionalProperties": False}
        registry.register(ToolSpec(
            name=name, description=definition["description"], handler=handler,
            parameters=schema, requires_approval=definition["approval"],
            timeout_seconds=definition["timeout"],
        ))
        registered.append(name)
    return registered

def browser_tool_catalog() -> list[dict[str, Any]]:
    """Return metadata only; never exposes credentials or handler internals."""
    return [{"name": name, "description": item["description"],
             "requires_approval": item["approval"],
             "parameters": {"type": "object", "properties": item["properties"],
                            "required": item["required"], "additionalProperties": False}}
            for name, item in _BROWSER_TOOLS.items()]

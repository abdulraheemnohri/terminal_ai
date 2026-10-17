"""Regression tests for dashboard control wiring and accessible labels."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "web" / "index.html"
JS_PATH = ROOT / "web" / "app.js"


def test_dashboard_element_ids_are_unique():
    html = HTML_PATH.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', html)
    duplicates = sorted(element_id for element_id, count in Counter(ids).items() if count > 1)
    assert not duplicates, f"Duplicate dashboard element IDs break control wiring: {duplicates}"


def test_static_javascript_id_references_exist_in_dashboard():
    html = HTML_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    html_ids = set(re.findall(r'\bid="([^"]+)"', html))
    js_ids = set(re.findall(r"""\$\(["']([^"']+)["']\)""", js))
    missing = sorted(js_ids - html_ids)
    assert not missing, f"JavaScript references missing dashboard element IDs: {missing}"



def test_chat_toolbar_controls_have_live_handlers_and_safe_export_routes():
    html = HTML_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    required_controls = {
        "chat-export-md",
        "chat-export-json",
        "chat-copy-transcript",
        "chat-new-session",
        "chat-refresh-runs",
    }
    ids = set(re.findall(r'\\bid="([^"]+)"', html))
    assert required_controls <= ids, f"Chat toolbar is missing controls: {sorted(required_controls - ids)}"
    for control in required_controls:
        assert control in js, f"Chat toolbar control has no JavaScript wiring: {control}"
        assert re.search(r'\\$\\(["\\']' + re.escape(control) + r'["\\']\\)\\?\\.addEventListener', js), (
            f"Chat toolbar control must register an event handler: {control}"
        )
    assert '"/api/sessions/new"' in js, "New chat must create a persistent server-side session"
    assert 'api("/api/chat/runs")' in js, "Refresh runs must use the metadata-only chat trace endpoint"
    assert "URL.createObjectURL" in js and "JSON.stringify(payload" in js, "Exports must create downloadable local files"
    assert 'run.execution' in js, "Trace rendering must display recorded execution stages"


def test_label_targets_exist_in_dashboard():
    html = HTML_PATH.read_text(encoding="utf-8")
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    targets = re.findall(r"""<label\b[^>]*\bfor=["']([^"']+)["']""", html)
    missing = sorted(set(targets) - ids)
    assert not missing, f"Labels reference missing dashboard controls: {missing}"



def test_control_audit_is_visible_and_endpoint_catalog_is_unique():
    html = HTML_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    required_ids = {
        "audit-controls-btn",
        "audit-controls-total",
        "audit-controls-available",
        "audit-controls-attention",
        "audit-controls-updated",
        "feature-control-audit-list",
    }
    html_ids = set(re.findall(r'\bid="([^"]+)"', html))
    assert required_ids <= html_ids, f"Control audit UI is missing: {sorted(required_ids - html_ids)}"

    match = re.search(r"const CONTROL_AUDIT_ENDPOINTS=\[(.*?)\n\];", js, re.S)
    assert match, "The dashboard must declare an explicit control audit endpoint catalog"
    endpoints = re.findall(r'path:"([^"]+)"', match.group(1))
    assert len(endpoints) >= 20, "The audit should cover the major application control surfaces"
    assert len(endpoints) == len(set(endpoints)), "Control audit endpoint paths must be unique"
    assert "/healthz" in endpoints and "/readyz" in endpoints
    assert "/api/settings" in endpoints and "/api/control/pending?status=pending&limit=1" in endpoints

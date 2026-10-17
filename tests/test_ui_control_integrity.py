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
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    assert required_controls <= ids, f"Chat toolbar is missing controls: {sorted(required_controls - ids)}"
    for control in required_controls:
        assert ('$("' + control + '")?.addEventListener' in js or "$('" + control + "')?.addEventListener" in js), (
            f"Chat toolbar control must register an event handler: {control}"
        )
    assert '"/api/sessions/new"' in js, "New chat must create a persistent server-side session"
    assert 'api("/api/chat/runs")' in js, "Refresh runs must use the metadata-only chat trace endpoint"
    assert "URL.createObjectURL" in js and "JSON.stringify(payload" in js, "Exports must create downloadable local files"
    assert "run.execution" in js, "Trace rendering must display recorded execution stages"



def test_chat_search_and_display_preferences_are_persisted_and_applied():
    html = HTML_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    required_ids = {
        "chat-search",
        "chat-search-status",
        "chat-setting-enter",
        "chat-setting-scroll",
        "chat-setting-meta",
        "chat-setting-compact",
        "chat-setting-font",
    }
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    assert required_ids <= ids, f"Chat search/settings UI is missing: {sorted(required_ids - ids)}"
    assert '$("chat-search")?.addEventListener("input",filterChatMessages)' in js
    assert 'localStorage.getItem(CHAT_PREFS_KEY)' in js and 'localStorage.setItem(CHAT_PREFS_KEY' in js
    assert 'if(e.key==="Enter"&&!e.shiftKey&&$("chat-setting-enter")?.checked)' in js
    assert 'classList.toggle("compact"' in js
    assert 'classList.toggle("hide-response-meta"' in js
    assert 'style.fontSize=$("chat-setting-font").value+"px"' in js


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


def test_live_control_feed_has_user_controls_and_bounded_reconnect():
    html = HTML_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    required_controls = {
        "control-live-filter",
        "control-live-pause",
        "control-live-clear",
        "control-live-reconnect",
        "control-live-help",
        "control-live-status",
        "control-live-feed",
    }
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    assert required_controls <= ids, (
        f"Live control feed is missing controls: {sorted(required_controls - ids)}"
    )
    assert '$("control-live-filter").addEventListener("change"' in js
    assert '$("control-live-pause").addEventListener("click"' in js
    assert '$("control-live-clear").addEventListener("click"' in js
    assert 'addEventListener("click",reconnectControlEvents)' in js
    assert 'addEventListener("click",()=>{' in js
    assert "controlSocketRetryDelay=Math.min(30000,delay*2)" in js
    assert "CONTROL_EVENT_HISTORY_LIMIT=100" in js
    assert "controlLivePaused" in js and "renderControlEventFeed()" in js
    assert "terminal-ai-control-feed-filter" in js
    assert 'new WebSocket(scheme+"//"+location.host+"/api/control/events")' in js

def test_diagnostics_report_export_is_visible_and_redacts_sensitive_fields():
    html = HTML_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    assert {"export-diagnostics-report", "diagnostics-export-status"} <= ids
    assert '$("export-diagnostics-report")?.addEventListener("click",exportDiagnosticsReport)' in js
    assert "DIAGNOSTIC_SENSITIVE_KEY" in js
    assert "api[_-]?key" in js
    assert "github_pat_" in js
    assert '"/api/diagnostics"' in js
    assert '"/api/status"' in js
    assert "privacy_note" in js


def test_chat_font_preference_is_applied_to_message_container():
    js = (ROOT / "web" / "chat-enhancements.js").read_text(encoding="utf-8")
    assert 'box.style.fontSize=String(prefs.font)+"px"' in js
    assert 'prefs.font=Math.max(12,Math.min(19,Number(prefs.font)||14))' in js

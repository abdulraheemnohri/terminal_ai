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
    ids = re.findall(r'\\bid=["\\']([^"\\']+)["\\']', html)
    duplicates = sorted(element_id for element_id, count in Counter(ids).items() if count > 1)
    assert not duplicates, f"Duplicate dashboard element IDs break control wiring: {duplicates}"


def test_static_javascript_id_references_exist_in_dashboard():
    html = HTML_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    html_ids = set(re.findall(r'\\bid=["\\']([^"\\']+)["\\']', html))
    js_ids = set(re.findall(r'\\$\\(["\\']([^"\\']+)["\\']\\)', js))
    missing = sorted(js_ids - html_ids)
    assert not missing, f"JavaScript references missing dashboard element IDs: {missing}"


def test_label_targets_exist_in_dashboard():
    html = HTML_PATH.read_text(encoding="utf-8")
    ids = set(re.findall(r'\\bid=["\\']([^"\\']+)["\\']', html))
    targets = re.findall(r'<label\\b[^>]*\\bfor=["\\']([^"\\']+)["\\']', html)
    missing = sorted(set(targets) - ids)
    assert not missing, f"Labels reference missing dashboard controls: {missing}"

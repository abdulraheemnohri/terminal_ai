from __future__ import annotations

import json
from pathlib import Path

import pytest

from terminal_ai_runtime import AuditLedger


def test_audit_ledger_verifies_appended_chain(tmp_path: Path):
    ledger = AuditLedger(tmp_path / "audit.jsonl")
    ledger.append("session.started", "test", {"session": "one"})
    ledger.append("tool.reviewed", "operator", {"approved": False})
    assert ledger.verify() == (True, 2)


def test_audit_ledger_detects_modified_event(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    ledger = AuditLedger(path)
    ledger.append("session.started", "test", {"session": "one"})
    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["actor"] = "tampered"
    path.write_text(json.dumps(entry) + "\\n", encoding="utf-8")
    assert ledger.verify() == (False, 0)


def test_audit_ledger_malformed_json_fails_closed(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    ledger = AuditLedger(path)
    path.write_text('{"incomplete":\\n', encoding="utf-8")
    assert ledger.verify() == (False, 0)


def test_audit_ledger_refuses_append_after_tampering(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    ledger = AuditLedger(path)
    ledger.append("session.started", "test", {"session": "one"})
    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["details"] = {"session": "altered"}
    path.write_text(json.dumps(entry) + "\\n", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity check failed"):
        ledger.append("session.ended", "test", {})

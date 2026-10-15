import json
import pytest
from terminal_ai_runtime import (
    AdaptivePlanner, ApprovalGate, AuditLedger, PolicyDenied, ToolSpec,
    WorldModel, validate_skill_package, export_skill, import_skill, ActionEventBus,
)

def test_auto_approval_is_limited_to_explicit_low_risk_tools():
    gate = ApprovalGate(auto_execute=True)
    safe = gate.request(ToolSpec("browser.search", "read-only", "read", False, True), {}, "search")
    assert safe.status == "approved"
    risky = gate.request(ToolSpec("file.delete", "delete", "high", False, True), {}, "delete")
    assert risky.status == "pending"
    assert gate.decide(risky.request_id, True, actor="user").status == "approved"

def test_blocklist_wins_over_allowlist():
    gate = ApprovalGate(allowlist={"browser.search"}, blocklist={"browser.search"})
    with pytest.raises(PolicyDenied):
        gate.request(ToolSpec("browser.search", "search"), {}, "test")

def test_audit_hash_chain_detects_edits(tmp_path):
    path = tmp_path / "audit.jsonl"
    ledger = AuditLedger(path)
    ledger.append("tool.start", "agent", {"tool": "browser.search"})
    ledger.append("tool.result", "agent", {"ok": True})
    assert ledger.verify() == (True, 2)
    rows = path.read_text().splitlines()
    row = json.loads(rows[0]); row["actor"] = "tampered"
    rows[0] = json.dumps(row); path.write_text("\n".join(rows) + "\n")
    assert ledger.verify()[0] is False

def test_world_model_confidence_and_expiry():
    model = WorldModel()
    fact = model.observe("service", "status", "healthy", source="health-check",
                         confidence=5, ttl_seconds=30)
    assert fact.confidence == 1
    assert model.query("service")[0].value == "healthy"

def test_planner_requires_approval_for_external_effects():
    plan = AdaptivePlanner().plan("submit a form", complexity=2, risk="low",
                                  has_external_side_effects=True)
    assert plan.strategy == "plan-review-execute" and plan.needs_approval

def test_skill_package_is_declarative_and_untrusted(tmp_path):
    package = {"name": "safe workflow", "steps": [
        {"action": "observe", "description": "Inspect status"},
        {"action": "tool_request", "tool": "browser.search", "description": "Search"}]}
    validated = validate_skill_package(package)
    assert validated["trust"] == "untrusted-import-review-required"
    assert all(step["approval_required"] for step in validated["steps"])
    path = export_skill(package, tmp_path / "skill.json")
    assert import_skill(path)["name"] == "safe workflow"
    with pytest.raises(ValueError):
        validate_skill_package({"name": "bad", "steps": [{"action": "exec", "command": "unsafe"}]})

def test_event_bus_isolates_failed_subscriber():
    bus = ActionEventBus()
    bus.subscribe(lambda event: (_ for _ in ()).throw(RuntimeError("offline")))
    seen = []; bus.subscribe(seen.append)
    bus.publish("tool.start", "Searching", tool_name="browser.search")
    assert len(seen) == 1 and bus.history()[0]["summary"] == "Searching"

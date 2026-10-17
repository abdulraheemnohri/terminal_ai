from litestar.testing import TestClient

from app import app


def test_command_control_ui_and_policy_endpoints():
    with TestClient(app=app) as client:
        page = client.get("/command-control")
        policy = client.get("/api/control/policy")
        audit = client.get("/api/control/audit")
    assert page.status_code == 200
    assert "Command Control Center" in page.text
    assert "control-pending-list" in page.text
    assert policy.status_code == 200
    assert policy.json()["policy"]["auto_execute"] is False
    assert policy.json()["execution_enabled"] is False
    assert audit.status_code == 200
    assert audit.json()["integrity"]["valid"] is True


def test_pending_operation_approval_does_not_execute():
    with TestClient(app=app) as client:
        queued = client.post("/api/control/pending", json={
            "tool": "workspace", "operation": "inspect", "arguments": {"path": "README.md"}
        })
        assert queued.status_code == 201
        ident = queued.json()["operation"]["id"]
        approved = client.post(f"/api/control/pending/{ident}/review", json={"approve": True})
    assert approved.status_code == 201
    assert approved.json()["executed"] is False
    assert approved.json()["operation"]["status"] == "approved"


def test_skill_marketplace_rejects_invalid_package_and_exports_schema():
    with TestClient(app=app) as client:
        invalid = client.post("/api/control/skills/import", json={"format": "wrong", "version": 1, "skills": []})
        exported = client.get("/api/control/skills/export")
    assert invalid.status_code == 400
    assert exported.status_code == 200
    assert exported.json()["format"] == "terminal-ai-skills"
    assert exported.json()["version"] == 1


def test_workspace_execution_obeys_control_center_blocklist():
    with TestClient(app=app) as client:
        client.patch("/api/settings", json={"workspace_tools_enabled": True})
        response = client.post("/api/workspace/execute", json={
            "argv": ["rm", "-rf", "/"], "approved": True, "timeout": 2
        })
    assert response.status_code == 403
    assert "blocked" in response.json()["detail"].lower()


def test_yaml_skill_export_is_available():
    with TestClient(app=app) as client:
        response = client.get("/api/control/skills/export.yaml")
    assert response.status_code == 200
    assert "terminal-ai-skills" in response.text


def test_command_control_status_filter_includes_execution_lifecycle_states():
    with TestClient(app=app) as client:
        for status in ("pending", "approved", "rejected", "executing", "executed", "failed", "expired"):
            response = client.get(f"/api/control/pending?status={status}")
            assert response.status_code == 200
            assert response.json()["status"] == status
            assert response.json()["allowed_statuses"] == [
                "pending", "approved", "rejected", "executing", "executed", "failed", "expired"
            ]
        invalid = client.get("/api/control/pending?status=banana")
    assert invalid.status_code == 400

def test_audit_limit_is_bounded_and_reported():
    with TestClient(app=app) as client:
        normal = client.get("/api/control/audit?limit=250")
        too_small = client.get("/api/control/audit?limit=0")
        too_large = client.get("/api/control/audit?limit=1001")
    assert normal.status_code == 200
    assert normal.json()["limit"] == 250
    assert len(normal.json()["entries"]) <= 250
    assert too_small.status_code == 400
    assert too_large.status_code == 400


def test_audit_export_controls_are_present_and_wired_to_real_elements():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "web" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "app.js").read_text(encoding="utf-8")
    for element_id in (
        "control-audit-limit",
        "control-audit-refresh",
        "control-audit-export-json",
        "control-audit-export-csv",
        "control-audit-export-status",
        "feature-control-audit-list",
    ):
        assert f'id="{element_id}"' in html
    assert '$("feature-control-audit-list")' in js
    assert "exportControlAuditJSON" in js
    assert "exportControlAuditCSV" in js
    assert "fetched audit snapshot only" in js

from litestar.testing import TestClient
from app import app

def test_knowledge_api_persists_and_searches_without_provider():
    with TestClient(app=app) as client:
        created=client.post("/api/knowledge",json={"title":"test offline knowledge","content":"SQLite local memory search","tags":["offline"]})
        assert created.status_code==201
        ident=created.json()["item"]["id"]
        found=client.get("/api/knowledge?q=offline")
        assert found.status_code==200
        assert any(item["id"]==ident for item in found.json()["items"])
        searched=client.post("/api/knowledge/search",json={"query":"SQLite local memory"})
        assert searched.status_code==201
        assert searched.json()["offline"] is True
        deleted=client.post(f"/api/knowledge/{ident}/delete",json={})
        assert deleted.status_code==201

def test_workspace_api_requires_approval_for_writes_and_commands():
    with TestClient(app=app) as client:
        listing=client.get("/api/workspace")
        assert listing.status_code==200
        write=client.post("/api/workspace/write",json={"path":"test-should-not-exist.txt","content":"no"})
        assert write.status_code==403
        execute=client.post("/api/workspace/execute",json={"argv":["pwd"]})
        assert execute.status_code==403

def test_scheduler_api_validates_job_types():
    with TestClient(app=app) as client:
        bad=client.post("/api/scheduled-tasks",json={"name":"Unsafe","kind":"shell","interval_minutes":60})
        assert bad.status_code==400
        good=client.post("/api/scheduled-tasks",json={"name":"API test diagnostic","kind":"diagnostics","interval_minutes":60})
        assert good.status_code==201
        ident=good.json()["task"]["id"]
        assert client.patch(f"/api/scheduled-tasks/{ident}",json={"enabled":False}).status_code==200
        assert client.post(f"/api/scheduled-tasks/{ident}/delete",json={}).status_code==201

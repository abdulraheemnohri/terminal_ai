import pytest
from task_scheduler import TaskScheduler

def test_scheduler_persists_allowlisted_tasks(tmp_path):
    path=tmp_path/"tasks.sqlite3"
    scheduler=TaskScheduler(path)
    task=scheduler.create("Daily backup","backup_memory",1440)
    assert task["enabled"] is True
    assert TaskScheduler(path).list()[0]["id"]==task["id"]

def test_scheduler_rejects_unsafe_kind_and_interval(tmp_path):
    scheduler=TaskScheduler(tmp_path/"tasks.sqlite3")
    with pytest.raises(ValueError): scheduler.create("Run shell","shell",60)
    with pytest.raises(ValueError): scheduler.create("Too frequent","diagnostics",1)

def test_scheduler_toggle_delete(tmp_path):
    scheduler=TaskScheduler(tmp_path/"tasks.sqlite3")
    task=scheduler.create("Check","diagnostics",30)
    assert scheduler.toggle(task["id"],False)
    assert scheduler.list()[0]["enabled"] is False
    assert scheduler.delete(task["id"])

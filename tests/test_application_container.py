from application.container import RuntimeServices


def test_runtime_services_builds_long_lived_dependencies_in_given_roots(tmp_path):
    state_dir = tmp_path / "state"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    services = RuntimeServices.create(state_dir=state_dir, workspace_root=workspace_root)

    assert services.memory.path == state_dir.resolve() / "long_term_memory.sqlite3"
    assert services.scheduler.path == state_dir.resolve() / "scheduled_tasks.sqlite3"
    assert services.command_control.path == state_dir.resolve() / "command_control.sqlite3"
    assert services.workspace.workspace == workspace_root.resolve()
    assert (state_dir / "command_control.sqlite3").is_file()

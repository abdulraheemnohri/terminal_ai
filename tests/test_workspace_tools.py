import pytest
from workspace_tools import WorkspaceTools

def test_workspace_rejects_path_escape(tmp_path):
    tools=WorkspaceTools(tmp_path/"workspace")
    with pytest.raises(ValueError): tools.resolve("../secret.txt")

def test_write_requires_approval_and_stays_in_workspace(tmp_path):
    tools=WorkspaceTools(tmp_path/"workspace")
    with pytest.raises(PermissionError): tools.write_file("note.txt","hello")
    result=tools.write_file("notes/note.txt","hello",approved=True)
    assert result["path"]=="notes/note.txt"
    assert tools.read_file("notes/note.txt")=="hello"

def test_commands_require_approval_and_no_shell(tmp_path):
    tools=WorkspaceTools(tmp_path)
    with pytest.raises(PermissionError): tools.run_command(["pwd"])
    with pytest.raises(PermissionError): tools.run_command(["python","-c","print(1)"],approved=True)
    result=tools.run_command(["pwd"],approved=True)
    assert result["returncode"]==0

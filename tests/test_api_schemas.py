import pytest
from pydantic import ValidationError

from api_schemas import (
    ChatRequest, CommandPolicyPatch, QueueOperationRequest,
    ReviewOperationRequest, SkillPackageRequest, YAMLImportRequest,
)


def test_chat_request_is_bounded_and_rejects_empty_message():
    assert ChatRequest(message="hello").message == "hello"
    with pytest.raises(ValidationError):
        ChatRequest(message=" ")


def test_command_policy_accepts_names_not_shell_fragments():
    assert CommandPolicyPatch(allowlist=["ls", "python"]).allowlist == ["ls", "python"]
    with pytest.raises(ValidationError):
        CommandPolicyPatch(allowlist=["ls; rm -rf /"])


def test_operation_request_is_structured_and_bounded():
    request = QueueOperationRequest(tool="workspace", operation="inspect", arguments={"path": "README.md"})
    assert request.arguments["path"] == "README.md"
    with pytest.raises(ValidationError):
        QueueOperationRequest(tool="shell && rm", operation="run")


def test_review_request_requires_boolean_approval():
    assert ReviewOperationRequest(approve=True, note="checked").approve is True
    with pytest.raises(ValidationError):
        ReviewOperationRequest(approve="yes")


def test_skill_package_requires_procedure_text_only():
    package = SkillPackageRequest.model_validate({
        "format": "terminal-ai-skills", "version": 1,
        "skills": [{"name": "Checklist", "steps": ["Inspect", "Validate"]}],
    })
    assert package.skills[0].name == "Checklist"
    with pytest.raises(ValidationError):
        SkillPackageRequest.model_validate({"format": "wrong", "version": 1, "skills": []})


def test_yaml_import_payload_has_size_limit():
    assert YAMLImportRequest(content="format: terminal-ai-skills").content
    with pytest.raises(ValidationError):
        YAMLImportRequest(content="x" * 200_001)

from agentic_features import (
    needs_planning,
    persona_instruction,
    planning_instruction,
    recovery_instruction,
    validate_tool_calls,
)


SCHEMA = [
    {"name": "read_file", "args": {"path": "string", "max_bytes": "int"}},
    {"name": "now", "args": {}},
]


def test_planning_is_selective_and_keeps_scratchpad_private():
    assert needs_planning("Please implement and debug this architecture.")
    assert planning_instruction("Please implement and debug this architecture.")
    assert "do not reveal hidden chain-of-thought" in planning_instruction(
        "Please implement and debug this architecture."
    )
    assert planning_instruction("hello") == ""


def test_persona_instruction_has_language_and_context_guidance():
    value = persona_instruction("technical")
    assert "technical language" in value
    assert "conversation context" in value
    assert "Reply in the user's language" in value


def test_tool_validation_accepts_valid_calls_and_rejects_unknown_or_bad_types():
    result = validate_tool_calls([
        {"name": "read_file", "args": {"path": "README.md", "max_bytes": 100}},
        {"name": "read_file", "args": {"path": 12}},
        {"name": "shell", "args": {"cmd": "whoami"}},
        {"name": "now", "args": {"extra": True}},
    ], SCHEMA)
    assert result.accepted == [{"name": "read_file", "args": {"path": "README.md", "max_bytes": 100}}]
    assert len(result.rejected) == 3


def test_tool_validation_can_enforce_execution_mode_allowlist():
    result = validate_tool_calls(
        [{"name": "read_file", "args": {"path": "README.md"}}],
        SCHEMA,
        allowed_names={"now"},
    )
    assert not result.accepted
    assert "not permitted" in result.rejected[0]


def test_recovery_prompt_does_not_echo_exception_message():
    value = recovery_instruction(RuntimeError("secret token=do-not-leak"), 1, 2)
    assert "RuntimeError" in value
    assert "do-not-leak" not in value
    assert "verified" in value

def test_parse_tool_calls_supports_nested_json():
    from terminal_ai import parse_tool_calls

    text = '<tool_call>{"name":"remember","args":{"key":"profile","value":{"nested":[1,2]}}}</tool_call>'
    calls = parse_tool_calls(text)
    assert calls == [{"name": "remember", "args": {"key": "profile", "value": {"nested": [1, 2]}}}]

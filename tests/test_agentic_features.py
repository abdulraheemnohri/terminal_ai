from agentic_features import (
    needs_planning,
    persona_instruction,
    planning_instruction,
    recovery_instruction,
    validate_tool_calls,
    parse_json_tool_payload,
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
    assert planning_instruction("Please implement this architecture.", enabled=False) == ""


def test_persona_instruction_has_language_and_context_guidance():
    value = persona_instruction("technical")
    assert "technical language" in value
    assert "conversation context" in value
    assert "Reply in the user's language" in value


def test_persona_fallback_and_roleplay_safety():
    assert "Be helpful" in persona_instruction("not-a-real-persona")
    roleplay = persona_instruction("roleplay")
    assert "fictional character" in roleplay
    assert "real person" in roleplay
    assert "real-world facts" in roleplay


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


def test_tool_validation_rejects_non_object_calls_and_args():
    result = validate_tool_calls(
        [None, {"name": "read_file", "args": ["README.md"]}],
        SCHEMA,
    )
    assert not result.accepted
    assert len(result.rejected) == 2
    assert "expected an object" in result.rejected[0]
    assert "args must be an object" in result.rejected[1]


def test_tool_validation_does_not_treat_bool_as_int_or_number():
    result = validate_tool_calls(
        [
            {"name": "read_file", "args": {"path": "README.md", "max_bytes": True}},
            {"name": "read_file", "args": {"path": "README.md", "max_bytes": 3.5}},
        ],
        SCHEMA,
    )
    assert not result.accepted
    assert len(result.rejected) == 2
    assert all("invalid type" in message for message in result.rejected)


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


def test_parse_json_tool_payload_requires_standalone_json_object():
    assert parse_json_tool_payload('{"name":"now","args":{}}') == {
        "name": "now",
        "args": {},
    }
    assert parse_json_tool_payload('prefix {"name":"now"}') is None
    assert parse_json_tool_payload("[1, 2]") is None
    assert parse_json_tool_payload('"string"') is None
    assert parse_json_tool_payload("{broken") is None
    assert parse_json_tool_payload(None) is None

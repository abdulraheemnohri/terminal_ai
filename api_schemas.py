"""Pydantic v2 request contracts for Terminal AI's public API."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class APIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class CommandPolicyPatch(APIRequest):
    auto_execute: bool | None = None
    tool_auto_execute: dict[str, bool] | None = Field(default=None, max_length=100)
    allowlist: list[str] | None = Field(default=None, max_length=100)
    blocklist: list[str] | None = Field(default=None, max_length=100)

    @field_validator("allowlist", "blocklist")
    @classmethod
    def validate_commands(cls, values: list[str] | None) -> list[str] | None:
        import re
        if values is not None and any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", item) for item in values):
            raise ValueError("Command entries must be executable names, not command strings.")
        return values

    @field_validator("tool_auto_execute")
    @classmethod
    def validate_tool_names(cls, values: dict[str, bool] | None) -> dict[str, bool] | None:
        import re
        if values is not None and any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", key) for key in values):
            raise ValueError("Tool names must be simple identifiers.")
        return values

class QueueOperationRequest(APIRequest):
    tool: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    operation: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    arguments: dict[str, Any] = Field(default_factory=dict)

class ReviewOperationRequest(APIRequest):
    approve: bool
    note: str = Field(default="", max_length=500)

class SkillDefinition(APIRequest):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(default="1.0.0", min_length=1, max_length=40)
    description: str = Field(default="", max_length=1000)
    steps: list[str] = Field(min_length=1, max_length=30)

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, steps: list[str]) -> list[str]:
        if any(not step.strip() or len(step) > 1000 for step in steps):
            raise ValueError("Each skill step must be non-empty and at most 1000 characters.")
        return steps

class SkillPackageRequest(APIRequest):
    format: Literal["terminal-ai-skills"]
    version: Literal[1]
    skills: list[SkillDefinition] = Field(min_length=1, max_length=100)

class YAMLImportRequest(APIRequest):
    content: str = Field(min_length=1, max_length=200_000)

class ChatRequest(APIRequest):
    message: str = Field(min_length=1, max_length=20_000)

class MemoryWriteRequest(APIRequest):
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=4_000)


class KnowledgeCreateRequest(APIRequest):
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=20000)
    kind: str = Field(default="note", min_length=1, max_length=40)
    tags: list[str] = Field(default_factory=list, max_length=30)
    pinned: bool = False

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        if any(not tag.strip() or len(tag) > 80 for tag in tags):
            raise ValueError("Tags must be non-empty and at most 80 characters.")
        return tags


class KnowledgeSearchRequest(APIRequest):
    query: str = Field(default="", max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)

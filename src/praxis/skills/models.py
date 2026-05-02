"""Skill subsystem Pydantic models."""

from __future__ import annotations

import re
from pathlib import Path  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class SkillFrontmatter(BaseModel):
    """Validated frontmatter from a SKILL.md file."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    name: str
    category: str
    description: str
    when_to_use: str = ""
    requires_toolsets: list[str] = []
    fallback_for_toolsets: list[str] = []
    required_engagement_fields: list[str] = []
    human_curated: bool = True
    status: Literal["draft", "published"] = "published"

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9-]+", v):
            msg = f"Skill name must match [a-z0-9-]+, got: {v!r}"
            raise ValueError(msg)
        return v

    @field_validator("category")
    @classmethod
    def _validate_category(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9_-]+", v):
            msg = f"Category must match [a-z0-9_-]+, got: {v!r}"
            raise ValueError(msg)
        return v


class Skill(BaseModel):
    """A loaded skill with parsed frontmatter and file inventory."""

    model_config = ConfigDict(extra="forbid")

    frontmatter: SkillFrontmatter
    body: str
    path: Path
    references: list[Path] = []
    templates: list[Path] = []
    examples: list[Path] = []
    source: Literal["bundled", "user", "engagement"]

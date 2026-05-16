"""Models for generated Praxis artifacts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ArtifactResult(BaseModel):
    """Result from generating or listing an artifact."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    schema_version: Literal[1] = 1
    artifact_kind: str
    path: Path
    content: str
    created_at: datetime
    sufficiency_verdict: str | None = None
    sufficiency_report_path: Path | None = None

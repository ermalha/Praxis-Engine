"""Email message models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ParsedMessage(BaseModel):
    """An email message parsed from the inbox."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    message_id: str
    in_reply_to: str | None = None
    from_addr: str
    to_addrs: list[str] = []
    subject: str
    body: str
    date: datetime | None = None

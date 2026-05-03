"""Match incoming emails to SEND_MESSAGE work-items."""

from __future__ import annotations

from pathlib import Path

import structlog

from praxis.integrations.email.models import ParsedMessage
from praxis.workqueue import WorkItemStatus, WorkQueueRepo

logger = structlog.get_logger()


def match_replies(
    messages: list[ParsedMessage],
    engagement_path: Path,
) -> list[tuple[ParsedMessage, str]]:
    """Match incoming messages against recent SEND_MESSAGE work-items.

    Returns a list of (message, work_item_id) pairs for messages that
    appear to be replies to outbound messages we sent.
    """
    repo = WorkQueueRepo(engagement_path)
    all_done = repo.list(status=WorkItemStatus.DONE)
    items = [i for i in all_done if i.type == "send_message"]

    matches: list[tuple[ParsedMessage, str]] = []
    for msg in messages:
        for item in items:
            if _is_reply(msg, item):
                matches.append((msg, item.id))
                logger.info(
                    "email.reply_matched",
                    message_id=msg.message_id,
                    work_item_id=item.id,
                )
                break

    return matches


def _is_reply(msg: ParsedMessage, item) -> bool:
    """Heuristic: does this message look like a reply to the work-item?"""
    payload = item.payload
    if not payload:
        return False

    recipient = payload.get("recipient", "")
    if not recipient:
        return False

    return recipient.lower() in msg.from_addr.lower()

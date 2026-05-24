"""Compact engagement-state digest for priming LLM-facing commands.

Used by ``praxis ask -e <engagement>`` (and any other command that wants a
read-only summary of an engagement) to inject just enough context that the
model can reason about the engagement without hallucinating.

D-059: thin wrapper around :func:`praxis.engagement.snapshot.render_snapshot_for_llm`
with ``purpose="ask"``. The detailed formatting logic now lives in
``snapshot.py``; this module keeps the legacy ``(name, text)`` return
shape so existing callers in ``cli/ask_cmd.py`` are untouched.
"""

from __future__ import annotations

from pathlib import Path

from praxis.engagement.snapshot import build_engagement_snapshot, render_snapshot_for_llm


def build_engagement_digest(eng_path: Path) -> tuple[str, str]:
    """Build a compact text digest of an engagement's state for ``ask``.

    Returns ``(engagement_name, digest_text)``. The digest format is owned by
    :func:`praxis.engagement.snapshot.render_snapshot_for_llm` (purpose="ask")
    — see that function for section ordering, caps, and truncation policy.
    """
    snapshot = build_engagement_snapshot(eng_path)
    return snapshot.name, render_snapshot_for_llm(snapshot, purpose="ask")

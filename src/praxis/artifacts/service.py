"""State-grounded artifact generation service."""

from __future__ import annotations

import contextlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from praxis.audit import emit
from praxis.config.models import ProfileConfig
from praxis.transport import ChatRequest, Message, Transport

from .models import ArtifactResult

_ARTIFACT_DIRS = ("stories", "specs", "reports", "matrices")

# D-037: artifact_kind (generate) → artifact_kind (check). Unknown kinds match
# their own name (exact). Extend here when adding new artifact kinds.
_ARTIFACT_TO_CHECK_KIND = {
    "scope-brief": "spec",
    "backlog": "backlog",
    "traceability": "traceability",
}


def _find_latest_sufficiency_for(
    engagement_path: Path, artifact_kind: str
) -> tuple[str, Path] | None:
    """Return ``(verdict, report_path)`` for the most recent matching sufficiency
    report, or ``None`` if no report matches.

    Matching: report's ``artifact_kind`` must equal the value mapped via
    ``_ARTIFACT_TO_CHECK_KIND`` (or the artifact_kind itself if not mapped).
    "Most recent" uses the report's ``generated_at`` field; file mtime is a
    fallback if the field is absent or unreadable.
    """
    target_kind = _ARTIFACT_TO_CHECK_KIND.get(artifact_kind, artifact_kind)
    reports_dir = engagement_path / ".praxis" / "state" / "sufficiency-reports"
    if not reports_dir.is_dir():
        return None

    best: tuple[str, str, Path] | None = None  # (sort_key, verdict, path)
    for report_file in reports_dir.glob("*.json"):
        with contextlib.suppress(json.JSONDecodeError, OSError, KeyError):
            data = json.loads(report_file.read_text(encoding="utf-8"))
            if data.get("artifact_kind") != target_kind:
                continue
            verdict = data.get("verdict")
            if not isinstance(verdict, str):
                continue
            sort_key = str(data.get("generated_at") or report_file.stat().st_mtime)
            if best is None or sort_key > best[0]:
                best = (sort_key, verdict, report_file.resolve())

    if best is None:
        return None
    return best[1], best[2]


def generate_artifact(
    *,
    engagement_path: Path,
    profile: ProfileConfig,
    model: str,
    transport: Transport,
    artifact_kind: str,
    prompt: str,
    output_dir: str = "reports",
) -> ArtifactResult:
    """Generate an engagement-grounded Markdown artifact and write it to disk."""
    now = datetime.now(UTC)
    grounded_prompt = build_artifact_prompt(engagement_path, artifact_kind, prompt)
    response = transport.chat(
        ChatRequest(
            model=model,
            messages=[Message(role="user", content=grounded_prompt)],
        )
    )
    content = response.content
    directory = _safe_artifact_dir(engagement_path, output_dir)
    path = directory / f"{_slug(artifact_kind)}-{now.strftime('%Y%m%dT%H%M%SZ')}.md"
    path.write_text(content, encoding="utf-8")
    resolved = path.resolve()
    emit(
        "artifact.created",
        component="artifacts",
        engagement_path=engagement_path,
        artifact_kind=artifact_kind,
        path=str(resolved),
        profile=profile.name,
    )
    binding = _find_latest_sufficiency_for(engagement_path, artifact_kind)
    return ArtifactResult(
        artifact_kind=artifact_kind,
        path=resolved,
        content=content,
        created_at=now,
        sufficiency_verdict=binding[0] if binding else None,
        sufficiency_report_path=binding[1] if binding else None,
    )


def list_artifacts(engagement_path: Path) -> list[ArtifactResult]:
    """List Markdown/text artifacts under the engagement artifact directories."""
    root = engagement_path / ".praxis" / "artifacts"
    results: list[ArtifactResult] = []
    for kind in _ARTIFACT_DIRS:
        directory = root / kind
        if not directory.exists():
            continue
        for path in sorted(directory.glob("**/*")):
            if not path.is_file():
                continue
            stat = path.stat()
            results.append(
                ArtifactResult(
                    artifact_kind=kind,
                    path=path.resolve(),
                    content=path.read_text(encoding="utf-8", errors="replace"),
                    created_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                )
            )
    return results


def build_artifact_prompt(engagement_path: Path, artifact_kind: str, prompt: str) -> str:
    """Build a compact prompt from persisted engagement state.

    D-059: the engagement-state portion of the prompt is now produced by
    :func:`praxis.engagement.snapshot.render_snapshot_for_llm` with
    ``purpose="artifact"``. This function keeps ownership of the LLM
    system instruction + artifact-kind + user-request framing.
    """
    from praxis.engagement.snapshot import build_engagement_snapshot, render_snapshot_for_llm

    snapshot = build_engagement_snapshot(engagement_path)
    state = render_snapshot_for_llm(snapshot, purpose="artifact")
    return (
        "You are Praxis, an IT business analyst. Generate the requested artifact using ONLY "
        "the persisted engagement facts below. Do not switch projects. Do not invent firm "
        "requirements; mark unknowns and assumptions explicitly. Include a concise 'Artifact "
        "source note' that says it was generated from the engagement model.\n\n"
        f"Artifact kind: {artifact_kind}\n"
        f"User request: {prompt}\n\n"
        "Persisted engagement model:\n"
        f"{state}\n"
    )


def _safe_artifact_dir(engagement_path: Path, output_dir: str) -> Path:
    kind = output_dir if output_dir in _ARTIFACT_DIRS else "reports"
    directory = engagement_path / ".praxis" / "artifacts" / kind
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "artifact"

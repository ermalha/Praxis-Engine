"""State-grounded artifact generation service."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from praxis.audit import emit
from praxis.config.loader import load_engagement_config
from praxis.config.models import ProfileConfig
from praxis.engagement.repos.assumptions import AssumptionsConstraintsRepo
from praxis.engagement.repos.decisions import DecisionRepo
from praxis.engagement.repos.glossary import GlossaryRepo
from praxis.engagement.repos.questions import OpenQuestionsRepo
from praxis.engagement.repos.risks import RiskRepo
from praxis.engagement.repos.stakeholders import StakeholderRepo
from praxis.transport import ChatRequest, Message, Transport

from .models import ArtifactResult

_ARTIFACT_DIRS = ("stories", "specs", "reports", "matrices")


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
    return ArtifactResult(
        artifact_kind=artifact_kind,
        path=resolved,
        content=content,
        created_at=now,
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
    """Build a compact prompt from persisted engagement state."""
    eng = load_engagement_config(engagement_path)
    sections = [
        f"Engagement: {eng.name}",
        f"Methodology: {eng.methodology.value}",
        _stakeholder_section(engagement_path),
        _glossary_section(engagement_path),
        _questions_section(engagement_path),
        _assumptions_constraints_section(engagement_path),
        _risks_section(engagement_path),
        _decisions_section(engagement_path),
    ]
    state = "\n\n".join(section for section in sections if section.strip())
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


def _stakeholder_section(path: Path) -> str:
    items = StakeholderRepo(path).list_all()
    lines = [f"- {item.name}: {item.role} [{item.id}]" for item in items]
    return "Stakeholders:\n" + "\n".join(lines) if lines else "Stakeholders: none"


def _glossary_section(path: Path) -> str:
    terms = GlossaryRepo(path).load().terms
    lines = [f"- {term.term}: {term.definition}" for term in terms]
    return "Glossary:\n" + "\n".join(lines) if lines else "Glossary: none"


def _questions_section(path: Path) -> str:
    questions = OpenQuestionsRepo(path).list_all()
    lines = [f"- [{q.status}] {q.question} ({q.priority})" for q in questions]
    return "Questions:\n" + "\n".join(lines) if lines else "Questions: none"


def _assumptions_constraints_section(path: Path) -> str:
    repo = AssumptionsConstraintsRepo(path)
    assumptions = [f"- {item.statement}" for item in repo.list_assumptions()]
    constraints = [
        f"- [{item.constraint_type}] {item.statement}"
        for item in repo.list_constraints()
    ]
    return (
        "Assumptions:\n"
        + ("\n".join(assumptions) if assumptions else "none")
        + "\n\nConstraints:\n"
        + ("\n".join(constraints) if constraints else "none")
    )


def _risks_section(path: Path) -> str:
    risks = RiskRepo(path).list_all()
    lines = [f"- [{r.likelihood}/{r.impact}] {r.title}: {r.description}" for r in risks]
    return "Risks:\n" + "\n".join(lines) if lines else "Risks: none"


def _decisions_section(path: Path) -> str:
    decisions = DecisionRepo(path).list_all()
    lines = [f"- [{d.status}] {d.title}: {d.decision}" for d in decisions]
    return "Decisions:\n" + "\n".join(lines) if lines else "Decisions: none"

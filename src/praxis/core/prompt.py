"""System prompt builder — deterministic, cache-stable."""

from __future__ import annotations

from pathlib import Path

from praxis.config.models import EngagementConfig, ProfileConfig
from praxis.skills import SkillRegistry

_PERSONALITY = """\
You are Praxis, an AI business analyst assistant. You help with requirements \
elicitation, stakeholder management, decision tracking, and project analysis.

Be precise, structured, and proactive. Use the engagement model tools to \
read and update project knowledge. Always cite your sources when referencing \
engagement data."""

_TOOL_GUIDANCE = """\
When using tools:
- Read before you write. Check existing data before adding duplicates.
- Use specific search queries for glossary and session search.
- For file operations, paths are relative to the engagement artifacts directory.
- Dangerous tools (writes, deletes) require human approval."""


def build_system_prompt(
    *,
    profile: ProfileConfig,
    engagement: EngagementConfig | None = None,
    engagement_path: Path | None = None,
    skill_registry: SkillRegistry | None = None,
) -> str:
    """Build the system prompt from layered sources.

    The output is deterministic for the same inputs — no time-varying content.
    This enables prompt caching on providers that support it.
    """
    sections: list[str] = []

    # 1. Personality
    sections.append(_PERSONALITY)

    # 2. Engagement summary
    if engagement is not None:
        eng_section = f"Active engagement: **{engagement.name}**"
        if engagement.methodology.value != "none":
            eng_section += f" (methodology: {engagement.methodology.value})"
        sections.append(eng_section)

    # 3. Skill index (level 0: name + description)
    if skill_registry is not None:
        skills = skill_registry.list_skills(only_active=True)
        if skills:
            lines = ["Available skills:"]
            for s in skills:
                lines.append(f"- **{s.frontmatter.name}**: {s.frontmatter.description}")
            sections.append("\n".join(lines))

    # 4. Tool use guidance
    sections.append(_TOOL_GUIDANCE)

    # 5. Engagement model quick refs
    if engagement_path is not None:
        refs = _engagement_quick_refs(engagement_path)
        if refs:
            sections.append(refs)

    # 6. User preferences
    if profile.display_name:
        sections.append(f"User: {profile.display_name}")

    return "\n\n".join(sections)


def _engagement_quick_refs(engagement_path: Path) -> str | None:
    """Build quick reference counts from the engagement model.

    Returns None if no engagement data is found.
    """
    praxis_dir = engagement_path / ".praxis" / "engagement"
    if not praxis_dir.is_dir():
        return None

    lines: list[str] = ["Engagement model:"]

    # Count items in YAML files without importing repos (keep prompt builder fast)
    import yaml

    counts: list[tuple[str, str, str]] = [
        ("glossary.yaml", "terms", "glossary terms"),
        ("stakeholders.yaml", "stakeholders", "stakeholders"),
        ("open-questions.yaml", "questions", "open questions"),
        ("risks.yaml", "risks", "risks"),
    ]

    for filename, key, label in counts:
        path = praxis_dir / filename
        if path.exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                items = data.get(key, [])
                if items:
                    lines.append(f"- {len(items)} {label}")
            except Exception:  # noqa: BLE001
                pass

    # Count decision files
    decisions_dir = praxis_dir / "decisions"
    if decisions_dir.is_dir():
        count = len(list(decisions_dir.glob("*.md")))
        if count:
            lines.append(f"- {count} decisions (ADRs)")

    if len(lines) == 1:
        return None
    return "\n".join(lines)

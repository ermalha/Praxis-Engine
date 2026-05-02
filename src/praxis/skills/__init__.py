"""Praxis skills subsystem — progressive-disclosure skill format and registry."""

# Auto-register skill tools when the package is imported
import praxis.skills.tools as _tools  # noqa: F401
from praxis.skills.loader import load_skills, parse_skill_md
from praxis.skills.manage import create_skill, delete_skill, patch_skill, promote_skill
from praxis.skills.models import Skill, SkillFrontmatter
from praxis.skills.registry import SkillRegistry

__all__ = [
    "Skill",
    "SkillFrontmatter",
    "SkillRegistry",
    "create_skill",
    "delete_skill",
    "load_skills",
    "parse_skill_md",
    "patch_skill",
    "promote_skill",
]

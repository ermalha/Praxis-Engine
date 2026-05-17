"""Praxis engagement subsystem — typed memory for the business analyst agent."""

# Auto-register engagement tools when the package is imported
import praxis.engagement.tools as _tools  # noqa: F401
from praxis.engagement.digest import build_engagement_digest
from praxis.engagement.models import (
    Assumption,
    AssumptionsAndConstraints,
    Constraint,
    ContactChannel,
    Decision,
    Glossary,
    GlossaryTerm,
    Milestone,
    OpenQuestion,
    OpenQuestions,
    Risk,
    RiskRegister,
    Stakeholder,
    StakeholderMap,
    System,
    SystemLandscape,
    Timeline,
)
from praxis.engagement.repos import (
    AssumptionsConstraintsRepo,
    DecisionRepo,
    GlossaryRepo,
    OpenQuestionsRepo,
    RiskRepo,
    StakeholderRepo,
    SystemLandscapeRepo,
    TimelineRepo,
)

__all__ = [
    "Assumption",
    "AssumptionsAndConstraints",
    "AssumptionsConstraintsRepo",
    "Constraint",
    "ContactChannel",
    "Decision",
    "DecisionRepo",
    "Glossary",
    "GlossaryRepo",
    "GlossaryTerm",
    "Milestone",
    "OpenQuestion",
    "OpenQuestions",
    "OpenQuestionsRepo",
    "Risk",
    "RiskRegister",
    "RiskRepo",
    "Stakeholder",
    "StakeholderMap",
    "StakeholderRepo",
    "System",
    "SystemLandscape",
    "SystemLandscapeRepo",
    "Timeline",
    "TimelineRepo",
    "build_engagement_digest",
]

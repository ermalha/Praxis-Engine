"""Engagement subcommands.

Previously a single 1059-line ``engagement_cmd.py``; split per-entity in
D-064 to lower the maintenance-hotspot risk Hermes flagged in review
item #7. Each entity module defines its own ``<entity>_app`` Typer sub-
app; this ``__init__`` composes them all under ``engagement_app`` so the
CLI-registration shape from ``praxis.cli`` is unchanged.

Source ordering matches the original file: glossary → stakeholder →
decision → question → system → risk → timeline → assumption →
constraint. Help output and command surface are byte-identical.
"""

from __future__ import annotations

import typer

from .assumptions import assumption_app
from .constraints import constraint_app
from .decisions import decision_app
from .glossary import glossary_app
from .questions import question_app
from .risks import risk_app
from .stakeholders import stakeholder_app
from .systems import system_app
from .timeline import timeline_app

engagement_app = typer.Typer(name="engagement", help="Manage the engagement model.")

engagement_app.add_typer(glossary_app)
engagement_app.add_typer(stakeholder_app)
engagement_app.add_typer(decision_app)
engagement_app.add_typer(question_app)
engagement_app.add_typer(system_app)
engagement_app.add_typer(risk_app)
engagement_app.add_typer(timeline_app)
engagement_app.add_typer(assumption_app)
engagement_app.add_typer(constraint_app)

__all__ = ["engagement_app"]

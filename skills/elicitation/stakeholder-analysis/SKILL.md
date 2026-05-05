---
name: stakeholder-analysis
category: elicitation
description: Identify, classify, and map stakeholders using RACI, Salience, and Influence-Interest models.
when_to_use: |
  At engagement start to build the initial stakeholder map, or when new
  stakeholders are discovered and need classification for communication
  and engagement planning.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: published
schema_version: 1
---

# Stakeholder Analysis

## Purpose

Knowing who matters, how much, and why is foundational. This skill guides
you through stakeholder identification, classification, and ongoing tracking
so you engage the right people at the right level.

## Procedure

### 1. Identify stakeholders

Sources for discovery:
- Org charts and team structures
- Project sponsors and governance boards
- End users and their representatives
- Regulatory and compliance contacts
- Technical SMEs and architects
- Operations and support teams
- External partners and vendors

Ask: "Who is affected by the outcome? Who can block it? Who funds it?"

### 2. Classify using models

#### Influence-Interest Grid

Plot stakeholders on two axes:
- **Influence** (ability to affect outcomes): Low → High
- **Interest** (degree of concern): Low → High

Quadrants:
- High Influence / High Interest → **Manage Closely** (key players)
- High Influence / Low Interest → **Keep Satisfied** (keep informed, don't overload)
- Low Influence / High Interest → **Keep Informed** (regular updates)
- Low Influence / Low Interest → **Monitor** (minimal effort)

#### Salience Model (Mitchell, Agle, Wood)

Three attributes: Power, Legitimacy, Urgency. Stakeholders with all three are
"definitive" and demand immediate attention.

#### RACI per deliverable

For each major deliverable or decision, assign:
- **R**esponsible — does the work
- **A**ccountable — single person who owns the decision
- **C**onsulted — provides input before decision
- **I**nformed — told after decision

### 3. Document in the engagement model

For each stakeholder, capture:
- Name, role, department
- Classification (grid quadrant)
- Communication preference (email, meeting, async)
- Decision authority scope
- Key concerns and motivations

### 4. Review and update

Stakeholder maps are living documents:
- Review quarterly or at phase boundaries
- Add new stakeholders as they emerge
- Reclassify as influence/interest shifts
- Archive stakeholders who leave the project

## Pitfalls

1. **Missing the quiet stakeholders** — Absence from meetings doesn't mean absence of influence. Seek out the informal power holders.
2. **Treating RACI as static** — As scope evolves, so do responsibilities. Review regularly.
3. **Single-A violation** — Every deliverable must have exactly one Accountable person. Multiple A's means no one is accountable.
4. **Confusing influence with seniority** — A junior developer who maintains a critical system may have more practical influence than a VP.

## Verification

- [ ] All quadrants of the influence-interest grid are populated
- [ ] Every major deliverable has a RACI assignment
- [ ] No deliverable has zero or multiple Accountable persons
- [ ] Communication preferences are documented for key players
- [ ] The map has been validated with at least one sponsor

## BABOK Reference

Derived from BABOK v3 Technique 10.42 (Stakeholder List, Map, or Personas) and 10.36 (RACI Matrix).

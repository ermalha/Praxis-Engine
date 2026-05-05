---
name: invest-story-writing
category: requirements
description: Draft and refine user stories that satisfy INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable).
when_to_use: |
  When capturing requirements as user stories for an agile backlog, or when
  refining existing stories that are too large, coupled, or vague.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: published
schema_version: 1
---

# INVEST Story Writing

## Purpose

User stories are the primary unit of work in agile delivery. A story that
satisfies INVEST is implementable, testable, and negotiable — it can flow
through a sprint without blocking other work or requiring rework.

## Procedure

### 1. Start with the user's goal

Use the canonical format:

> As a [role], I want [capability] so that [benefit].

The "so that" clause is mandatory — it establishes value and enables negotiation.

### 2. Apply INVEST criteria

Score each story against:

- **I — Independent**: Can it be developed without depending on other stories? If not, split or reorder.
- **N — Negotiable**: Is it a conversation starter, not a contract? Avoid over-specification.
- **V — Valuable**: Does it deliver user or business value? Technical tasks need a value wrapper.
- **E — Estimable**: Can the team estimate effort? If not, the story needs a spike or decomposition.
- **S — Small**: Can it fit in one sprint? If not, split by workflow step, data variation, or operation (CRUD).
- **T — Testable**: Can you write acceptance criteria? If "I'll know it when I see it," it's not testable.

### 3. Split stories that fail INVEST

Common splitting patterns:
- **By workflow step**: "User registers" → "User enters email" + "System sends verification" + "User confirms"
- **By data variation**: "Import data" → "Import CSV" + "Import Excel" + "Import API"
- **By operation**: "Manage users" → "Create user" + "Edit user" + "Deactivate user"
- **By business rule**: "Calculate price" → "Apply base price" + "Apply discount" + "Apply tax"
- **By role**: "View dashboard" → "Manager sees team metrics" + "IC sees personal metrics"

### 4. Add acceptance criteria

Every story needs testable acceptance criteria (see acceptance-criteria-gwt skill).
Aim for 3-7 criteria per story.

### 5. Validate with Product Owner

Confirm:
- Value is understood and prioritized
- Scope is clear (what's in/out)
- Dependencies are identified
- Team can estimate with confidence

## Pitfalls

1. **Missing "so that"** — Without the value clause, you can't negotiate scope or prioritize.
2. **Technical stories masquerading as user stories** — "As a developer, I want to refactor the DB" isn't a user story. Wrap in user value or make it a technical task.
3. **Epic-sized stories** — "As a user, I want to manage my account" is an epic. Apply splitting patterns.
4. **Over-specification** — Stories with 20 acceptance criteria are mini-specs. Split the story instead.

## Verification

- [ ] Story follows "As a / I want / so that" format
- [ ] All six INVEST criteria score positively
- [ ] Story fits in one sprint (team confirms)
- [ ] 3-7 acceptance criteria attached
- [ ] Product Owner has validated value and priority

## BABOK Reference

Derived from BABOK v3 Technique 10.47 (User Stories) and the INVEST framework by Bill Wake.

---
name: adr-authoring
category: decision
description: Write Architecture Decision Records with context, decision, consequences, alternatives, and proper numbering.
when_to_use: |
  When a significant technical or architectural decision needs to be documented
  for future reference, team alignment, or governance compliance.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: published
schema_version: 1
---

# ADR Authoring

## Purpose

Architecture Decision Records capture the WHY behind significant decisions.
When someone asks "why did we choose X?" six months later, the ADR provides
context, rationale, alternatives considered, and expected consequences — so
the decision can be understood without tribal knowledge.

## Procedure

### 1. Identify decision-worthy moments

Not every choice needs an ADR. Write one when:
- The decision is hard to reverse (infrastructure, data format, framework)
- Multiple valid options exist and the choice isn't obvious
- The decision affects multiple teams or has long-term implications
- Someone will ask "why?" in 6 months

### 2. Write the ADR sections

#### Title
Use the format: "ADR-NNN: [Verb] [Subject]"
Example: "ADR-003: Use PostgreSQL for event storage"

#### Status
One of: Proposed, Accepted, Deprecated, Superseded

#### Context
What forces are at play? What problem are we solving?
- Business constraints (budget, timeline, compliance)
- Technical constraints (scale, performance, existing tech)
- Team constraints (expertise, capacity)

Be factual, not persuasive. State the situation neutrally.

#### Decision
State the decision clearly in one sentence:
"We will use [X] for [purpose]."

Then elaborate with key design choices.

#### Consequences
Both positive and negative:
- What becomes easier?
- What becomes harder?
- What new risks or technical debt does this introduce?
- What options does this close off?

#### Alternatives Considered
For each alternative:
- What was it?
- Why was it rejected?
- What would have made us choose it instead?

### 3. Number and file

- Sequential numbering: ADR-001, ADR-002, ...
- Store in a predictable location (e.g., `docs/decisions/`)
- Never delete — mark as Deprecated or Superseded
- Link superseding ADR: "Superseded by ADR-015"

### 4. Review and accept

ADRs should be reviewed by:
- Technical leads (feasibility)
- Architects (alignment with strategy)
- Affected teams (awareness)

Move from Proposed → Accepted after review.

## Pitfalls

1. **Writing ADRs after the fact** — The best time is during the decision. Memory fades and rationale is lost.
2. **Missing alternatives** — An ADR with no alternatives suggests the decision wasn't deliberated. Even obvious choices had alternatives.
3. **Only positive consequences** — Every decision has downsides. Listing only positives reads as advocacy, not documentation.
4. **Too long** — An ADR should be 1-2 pages. If longer, the scope is too broad — split into multiple decisions.

## Verification

- [ ] Title clearly identifies the decision
- [ ] Context is factual and neutral (not persuasive)
- [ ] Decision is stated in one clear sentence
- [ ] At least 2 alternatives are documented with rejection rationale
- [ ] Consequences include both positive and negative impacts
- [ ] ADR is numbered and filed in the standard location

## BABOK Reference

Derived from Michael Nygard's ADR pattern and BABOK v3 Task 5.4 (Define Design Options) and 5.5 (Assess Proposed Solutions).

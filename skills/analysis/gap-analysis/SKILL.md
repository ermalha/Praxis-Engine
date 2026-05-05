---
name: gap-analysis
category: analysis
description: Identify gaps between current state and desired state with structured prioritization.
when_to_use: |
  When you need to compare where the organization is today against where it
  needs to be, and produce a prioritized list of gaps to close.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: published
schema_version: 1
---

# Gap Analysis

## Purpose

Gap analysis makes the distance between "as-is" and "to-be" explicit and
measurable. It produces a structured inventory of gaps that drives the
roadmap, requirements backlog, and investment decisions.

## Procedure

### 1. Define the current state (As-Is)

Document what exists today:
- Processes currently followed (even informal ones)
- Systems and tools in use
- Capabilities the organization has
- Performance metrics and their current values
- Pain points reported by stakeholders

Use artifacts: process maps, system inventories, interview transcripts.

### 2. Define the desired state (To-Be)

Document the target:
- Business objectives and success criteria
- Required capabilities
- Target performance metrics
- Regulatory or compliance requirements
- Strategic direction from sponsors

Source from: vision documents, strategy decks, compliance mandates.

### 3. Identify gaps

For each dimension (process, capability, system, data, people):
- Compare As-Is to To-Be
- Name the gap explicitly
- Categorize: missing capability, performance shortfall, compliance violation, skill deficit

### 4. Prioritize gaps

Score each gap on:
- **Impact** — How much does closing this gap move the needle? (1-5)
- **Urgency** — How time-sensitive is closure? (1-5)
- **Feasibility** — How achievable is closure with available resources? (1-5)
- **Risk of inaction** — What happens if we don't close it? (1-5)

Composite score = Impact + Urgency + Risk - (5 - Feasibility)

### 5. Recommend actions

For each high-priority gap, propose:
- Specific initiative or project to close it
- Owner and timeline estimate
- Dependencies on other gaps
- Quick wins vs. strategic investments

## Pitfalls

1. **Vague desired state** — "We want to be digital" isn't a target. Insist on measurable To-Be definitions.
2. **Ignoring informal processes** — Formal process maps miss the workarounds people actually use. Interview, don't just read documentation.
3. **Equal weighting** — Not all gaps are equal. Use the scoring framework; don't present a flat list.
4. **Solution-jumping** — Name the gap before proposing solutions. "We need Salesforce" is a solution, not a gap description.

## Verification

- [ ] Both As-Is and To-Be are documented with evidence
- [ ] Gaps are named as capability deficits, not solutions
- [ ] Every gap has an impact/urgency/feasibility score
- [ ] Top 5 gaps have recommended actions with owners
- [ ] Stakeholders have validated the As-Is description

## BABOK Reference

Derived from BABOK v3 Task 6.2 (Define Future State) and Technique 10.19 (Gap Analysis).

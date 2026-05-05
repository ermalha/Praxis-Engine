---
name: requirements-traceability-matrix
category: requirements
description: Link business needs to features, stories, and tests with orphan and coverage checks.
when_to_use: |
  When you need to demonstrate that all business requirements are addressed
  by the solution, or to identify gaps in test coverage and scope creep.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: published
schema_version: 1
---

# Requirements Traceability Matrix

## Purpose

A traceability matrix links every business need through the delivery chain:
need → feature → story → test. It answers "is every requirement covered?"
and "is every feature justified by a business need?" — catching both gaps
and gold-plating.

## Procedure

### 1. Establish the hierarchy

Define your traceability levels:
- **Business Need (BN)** — High-level business objective or regulatory requirement
- **Feature (F)** — Functional capability that addresses a need
- **User Story (US)** — Implementable unit within a feature
- **Test Case (TC)** — Verification that the story works

### 2. Populate top-down

Start from business needs and trace forward:
1. List all known business needs (from stakeholders, strategy docs, compliance)
2. Map each need to one or more features
3. Map each feature to its user stories
4. Map each story to its test cases

### 3. Populate bottom-up

Cross-check by tracing backwards:
1. For each test case, identify its story
2. For each story, identify its feature
3. For each feature, identify its business need
4. Flag anything that can't trace back — potential scope creep

### 4. Run coverage checks

| Check | Finding | Action |
|-------|---------|--------|
| **Orphan Need** | BN with no Feature mapped | Feature gap — needs analysis |
| **Orphan Feature** | Feature with no BN | Scope creep — remove or justify |
| **Orphan Story** | Story with no Feature | Misaligned — reassign or remove |
| **Untested Story** | Story with no TC | Test gap — write tests |
| **Over-covered** | BN with 10+ features | Possible over-engineering |

### 5. Maintain over time

The matrix is a living document:
- Update when new needs are discovered
- Update when stories are added or removed
- Review at sprint boundaries
- Use as input to release go/no-go decisions

## Pitfalls

1. **Stale matrix** — A traceability matrix created once and never updated is worse than none (false confidence).
2. **Wrong granularity** — Tracing to individual code lines is overkill. Trace to user stories and test cases.
3. **Missing the "why"** — If you can't articulate why a feature exists, it may be scope creep.
4. **Treating coverage as quality** — 100% traceability doesn't mean the requirements are correct. It means every requirement has *something* — validate the quality separately.

## Verification

- [ ] Every business need traces to at least one feature
- [ ] Every feature traces back to a business need
- [ ] Every story traces to a feature and has test cases
- [ ] Orphan check produces zero unresolved items
- [ ] Matrix has been reviewed with the Product Owner

## BABOK Reference

Derived from BABOK v3 Task 4.5 (Maintain Requirements) and Technique 10.3.1 (Requirements Traceability).

---
name: acceptance-criteria-gwt
category: requirements
description: Write Given-When-Then acceptance criteria with one scenario per behavior, data tables, and smell detection.
when_to_use: |
  When defining testable acceptance criteria for user stories, or when
  validating that existing criteria are specific enough for development and QA.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: published
schema_version: 1
---

# Acceptance Criteria (Given-When-Then)

## Purpose

GWT acceptance criteria translate business intent into testable scenarios.
Each scenario is a concrete example of behavior that can be automated as a
test, verified in review, and demonstrated in sprint demo.

## Procedure

### 1. Understand the structure

Each criterion follows:
- **Given** [a precondition or context]
- **When** [an action or event occurs]
- **Then** [an observable outcome]

Optionally: **And** continues any section, **But** adds negative conditions.

### 2. Write one scenario per behavior

Each GWT should test exactly ONE behavior:
- Don't combine happy path and error handling in one scenario
- Don't test multiple user actions in one When clause
- Don't verify multiple unrelated outcomes in one Then clause

### 3. Be specific with data

Bad: "Given the user has items in cart"
Good: "Given the user has 3 items in cart totaling $75.00"

Use data tables for variations:

| Item | Quantity | Price |
|------|----------|-------|
| Widget A | 2 | $25.00 |
| Widget B | 1 | $25.00 |

### 4. Cover the key scenarios

For each story, aim for:
- **Happy path** — The main success scenario
- **Edge cases** — Boundary values, empty states, maximums
- **Error cases** — Invalid input, permission denied, timeout
- **Business rules** — Discount thresholds, approval limits

3-7 scenarios per story is the sweet spot.

### 5. Detect common smells

Watch for these anti-patterns:
- **Implementation language** — "Then the database is updated" (test behavior, not internals)
- **UI-specific** — "Then a green toast appears" (test the outcome, not the presentation)
- **Vague outcomes** — "Then the system handles it correctly" (correct how?)
- **Compound scenarios** — Multiple When/Then pairs (split into separate scenarios)
- **Missing Given** — No context means the scenario is incomplete

## Pitfalls

1. **Testing implementation, not behavior** — "Then the API returns 200" is a technical test. Write "Then the order confirmation is displayed."
2. **Compound When clauses** — "When the user logs in and navigates to settings and changes their name" is three scenarios.
3. **Untestable Then** — "Then the user is satisfied" cannot be automated. Make outcomes observable and measurable.
4. **Too many scenarios** — More than 7 suggests the story is too big. Split the story first.

## Verification

- [ ] Each scenario tests exactly one behavior
- [ ] Given establishes clear, specific context
- [ ] When describes a single action or event
- [ ] Then describes an observable, verifiable outcome
- [ ] No implementation details leak into criteria
- [ ] Edge cases and error paths are covered

## BABOK Reference

Derived from BABOK v3 Technique 10.1 (Acceptance and Evaluation Criteria) and the Gherkin specification language by Cucumber.

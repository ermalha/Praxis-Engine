---
name: decision-matrix-construction
category: modeling
description: Construct weighted decision matrices to compare options against criteria using scoring methods like weighted sum and AHP-lite.
when_to_use: |
  When stakeholders need to choose between two or more alternatives and the
  decision must be transparent, repeatable, and defensible — not driven by
  gut feeling or whoever speaks loudest in the room.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: published
schema_version: 1
---

# Decision Matrix Construction

## Purpose

A decision matrix replaces subjective "I just feel like Option B" with a
structured, auditable scoring process. It forces stakeholders to name their
criteria, agree on what matters most, and evaluate each option against the
same yardstick. The output is not a magic answer — it is a conversation tool
that makes trade-offs visible and defensible.

As a BA, you will reach for a decision matrix when selecting vendors, choosing
architecture options, prioritizing feature sets, or comparing process redesign
alternatives. The matrix is most valuable when there are 3-7 options and 4-10
criteria. Below that range, a simple pros/cons list works. Above it, the
matrix becomes unwieldy and you need decomposition.

## Procedure

### 1. Define the decision statement

Write a clear, specific question: "Which CRM platform should we adopt for the
EMEA sales team by Q3 2025?" A vague question ("What tool should we use?")
produces vague criteria.

### 2. Identify options

List all feasible alternatives. Include the "do nothing" option explicitly —
it is always a legitimate baseline. Remove obviously non-viable options early,
but document why they were excluded so nobody re-raises them later.

### 3. Define evaluation criteria

Good criteria are:
- **Measurable** — you can score an option against them
- **Independent** — they don't double-count the same concern
- **Complete** — together they cover what matters to the decision
- **Stakeholder-validated** — the people affected agree these are the right
  dimensions

Common categories: cost, time-to-implement, strategic alignment, risk,
usability, maintainability, compliance, vendor stability.

### 4. Assign weights

Weights express relative importance. Two approaches:

**Simple allocation:** Distribute 100 points across criteria. Stakeholders
negotiate until consensus. This is fast and works for most BA decisions.

**AHP-lite (pairwise comparison):** Compare each pair of criteria and ask
"Which matters more, and by how much?" (scale: 1 = equal, 3 = moderate,
5 = strong, 9 = extreme). Build a comparison matrix, normalize columns,
and average rows to get weights. This is more rigorous and useful when
stakeholders cannot agree on simple allocation.

Regardless of method, publish the weights before scoring options. Never
adjust weights after seeing scores — that is outcome-rigging.

### 5. Score each option

Use a consistent scale (1-5 or 1-10) for every cell. Define what each
score level means for each criterion:
- 1 = Does not meet the criterion at all
- 3 = Partially meets, with significant gaps
- 5 = Fully meets or exceeds the criterion

Have at least two people score independently, then discuss divergences. A
3-point gap on the same cell signals that one scorer has information the
other lacks.

### 6. Calculate weighted scores

For each option: Weighted Score = SUM(criterion_weight * criterion_score)

Rank options by total weighted score. Present the full table, not just the
winner — stakeholders need to see the margins.

### 7. Sensitivity check

Ask: "If we changed the weight of [top criterion] by +/- 20%, would the
winner change?" If yes, the decision is fragile and you need deeper analysis
on that criterion. Run at least two sensitivity scenarios and document them.

### 8. Document the recommendation

State the recommended option, the margin of victory, which criteria drove
it, and what risks the recommendation carries. Flag any criteria where the
winner scored poorly — those become risk mitigations.

## Pitfalls

1. **Criteria overlap** — "Cost" and "Total Cost of Ownership" measure the
   same thing. Overlapping criteria double-count concerns and bias the
   result. Review criteria for independence before scoring.

2. **Anchoring bias in scoring** — If you score options top-to-bottom in the
   matrix, the first option anchors all subsequent scores. Score each
   criterion across all options as a row, not each option as a column.

3. **Weight manipulation** — Adjusting weights after seeing scores to favor
   a preferred option destroys the matrix's credibility. Lock weights before
   scoring begins.

4. **False precision** — A weighted score of 4.23 vs 4.19 is meaningless
   noise. If the margin between top options is less than 10% of the maximum
   possible score, call it a tie and use qualitative judgment for the final
   call.

5. **Missing "do nothing" baseline** — Without it, you cannot tell whether
   any option is actually better than the status quo.

## Verification

- [ ] Decision statement is specific and time-bound
- [ ] "Do nothing" is included as a baseline option
- [ ] Criteria are independent (no double-counting)
- [ ] Weights were agreed before scoring began
- [ ] Score definitions are documented (what does a "3" mean?)
- [ ] At least two scorers participated independently
- [ ] Sensitivity check performed on top-weighted criterion
- [ ] Recommendation states margin, drivers, and residual risks

## BABOK Reference

Derived from BABOK v3 Technique 10.11 (Decision Analysis) and supports
Task 6.3 (Assess Risks) and Task 6.4 (Define Change Strategy). The weighted
scoring approach maps to the multi-criteria decision analysis method
described in the Decision Analysis technique.

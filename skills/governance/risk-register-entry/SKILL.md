---
name: risk-register-entry
category: governance
description: Add risks to the register with likelihood, impact, mitigation type, owner, and review cadence.
when_to_use: |
  When a new risk is identified during analysis, elicitation, or review that
  needs formal tracking, or when reviewing and updating existing risk entries.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: published
schema_version: 1
---

# Risk Register Entry

## Purpose

A well-maintained risk register prevents surprises by making threats visible,
owned, and actively managed. Each entry captures enough information for the
risk owner to monitor, mitigate, and escalate when needed.

## Procedure

### 1. Identify and describe the risk

Write the risk as a conditional statement:
"If [threat/event] occurs, then [impact on project/business]."

Bad: "Database risk"
Good: "If the legacy database migration takes longer than 6 weeks, then the go-live date will slip by 2-4 weeks, affecting Q3 revenue targets."

### 2. Assess likelihood

| Rating | Meaning | Probability |
|--------|---------|-------------|
| High | Very likely to occur | >70% |
| Medium | Possible, has happened before | 30-70% |
| Low | Unlikely but possible | <30% |

Base on evidence: has this happened before? Are conditions present?

### 3. Assess impact

| Rating | Meaning | Examples |
|--------|---------|----------|
| High | Major disruption | Budget overrun >20%, missed regulatory deadline, data breach |
| Medium | Manageable disruption | 1-2 sprint delay, workaround needed, quality compromise |
| Low | Minor inconvenience | Small delay, no stakeholder impact |

### 4. Calculate risk score

Risk Score = Likelihood x Impact (using H=3, M=2, L=1):
- **6-9**: Critical — immediate mitigation required
- **3-4**: Moderate — mitigation planned
- **1-2**: Low — monitor and accept

### 5. Choose mitigation strategy

| Strategy | When to use | Example |
|----------|-------------|---------|
| **Avoid** | Eliminate the threat entirely | Change approach, remove scope |
| **Mitigate** | Reduce likelihood or impact | Add testing, create backup plan |
| **Transfer** | Shift to a third party | Insurance, vendor SLA, contract clause |
| **Accept** | Cost of mitigation exceeds impact | Document and monitor |

### 6. Assign ownership and review cadence

- **Owner**: One person accountable for monitoring and executing mitigation
- **Review cadence**: How often to reassess (weekly for critical, monthly for moderate)
- **Trigger indicators**: What signals that the risk is materializing?

### 7. Common BA risk patterns

Risks that BAs commonly identify:
- **Stakeholder availability** — Key SME unavailable during critical analysis period
- **Scope creep** — Requirements expanding without corresponding budget/timeline adjustment
- **Integration complexity** — External system dependencies underestimated
- **Data quality** — Source data incomplete or inconsistent for migration/reporting
- **Change resistance** — Users unwilling to adopt new processes
- **Regulatory change** — Compliance requirements shifting mid-project
- **Knowledge loss** — Key team member departure during critical phase

## Pitfalls

1. **Vague risk descriptions** — "Technical risk" is not actionable. Always use "If X then Y" format.
2. **No owner** — A risk with no owner will not be monitored. Every risk needs exactly one accountable person.
3. **Register as a graveyard** — A register that's never reviewed is theater. Set review cadence and stick to it.
4. **Confusing risks with issues** — Risks are future possibilities. Issues have already occurred. Don't put current problems in the risk register.

## Verification

- [ ] Risk described as "If [threat] then [impact]"
- [ ] Likelihood and impact assessed with justification
- [ ] Mitigation strategy chosen and documented
- [ ] Single owner assigned
- [ ] Review cadence set
- [ ] Risk fits in the register format (not an issue, not an assumption)

## BABOK Reference

Derived from BABOK v3 Technique 10.38 (Risk Analysis and Management) and ISO 31000 risk management principles.

# Starter Skills Reference

Praxis ships 12 bundled skills covering core BABOK techniques. All are
`human_curated: true`, `status: published`, and available in every engagement
by default.

## Elicitation

| Skill | Description | When to use |
|-------|-------------|-------------|
| `interview-preparation` | Prepare for stakeholder interviews: research, agenda, question types, follow-ups | Before any scheduled stakeholder interview |
| `stakeholder-analysis` | Identify, classify (RACI / Salience / Influence-Interest), and map stakeholders | At engagement start or when new stakeholders emerge |

## Analysis

| Skill | Description | When to use |
|-------|-------------|-------------|
| `gap-analysis` | Current state vs. desired state with structured gap identification | When assessing transformation scope or evaluating readiness |
| `process-modeling-bpmn` | BPMN process models in text/Mermaid with swimlanes, gateways, events | When documenting or improving business processes |

## Modeling

| Skill | Description | When to use |
|-------|-------------|-------------|
| `decision-matrix-construction` | Weighted scoring with criteria, options, and sensitivity checks | When stakeholders must choose between alternatives |
| `raci-construction` | RACI matrix from process or scope with conflict detection | When clarifying roles and responsibilities |

## Requirements

| Skill | Description | When to use |
|-------|-------------|-------------|
| `invest-story-writing` | User stories satisfying INVEST criteria | During backlog creation or refinement |
| `acceptance-criteria-gwt` | Given-When-Then acceptance criteria with data tables | When defining done for user stories |
| `requirements-traceability-matrix` | Link business needs to features, stories, and tests | When maintaining traceability across requirement levels |

## Decision

| Skill | Description | When to use |
|-------|-------------|-------------|
| `adr-authoring` | Architecture Decision Records with context, decision, consequences | When recording significant technical or process decisions |

## Communication

| Skill | Description | When to use |
|-------|-------------|-------------|
| `status-report` | Weekly/monthly reports: progress, plan, blockers, asks, RAID | When producing periodic stakeholder updates |

## Governance

| Skill | Description | When to use |
|-------|-------------|-------------|
| `risk-register-entry` | Risk entries with likelihood, impact, mitigation, ownership | When a new risk needs formal tracking |

## Skill locations

Skills are discovered from three locations (higher precedence shadows lower):

1. **Bundled** — shipped with Praxis in `praxis/_bundled_skills/`
2. **User** — `~/.praxis/skills/`
3. **Engagement** — `<engagement>/.praxis/skills/`

To list all available skills:

```bash
praxis skill list
```

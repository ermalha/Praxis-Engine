# Sufficiency Templates Reference

Templates provide pre-populated information needs for known artifact kinds.
They live in `src/praxis/core/sufficiency_templates/` as YAML files.

## Template format

```yaml
artifact_kind: <kind>
information_needs:
  - need: "<description of what information is needed>"
    blocker: true | false
```

Each need is a starting point — the LLM may add, modify, or refine needs
based on the specific artifact target and engagement context.

## Available templates

### user-story

| Need | Blocker |
|------|---------|
| Actor identity — who is the user or persona performing the action? | Yes |
| Action goal — what does the actor want to accomplish? | Yes |
| Value / why — what business or user value does this deliver? | Yes |
| Acceptance criteria — concrete conditions that define done | Yes |
| Business rules and constraints governing the behaviour | No |
| Non-functional requirements (performance, security, accessibility) | No |

### decision-matrix

| Need | Blocker |
|------|---------|
| Options — the set of alternatives being compared | Yes |
| Evaluation criteria — the dimensions used to score options | Yes |
| Criteria weights — relative importance of each criterion | No |
| Evaluator(s) — who provides the scoring or assessment? | No |
| Decision authority — who has final sign-off? | Yes |

### spec

| Need | Blocker |
|------|---------|
| Scope boundaries — what is in scope and what is out of scope? | Yes |
| Actors — who interacts with the system? | Yes |
| Business rules governing the domain logic | Yes |
| Data model — key entities, attributes, and relationships | No |
| Integration points — external systems and interfaces | No |
| Non-functional requirements (performance, security, scalability) | No |

### process-model

| Need | Blocker |
|------|---------|
| Start and end events — what triggers the process and what ends it? | Yes |
| Actors — who performs each step? | Yes |
| Decision points — branching conditions and their outcomes | Yes |
| Exception flows — what happens when something goes wrong? | No |
| System interactions — which systems are involved at each step? | No |

### risk-register-entry

| Need | Blocker |
|------|---------|
| Likelihood basis — evidence or reasoning for the probability rating | Yes |
| Impact basis — what would be affected and how severely? | Yes |
| Risk owner — who is accountable for monitoring and mitigation? | Yes |
| Mitigation feasibility — are there practical options to reduce the risk? | No |

## Adding custom templates

Place a YAML file in the templates directory following the format above.
The filename (without extension) becomes the artifact kind identifier.

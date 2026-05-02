# Sufficiency Gate

The Sufficiency Gate is the first of three components that make Praxis distinct
from a chat agent. Before producing any artifact (user story, spec, decision
matrix, report), the agent runs a typed self-check: **do I have enough
information to do this well?**

## Principle

Analysts don't write stories with half the facts. Neither should an AI agent.
The Gate enforces a structured evaluation before artifact production, making
the agent's analytical posture visible and inspectable.

## How it works

1. The agent (or human via CLI) requests a sufficiency check for a given
   artifact kind and target description.
2. The Gate builds a focused sub-prompt that:
   - Enumerates information needs for that artifact kind
   - Uses pre-populated templates for known kinds (user-story, spec, etc.)
   - Classifies each need as KNOWN, PARTIAL, or UNKNOWN by checking the
     engagement model
   - Proposes candidate sources for missing information
3. A single LLM call produces a structured `SufficiencyReport`.
4. Cross-references are validated (stakeholder IDs must exist).
5. The report is persisted as an immutable JSON file.

## The report

```
Verdict: SUFFICIENT | PARTIAL | INSUFFICIENT
Action:  produce    | produce_with_caveats | elicit
```

Each information need includes:
- **status**: known / partial / unknown
- **blocker**: whether the artifact cannot proceed without this
- **have**: what information is already available
- **missing**: what's still needed
- **candidate_sources**: where to get the missing information

## Verdict rules

- **SUFFICIENT** — all needs are KNOWN. Action: `produce`.
- **PARTIAL** — no blockers are UNKNOWN, but some needs are PARTIAL.
  Action: `produce_with_caveats`.
- **INSUFFICIENT** — at least one blocker is UNKNOWN.
  Action: `elicit`.

## Using the Gate

### As a tool (agent calls it)

The agent should call `sufficiency_check` before producing any artifact.
The system prompt encourages this behaviour.

### From the CLI

```bash
praxis check user-story "Invoice approval workflow"
praxis check spec "Payment module" --json
praxis check decision-matrix "Technology selection" --context "Comparing React vs Vue"
```

## Templates

For known artifact kinds, the Gate uses pre-populated templates that give the
LLM a strong prior on what information is typically needed. Templates exist for:

- `user-story` — actor, goal, value, acceptance criteria, business rules, NFRs
- `decision-matrix` — options, criteria, weights, evaluator, authority
- `spec` — scope, actors, business rules, data model, integrations, NFRs
- `process-model` — start/end events, actors, decisions, exceptions, systems
- `risk-register-entry` — likelihood, impact, owner, mitigation feasibility

For unknown artifact kinds, the LLM enumerates needs from scratch.

## Configuration

- `profile.enforce_sufficiency_gate` (default: `true`) — when enabled,
  artifact production tools can check the Gate and refuse on INSUFFICIENT.
- `profile.sufficiency_gate_model_alias` — optional model alias for Gate calls
  (a cheaper/faster model is often sufficient).

## Design notes

- The Gate is intentionally cheap: a single LLM call with bounded output.
- Reports are immutable — re-running creates a new report.
- Reports are persisted to `<engagement>/.praxis/state/sufficiency-reports/`.

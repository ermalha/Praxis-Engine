# Elicitation Planner

The Elicitation Planner closes the loop between "I don't know X" (from the
Sufficiency Gate) and "Maria knows X and prefers email; here's the message."

## How it works

1. Takes a `SufficiencyReport` with `UNKNOWN` or `PARTIAL` information needs.
2. Groups needs by candidate stakeholder.
3. For each group, the LLM drafts a targeted message choosing:
   - **Channel** — based on the stakeholder's `contact_preference`
   - **Mode** — based on complexity and number of needs
   - **Priority** — based on blocker status
4. Auto-creates `OpenQuestion` entries in the engagement model.
5. Persists drafts to disk for review.

## Elicitation modes

| Mode | When to use |
|------|-------------|
| `direct_question` | 1-2 simple, factual questions |
| `email` | Formal request with context |
| `meeting_request` | Complex topic needing discussion |
| `workshop` | 5+ needs across topics, multiple stakeholders |
| `document_request` | Need an existing document or artifact |
| `shadowing` | Need to observe a process |

## Stakeholder selection

Priority order:
1. Preferred IDs from the sufficiency report's `candidate_sources`
2. Stakeholders with matching `expertise` keywords
3. Stakeholders with matching `decision_authority`
4. Fallback: `UNKNOWN` — asks the human operator to identify the right person

## Draft templates

Templates in `src/praxis/core/elicitation_templates/` provide structure:
- `email_direct_question.yaml`
- `email_meeting_request.yaml`
- `email_document_request.yaml`
- `chat_direct_question.yaml`
- `meeting_workshop_agenda.yaml`

## Using the planner

### As a tool (agent calls it)

```
plan_elicitations_for_report(sufficiency_report_id="abc123")
```

### From the CLI

```bash
praxis elicit --latest
praxis elicit abc123def456
praxis elicit --latest --json
```

## What happens next

Drafts are saved but NOT sent automatically. In the current version, the
human reviews drafts and dispatches them manually. The work-queue (chunk 11)
will enable structured review and dispatch workflows.

## Design notes

- Conservative stakeholder selection: when in doubt, fall back to UNKNOWN.
- Fewer, richer messages preferred over many small ones.
- Drafts are immutable once saved. Re-running creates a new batch.
- OpenQuestion entries are created with `status="open"` and linked to the
  candidate stakeholder.

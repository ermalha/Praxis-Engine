# Work Queue

The Work Queue is where the agent and the human meet. The agent enqueues
items it can't (or shouldn't) execute alone; the human commits, rejects,
modifies, or defers them. This is the operational core of "agent-led,
human-gated."

## Two flavors of work items

- **Human work-items** — things the human must do (send an email, attend a
  meeting, click a button in a SaaS the agent can't reach)
- **Agent work-items** — things the agent queues for later execution
  (re-evaluate sufficiency, follow up on stalled questions)

## Work-item types

| Type | Assignee | Description |
|------|----------|-------------|
| `send_message` | human | Send a drafted message (email, chat) |
| `schedule_meeting` | human | Book a meeting with stakeholders |
| `conduct_interview` | human | Run an elicitation interview |
| `review_artifact` | human/agent | Review a produced artifact |
| `approve_artifact` | human | Approve an artifact for release |
| `execute_in_system` | human | Perform an action in an external system |
| `answer_question` | human | Provide an answer the agent needs |
| `make_decision` | human | Make a decision the agent can't |
| `agent_follow_up` | agent | Agent self-task for future action |
| `agent_refresh` | agent | Agent self-task to refresh data |

## State machine

```
QUEUED → IN_PROGRESS → DONE
QUEUED → IN_PROGRESS → BLOCKED → IN_PROGRESS → ...
QUEUED → REJECTED
QUEUED | IN_PROGRESS → DEFERRED → QUEUED
* → SUPERSEDED
```

Invalid transitions raise `WorkqueueError`.

## Prioritization

Items are scored by a composite formula:

```
score = priority_weight + deadline_urgency + blocking_count + age_decay
```

The daily view shows items ordered by score, highest first.

## CLI

```bash
praxis queue                  # Show prioritized human items
praxis queue --all            # Include agent items
praxis queue show <id>        # Full details
praxis queue start <id>       # Mark in-progress
praxis queue done <id> --note "Done"
praxis queue commit <id> --note "Sent" --result '{"answer":"..."}'
praxis queue reject <id>
praxis queue defer <id>
```

## The commit moment

When a human marks an item as **done**, they must provide a `completion_note`
explaining what happened. This becomes part of the engagement record. If the
item was linked to an `OpenQuestion` and the return payload contains an
`answer`, the question is automatically updated to `answered`.

## Bridges

- **Elicitation drafts** become `SEND_MESSAGE` work-items
- **Open questions** without an answerer become `ANSWER_QUESTION` items
- **Sufficiency reports** with `PARTIAL` verdict can create `REVIEW_ARTIFACT`
  items for the agent

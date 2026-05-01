# Chunk 11 — Human Work-Queue

**Phase:** Praxis Distinctives | **Estimated effort:** 5 hours | **Dependencies:** 01–10

---

## Context

The Work-Queue is where the agent and the human meet. The agent enqueues
items it can't (or shouldn't) execute alone; the human commits, rejects,
modifies, or defers them. This is the operational core of "agent-led, human-gated."

Items come in two flavors:

- **Human work-items** — things the human must do (send the email the agent drafted, attend the meeting, run a test, make a call, click a button in a SaaS the agent can't reach)
- **Agent work-items** — things the agent itself queues for later execution (re-evaluate sufficiency in 2 days, follow up on stalled question, refresh stakeholder map)

This chunk delivers the typed work-item schema, the queue persistence,
the state machine, and a CLI to manage it. Chunk 13 adds the TUI on top.

---

## Scope

### Models (`src/praxis/workqueue/models.py`)

```python
class WorkItemStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    DEFERRED = "deferred"

class WorkItemPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class WorkItemType(StrEnum):
    SEND_MESSAGE = "send_message"               # email, chat, etc — payload is ElicitationDraft
    SCHEDULE_MEETING = "schedule_meeting"
    CONDUCT_INTERVIEW = "conduct_interview"
    REVIEW_ARTIFACT = "review_artifact"
    APPROVE_ARTIFACT = "approve_artifact"
    EXECUTE_IN_SYSTEM = "execute_in_system"     # for actions in SaaS the agent can't reach
    ANSWER_QUESTION = "answer_question"          # human, please answer this
    MAKE_DECISION = "make_decision"
    AGENT_FOLLOW_UP = "agent_follow_up"          # agent self-task
    AGENT_REFRESH = "agent_refresh"              # agent self-task

class WorkItem(BaseModel):
    schema_version: Literal[1] = 1
    id: str
    type: WorkItemType
    assignee: Literal["human", "agent"]
    status: WorkItemStatus
    priority: WorkItemPriority
    title: str                                  # one-line summary
    description: str                            # full context
    payload: dict                               # type-specific structured data
    related_artifact_ids: list[str] = []
    related_question_ids: list[str] = []
    related_stakeholder_ids: list[str] = []
    blocks: list[str] = []                      # other work-item ids this blocks
    blocked_by: list[str] = []
    created_at: datetime
    updated_at: datetime
    deadline: datetime | None = None
    completed_at: datetime | None = None
    completion_note: str | None = None          # what happened when it was done
    return_payload: dict | None = None          # what was learned (e.g., the answer to a question)
    rationale: str                              # why the agent created this item
```

### Persistence (`src/praxis/workqueue/repo.py`)

```python
class WorkQueueRepo:
    def __init__(self, engagement_path: Path): ...
    def create(self, item: WorkItem) -> WorkItem: ...
    def get(self, id: str) -> WorkItem: ...
    def list(self, *, status: WorkItemStatus | None = None,
             assignee: str | None = None,
             priority: WorkItemPriority | None = None) -> list[WorkItem]: ...
    def transition(self, id: str, to: WorkItemStatus,
                   note: str | None = None,
                   return_payload: dict | None = None) -> WorkItem: ...
    def update(self, id: str, **fields) -> WorkItem: ...
```

Storage: `workitems` SQLite table (schema from chunk 03) plus a JSONL append
at `<engagement>/.praxis/state/workqueue.jsonl` for the audit-friendly stream.

State machine (validated in `transition`):

```
QUEUED → IN_PROGRESS → DONE
QUEUED → IN_PROGRESS → BLOCKED → IN_PROGRESS → ...
QUEUED → REJECTED
QUEUED | IN_PROGRESS → DEFERRED → QUEUED
* → SUPERSEDED   (when a new item replaces this one)
```

Invalid transitions raise `WorkqueueError`.

### Prioritization helper (`src/praxis/workqueue/scoring.py`)

Sort items by a composite score for the daily view:

```
score = priority_weight + deadline_urgency + blocking_count + age_decay
```

Configurable weights via profile config (defaults given). Returns list ordered
high-to-low.

### Bridges from earlier chunks

- **Elicitation drafts → SEND_MESSAGE items.** Add `praxis elicit --enqueue`
  flag in chunk 10 CLI (or extend that flag here): convert each draft to a
  `WorkItem(type=SEND_MESSAGE, assignee=human, payload=draft.dict())`.
- **Open questions without an answerer → ANSWER_QUESTION items** (assignee=human, "please identify who can answer this") created automatically by an agent tool.
- **Sufficiency report verdict=PARTIAL with no blockers → optional REVIEW_ARTIFACT**
  on the agent itself: re-check after some progress.

### Tools

```python
@tool("workqueue_enqueue", toolset="workqueue", dangerous=True)
def workqueue_enqueue(ctx, type: str, assignee: str, title: str,
                      description: str, priority: str = "medium",
                      payload: dict = {}, ...) -> ToolResult: ...

@tool("workqueue_list", toolset="workqueue", dangerous=False)
def workqueue_list(ctx, status: str | None = None,
                   assignee: str | None = None) -> ToolResult: ...

@tool("workqueue_transition", toolset="workqueue", dangerous=True)
def workqueue_transition(ctx, id: str, to: str, note: str | None = None,
                         return_payload: dict = {}) -> ToolResult: ...
```

The agent uses `workqueue_enqueue` to create human work-items. It also uses
`workqueue_transition` on its own agent-assigned items.

### CLI

```
praxis queue                        # show prioritized list of human items
praxis queue --all                  # include agent items, all statuses
praxis queue show <id>              # full details
praxis queue commit <id> [--note "...."] [--result "..."]
praxis queue reject <id> [--note "..."]
praxis queue defer <id> --until 2026-05-10
praxis queue start <id>             # mark IN_PROGRESS
praxis queue done <id> --note "..." [--return-data '{"answer":"..."}']
```

Output is rich tables for `queue` (with priority, deadline, age, title)
and detail panels for `show`.

### Audit events

- `workitem.created`
- `workitem.transitioned` (carries from→to)
- `workitem.committed` (DONE with notes — the human commit moment)
- `workitem.rejected`
- `workitem.deferred`

---

## Deliverables

- `src/praxis/workqueue/` — models, repo, scoring, transitions
- 3 tools registered with chunk-5 registry
- CLI: `praxis queue` and subcommands
- Update `praxis elicit` to support `--enqueue` (creates SEND_MESSAGE items)
- Auto-creation of ANSWER_QUESTION items for open questions without identified answerers (run on engagement open)
- Tests:
  - State machine transitions valid and invalid paths
  - Scoring orders correctly
  - Elicitation draft → SEND_MESSAGE work-item round-trip
  - `queue commit` with `--return-data` updates the linked OpenQuestion's answer field
  - `workqueue_transition` from the agent's tool path emits proper audit
- `tests/integration/test_chunk_11.py`
- `docs/concepts/work-queue.md` — the daily-driver concept, the human-gated principle in action
- `docs/how-to/manage-the-queue.md`
- Update `chunks/STATUS.md`

---

## Acceptance test

```python
def test_full_workqueue_flow(tmp_engagement, mock_anthropic):
    # 1. Create stakeholder + question + sufficiency report + elicitation draft
    # 2. Convert draft → SEND_MESSAGE work-item
    # 3. List queue: shows the item at top (priority high, blocking)
    # 4. Start → in_progress
    # 5. Commit with return-data: includes the answer text
    # 6. Verify: the linked OpenQuestion is now status=answered and has the answer
    # 7. Verify: audit events for create, transition, commit
```

---

## Explicit non-goals

- No TUI yet (chunk 13)
- No actual sending of emails (chunk 14)
- No followup automation (cron-like rescheduling) — flagged for future

---

## Notes

- The work-queue is a **priority list of next actions**, not a project plan.
  Anything taking more than a few hours of human time should be decomposed.
- "Done" requires a `completion_note` for human items — the human must say
  what happened. This becomes part of the engagement record.
- Agent work-items (assignee=agent) are picked up by the orchestrator's
  wake cycle (chunk 12). Until then they just sit there.

---

## Definition of done

- All deliverables present
- Acceptance test passes
- `praxis queue` shows a useful daily view with real items
- `pytest`, `ruff`, `mypy` green
- `chunks/STATUS.md` updated

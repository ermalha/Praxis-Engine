# Chunk 12 — Wake Cycle / Orchestrator

**Phase:** Praxis Distinctives | **Estimated effort:** 5–6 hours | **Dependencies:** 01–11

---

## Context

This is the chunk that turns Praxis from a chat agent into an **agent-led
analyst**. The orchestrator wakes up (on schedule, on event, on demand),
surveys the engagement state, decides what work to do next, executes what it
can, and queues what it can't. Everything from chunks 1–11 was building
toward this moment.

After this chunk, you can run `praxis run` and the agent operates
continuously — checking inboxes, drafting artifacts, finding gaps, generating
work-items — without waiting for prompts.

---

## Scope

### The orchestrator (`src/praxis/core/orchestrator.py`)

```python
class Orchestrator:
    def __init__(self, agent: Agent, profile: ProfileConfig,
                 engagement: EngagementConfig, engagement_path: Path): ...
    def wake_once(self, *, trigger: WakeTrigger) -> WakeReport: ...
    def run_forever(self, *, cancel_event: Event) -> None: ...
```

`wake_once` is a single iteration. `run_forever` schedules wakes per the
config (interval + event-driven triggers).

### The wake algorithm

```
1. Refresh state:
   - Read inbox (chunk 14 integrations if connected; otherwise no-op)
   - Re-load engagement model (mtime check on files)
   - Pull workqueue items in QUEUED state
   - Pull conversation history for unread messages

2. Update engagement model with anything new:
   - Newly-arrived emails parsed for stakeholder ids → update
     OpenQuestion.answer if matched (keyword + recipient match)
   - New documents in inbox added to artifacts/inbox/
   - Calendar events in next 24h surface as MEETING_REMINDER work-items

3. Generate or refresh "agent-task plan":
   - List candidate tasks, scored:
     a. Stalled questions (asked > N days ago without answer) → followup
     b. Insufficient artifacts (sufficiency reports with INSUFFICIENT verdict) → re-evaluate
     c. Empty engagement areas (no stakeholders yet, no risks yet) → propose elicitation
     d. Newly arrived inbox items needing classification → triage
     e. Agent work-items in QUEUED → execute
   - Score and pick top K (configurable, default 3)

4. For each picked task:
   - Run sufficiency check if it produces an artifact
   - Execute via tool calls if agent-only action
   - Enqueue human work-item if requires commit
   - Emit audit events

5. Sleep until next trigger
```

### Triggers

`WakeTrigger` enum: `MANUAL`, `SCHEDULED`, `INBOX_EVENT`, `WORKQUEUE_REPLY`,
`FILE_CHANGED`, `STARTUP`.

For v1:
- `MANUAL` (`praxis wake`) and `SCHEDULED` are required.
- `STARTUP` runs when `praxis run` first starts.
- `INBOX_EVENT` is wired in chunk 14 (the integrations chunk) — for now there's
  a stub interface.
- `FILE_CHANGED` watches `<engagement>/.praxis/engagement/` and `artifacts/` via `watchdog`.

### Quiet hours

If the wake time falls in `wake_cycle.quiet_hours`, defer to the next
non-quiet slot. Useful for not pinging users at 3am.

### Loop budget

A single wake has a token budget (configurable, default 50k). When approaching
the budget, the orchestrator wraps up the current task and emits a
`wake.budget_exceeded` audit event.

### `WakeReport`

```python
class WakeReport(BaseModel):
    started_at: datetime
    ended_at: datetime
    trigger: WakeTrigger
    state_changes_observed: list[str]    # high-level summary
    tasks_considered: list[str]
    tasks_executed: list[str]
    workitems_created: list[str]
    audit_event_count: int
    tokens_used: int
    notes: str | None = None
```

Persisted to `<engagement>/.praxis/state/wake-reports/<timestamp>.json` for
diagnostics and the TUI's "what just happened" view.

### Daily plan

A meta-task: once per day (configurable hour), the orchestrator generates a
`DailyPlan` artifact summarizing:
- What happened in the last 24h
- What's expected today
- Top 3-5 prioritized work-items for the human
- Open blockers

Saved to `<engagement>/.praxis/artifacts/reports/daily-plan-<date>.md`.
Linked from the queue view.

### Tools (limited new tools — orchestrator mostly uses existing ones)

- `wake_status` — internal tool the agent can call to read its own recent wake reports
- `propose_followup` — agent-callable, schedules an `AGENT_FOLLOW_UP` work-item

### CLI

```
praxis run                          # blocking; runs the orchestrator until Ctrl-C
praxis wake                         # one-shot wake cycle
praxis wake --dry-run               # plan tasks but don't execute
praxis plan today                   # generate today's daily plan
praxis status                       # human-readable engagement health snapshot
```

`praxis status` is especially valuable — a quick "what's the agent thinking"
view: open questions, blocked artifacts, last wake summary, top queue items.

---

## Deliverables

- `src/praxis/core/orchestrator.py`
- `src/praxis/core/wake/` — task generators, scorers, daily-plan generator
- File watcher integration (`watchdog` dependency)
- 2 new tools: `wake_status`, `propose_followup`
- CLI: `praxis run`, `praxis wake`, `praxis plan today`, `praxis status`
- Tests:
  - Single wake with empty state: produces a no-op WakeReport
  - Wake with stalled question: generates AGENT_FOLLOW_UP item
  - Wake with insufficient artifact in queue: re-runs sufficiency check
  - Wake with empty stakeholders: proposes "identify-stakeholders" elicitation
  - Quiet-hours deferral
  - Budget exceeded mid-task
  - File-change trigger reloads model
- `tests/integration/test_chunk_12.py` — multi-wake scenario:
  1. Start with engagement having an open unanswered question (asked 5 days ago)
  2. `praxis wake` once
  3. Verify a SEND_MESSAGE work-item was created as a followup
  4. Verify daily plan was generated
- `docs/concepts/orchestrator.md` — the wake-cycle pattern
- `docs/concepts/agent-led-vs-reactive.md` — the philosophy
- Update `chunks/STATUS.md`

---

## Acceptance test

```python
def test_followup_on_stalled_question(tmp_engagement, mock_anthropic, freezer):
    # Setup: stakeholder, open question asked 5 days ago, no answer
    StakeholderRepo(tmp_engagement).add(name="Maria L.", id="m1", role="AP", contact_preference="email")
    qr = OpenQuestionsRepo(tmp_engagement)
    q = qr.open(question="What's the AP threshold?", why_it_matters="Blocker",
                candidate_answerers=["m1"])
    qr.mark_asked(q.id, asked_at=datetime.now(UTC) - timedelta(days=5))

    orch = make_orchestrator(tmp_engagement)
    report = orch.wake_once(trigger=WakeTrigger.MANUAL)

    assert "stalled_question" in report.state_changes_observed
    items = WorkQueueRepo(tmp_engagement).list(status=WorkItemStatus.QUEUED)
    followups = [i for i in items if i.type == WorkItemType.SEND_MESSAGE]
    assert len(followups) == 1
    assert "follow" in followups[0].title.lower() or "remind" in followups[0].title.lower()

def test_dry_run_doesnt_persist(tmp_engagement):
    before = ...
    orch.wake_once(trigger=WakeTrigger.MANUAL, dry_run=True)
    after = ...
    assert before == after  # no work-items created, no engagement model changes
```

---

## Explicit non-goals

- No TUI streaming live wake updates (chunk 13)
- No actual external integrations yet — inbox is a stub
- No multi-engagement orchestrator — one engagement per run

---

## Notes

- This is the heaviest chunk so far. Take it slowly. Build task generators
  one at a time and test each in isolation before composing.
- Resist the urge to make the orchestrator clever. The task generators are
  rule-based; the LLM is only invoked for the actual artifact production
  and elicitation drafting (existing tools).
- Wake reports are first-class observability. The TUI in chunk 13 will display
  them prominently.
- Quiet hours apply globally; don't make per-stakeholder quiet times in v1.

---

## Definition of done

- All deliverables present
- Acceptance test passes
- `praxis run` works for at least 30 minutes against a real engagement without crashing
- `pytest`, `ruff`, `mypy` green
- `chunks/STATUS.md` updated — **Praxis-distinctive milestone reached**

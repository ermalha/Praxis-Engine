# Orchestrator & Wake Cycle

The Orchestrator is what makes Praxis **agent-led** rather than reactive.
Instead of waiting for the human to ask questions, the agent wakes up on a
schedule (or on events), surveys the engagement state, and decides what to
do next.

## The wake algorithm

Each wake cycle follows five steps:

1. **Gather candidates** — rule-based generators scan for:
   - Stalled questions (asked > N days ago, no answer)
   - Insufficient artifacts (sufficiency gate returned INSUFFICIENT)
   - Empty engagement areas (no stakeholders, no risks registered)
   - Agent work-items in QUEUED status

2. **Score and rank** — each candidate gets a composite score based on
   urgency, priority, and impact.

3. **Pick top K** — the orchestrator selects the top K tasks (default 3)
   to execute in this wake.

4. **Execute** — for each task:
   - Create human work-items if the task requires human commit
   - Execute directly if agent-only
   - Emit audit events

5. **Report** — produce a `WakeReport` persisted to disk for diagnostics.

## Triggers

| Trigger | When |
|---------|------|
| `MANUAL` | `praxis wake` command |
| `SCHEDULED` | Timer-based (configurable interval) |
| `STARTUP` | First wake when `praxis run` starts |
| `INBOX_EVENT` | External event (stub until integrations chunk) |
| `FILE_CHANGED` | Engagement files modified on disk |
| `WORKQUEUE_REPLY` | Human completes a work-item |

## Quiet hours

If `wake_cycle.quiet_hours` is set (e.g., `(23, 7)` for 11pm–7am), the
orchestrator defers wakes during that window to avoid disturbing users.

## Token budget

Each wake has a configurable token budget (default 50,000). When the budget
is approached, the orchestrator wraps up and reports `wake.budget_exceeded`.

## Daily plan

Once per day, the orchestrator generates a `DailyPlan` artifact:

- What happened in the last 24 hours
- Top prioritized work-items for today
- Open blockers

Saved to `<engagement>/.praxis/artifacts/reports/daily-plan-<date>.md`.

## CLI

```bash
praxis run          # Start continuous orchestration (Ctrl-C to stop)
praxis wake         # Single wake cycle
praxis wake --dry-run  # Plan only, don't execute
praxis plan today   # Generate today's daily plan
praxis status       # Engagement health snapshot
```

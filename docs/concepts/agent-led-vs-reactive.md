# Agent-Led vs Reactive

## The reactive model (what most tools do)

Most AI assistants are **reactive**: the human asks, the AI responds. The
human drives the conversation, decides what to work on next, and manages
their own task list. The AI is a tool, not a colleague.

## The agent-led model (what Praxis does)

Praxis inverts the relationship. The **agent** decides what needs attention
next, based on the engagement state:

- Are there stalled questions no one has followed up on?
- Are there artifacts that can't be produced because information is missing?
- Are there engagement areas with no data at all?

The agent generates work and presents it to the human via the **work queue**.
The human reviews, commits, rejects, or defers — but doesn't have to
remember what needs doing.

## Three things that make this work

1. **Proactive wake cycle** — the agent wakes up on a schedule and surveys
   the engagement, rather than waiting for prompts.

2. **Sufficiency gate** — before producing any artifact, the agent checks
   whether enough information exists. If not, it generates elicitation
   tasks rather than guessing.

3. **Structured engagement model** — stakeholders, questions, risks,
   glossary, timeline — all tracked in a schema that the agent can reason
   about programmatically.

## The human's role

The human is the **commit authority**. Nothing goes out without human
approval:

- Emails are drafted, not sent
- Meetings are proposed, not booked
- Artifacts are produced with caveats, not published

The daily interface is the **work queue**, not the chat window. The human
reviews what the agent has prepared, provides answers the agent needs, and
approves outgoing communications.

## Why this matters for business analysis

Business analysis is a coordination-heavy discipline. The bottleneck is
rarely "can we write the requirements?" — it's "did we talk to the right
people, ask the right questions, and follow up when answers didn't come?"

An agent-led approach keeps the engagement moving even when the human
analyst is busy with other work. The agent tracks what's stalled, what's
missing, and what's next — so the human can focus on the parts that
genuinely require human judgment.

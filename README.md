<img width="478" height="296" alt="image" src="https://github.com/user-attachments/assets/20942de3-057a-4c5b-9ad6-541b9b88cd45" />



> An open-source, **agent-led** framework for IT business analysis.

Praxis is a continuously-running analytical agent that performs the work of an
IT business / functional analyst. It drives the analytical process itself,
executes mechanical work directly, and hands off to a human operator only when
an action requires human commit (sending email, scheduling meetings, publishing
institutional artifacts).

Praxis is **not** a chatbot, copilot, or wrapper around an issue tracker. The
default surface is a work-queue and a typed engagement model — not a chat box.

---

## Why Praxis

| | |
|---|---|
| **Knowledge continuity** | Engagement state — decisions, constraints, glossary, open questions, stakeholders, risks — lives in typed YAML / Markdown files, not in an analyst's head. When a BA leaves, the replacement opens the queue and is productive in a day. |
| **Auditable by design** | Every decision, question, sufficiency verdict, wake cycle, and work-item transition is recorded with timestamp, actor, and subject. Useful for SOX / GLBA / HIPAA shops or any audit-conscious organisation. |
| **Local-first, no vendor lock-in** | All state on disk in human-readable formats — `cat`, `grep`, and `git diff` work. Engagements work fully offline. You own your engagement model; you can fork, backup, or migrate without permission. |
| **Provider-agnostic** | First-class adapters for Anthropic, OpenAI, OpenRouter, and any OpenAI-compatible local server (Ollama, vLLM, LM Studio). Switch models without changing engagements. |
| **Less expensive analyst time** | The agent drafts clarifying questions, scopes artifacts, and builds traceability matrices. The human focuses on judgment calls, stakeholder relationships, and decisions. |
| **Catches missing requirements early** | The Sufficiency Gate is an explicit, typed check before any artifact is produced — it identifies the gaps with named candidate sources, instead of letting you commit to building the wrong thing. |
| **Proactive, not reactive** | A scheduled wake cycle works the engagement while you sleep — surfaces stalled questions, detects new state changes, and flags insufficient artifacts. You open the queue and the agenda is already set. |
| **Engagement state as a git-friendly artifact** | Decisions are ADRs. Glossary is YAML. Backlog is Markdown. The whole engagement diffs cleanly; PR review actually works on analysis output. |

---

## Status

**Latest release: [v0.3.0](https://github.com/ermalha/Praxis-Engine/releases/tag/v0.3.0)** — agent-led, end-to-end, with a live TUI workspace.

Active development. The build plan is in `PROJECT.md` (architecture & principles)
and the per-feature briefs are in `chunks/`. Track progress in
`chunks/STATUS.md`.

---

## Install

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | required |
| [uv](https://docs.astral.sh/uv/) | latest | package manager |
| git | any | for source install |
| LLM API key | — | Anthropic, OpenAI, or OpenRouter (skip for local/offline) |

```bash
# From source (until PyPI publish)
git clone https://github.com/ermalha/Praxis-Engine.git
cd Praxis-Engine
uv sync --extra dev --extra all
```

---

## Five-minute tour

## The analytical loop

Praxis runs the analytical loop a business / functional analyst runs manually — but as software, on persistent state, with an audit trail.

  <img width="698" height="672" alt="image" src="https://github.com/user-attachments/assets/bd514ba3-0460-4a39-a84c-149c9a5c8dc6" />
            


The whole flow, from zero to a usable engagement, in about a dozen commands.

### 1. Create a profile
<img width="1882" height="619" alt="image" src="https://github.com/user-attachments/assets/02269fa1-77c7-4a9b-baa6-474f2517fb47" />


A profile pairs a name with an LLM model and the env var holding its key.
The actual key never lives in config — only the env var **name** does.

```bash
export OPENAI_API_KEY=sk-...
uv run praxis profile create alice \
  --provider openai --model gpt-4.1 --api-key-env OPENAI_API_KEY
# Auto-set as default profile (only profile).
```

### 2. Initialize an engagement

```bash
mkdir my-project && cd my-project
uv run praxis init --name "Acme Loan Intake" --methodology agile
```

### 3. Seed core state

```bash
uv run praxis engagement stakeholder add "Alice Chen" "VP of Lending"
uv run praxis engagement glossary    add "Member" "A credit-union customer."
uv run praxis engagement constraint  add "Must comply with GLBA." regulatory
uv run praxis engagement risk        add "Vendor sandbox delay" \
   "Core banking sandbox takes 2 weeks" -i medium -l medium
```

### 4. Ask the engagement-aware agent

`praxis ask -e .` primes the LLM with your engagement state (decisions,
constraints, open questions, stakeholders) and asks it to flag gaps rather
than invent. If the answer depends on facts not in your state, Praxis names
the gap and proposes the question to ask.

```bash
uv run praxis ask -e . "Should we save partial application progress automatically?"
```

> _Sample response (truncated):_
>
> > Based on the engagement, there is no explicit decision or constraint about auto-save. **Stakeholders to consult:** Devon Price (Product Manager); Alice Chen (VP of Lending). **Proposed Open Question:** "Should the MVP support autosaving partial application progress, and allow members to resume from a different device?"

### 5. Sufficiency check before producing an artifact

The Sufficiency Gate explicitly identifies missing information and maps each
gap to candidate stakeholders before you generate anything:

```bash
uv run praxis check spec "MVP functional requirements for online loan flow" -e .
```

The output names every information need with `known` / `partial` / `unknown`
status, cites the decisions and constraints that satisfy each need by ID, and
suggests:

```
Next: run praxis elicit --latest -e . to convert these gaps into
open questions and stakeholder-targeted drafted emails.
```

### 6. Elicit drafts

```bash
uv run praxis elicit --latest -e .
```

For each gap the gate identified, this produces a draft message (subject +
body + target stakeholder) and registers the corresponding open question
in the engagement.

### 7. Generate a state-grounded artifact

```bash
uv run praxis artifact generate scope-brief -e . --json
```

The output is a Markdown scope brief generated **only** from your engagement
facts, with an inline source note. The result is auto-bound to the latest
matching sufficiency report so the artifact's evidence trail is one click
away.

### 8. Daily status snapshot

```bash
uv run praxis status -e .
```

```
Engagement Status: Acme Loan Intake
┌─────────────────────────────────┬──────────┐
│ Stakeholders                    │ 4        │
│ Glossary terms                  │ 3        │
│ Decisions                       │ 2        │
│ Constraints                     │ 3        │
│ Risks                           │ 1        │
│ Open questions                  │ 3 / 3    │
│ Human work-items (active/total) │ 2 / 2    │
│ Agent work-items (active/total) │ 1 / 1    │
│ Last sufficiency                │ insufficient (2026-05-17) │
│ Last wake                       │ 2026-05-17T08:32:00Z │
└─────────────────────────────────┴──────────┘

Top critical open questions:
  - [b7f...] What is the explicit launch deadline?
```

### 9. Proactive wake cycle

```bash
uv run praxis wake -e .
```

The wake cycle detects state changes since the last wake, processes
insufficient sufficiency reports into actionable elicit tasks, and surfaces
stalled questions. **Idempotent** — repeat wakes don't pile up duplicate
work items, and PII-looking input in chat or ask emits a warning before
hitting the provider.

### 10. The TUI — your daily-driver workspace

```bash
uv run praxis tui -e .
```

Nine screens, live auto-refresh, switchable by number key. Screenshots below.

---

## The TUI

The TUI is the analyst's day-to-day surface. All screens auto-refresh on a
3-second interval, so agent-driven state changes appear live without manual
reload. Press the screen number (1–9), `r` to manually refresh, `w` to
trigger a wake cycle, `q` to quit.

### Queue (key `1`) — prioritized work-items

![Queue screen](docs/screenshots/01-queue.svg)

### Chat (key `2`) — agent REPL with engagement context

![Chat screen](docs/screenshots/02-chat.svg)

### Engagement (key `3`) — browse stakeholders, glossary, decisions

![Engagement screen](docs/screenshots/03-engagement.svg)

### Audit (key `4`) — every state change, timestamped

![Audit screen](docs/screenshots/04-audit.svg)

### Backlog (key `5`) — generated artifacts list

![Backlog screen](docs/screenshots/05-backlog.svg)

### Config (key `6`) — profile + engagement config

![Config screen](docs/screenshots/06-config.svg)

### Setup (key `7`) — guided project initialization

![Setup screen](docs/screenshots/07-setup.svg)

### Priorities (key `8`) — what to work on now

The "what should I work on?" view: top critical open questions, oldest
unanswered, top active work items, insufficient artifacts needing
elicitation.

![Priorities screen](docs/screenshots/08-priorities.svg)

### Artifact Viewer (key `9`) — rendered markdown of any generated artifact

![Artifact Viewer screen](docs/screenshots/09-artifact-viewer.svg)

> Screenshots are SVG, regenerated from a seeded demo engagement.
> Run `uv run python scripts/gen_screenshots.py` to refresh them.

---

## Architecture

```
                  ┌─────────────────────────────────────────┐
                  │        ENGAGEMENT MODEL (memory)         │
                  │  who, what, decisions, history, history  │
                  └────────────────┬────────────────────────┘
                                   │
                        ┌──────────┴──────────┐
                        │   ORCHESTRATOR      │
                        │  (the BA agent)     │
                        └──────────┬──────────┘
                                   │
                     ┌─────────────┴──────────────┐
                     │                            │
            ┌────────▼─────────┐         ┌────────▼─────────┐
            │  SUFFICIENCY     │   YES   │   ARTIFACT       │
            │     GATE         ├────────►│   PRODUCER       │
            └────────┬─────────┘         └──────────────────┘
                     │ NO
            ┌────────▼─────────┐
            │   ELICITATION    │
            │     PLANNER      │
            └────────┬─────────┘
                     │
                     ▼
            ┌──────────────────┐         ┌──────────────────┐
            │  HUMAN WORK-ITEM │◄───────►│  HUMAN OPERATOR  │
            │      QUEUE       │  reply  │   (analyst)      │
            └──────────────────┘         └──────────────────┘
```

Full architecture in `PROJECT.md`; diagrams in `docs/architecture.md`.

---

## Three things that make Praxis different from a chat agent

1. **Proactive wake cycle** — scheduled, not reactive turn-taking. The agent runs *because the clock said so*, not because you asked.
2. **Sufficiency Gate** — typed self-check before any artifact production. Praxis says "I don't have enough" loudly, with citations.
3. **Structured engagement model** — typed YAML/MD files (glossary, stakeholders, decisions, open questions, system landscape, risks, assumptions/constraints, timeline) instead of flat memory.

If a design choice you're considering would erase any of those three, stop and ask.

---

## Documentation

- **`PROJECT.md`** — architecture, principles, tech stack
- **`CHANGELOG.md`** — what shipped in each release
- **`CONTRIBUTING.md`** — how to contribute
- **`chunks/`** — feature briefs (numbered, dependency-ordered)
- **`docs/concepts/`** — engagement model, sufficiency gate, work-queue, agent-led vs reactive
- **`docs/how-to/`** — first chat, connect Jira, author a skill, etc.
- **`docs/reference/`** — API, schemas, keybinds, config

---

## License

MIT. See `LICENSE`.

---

## Acknowledgments

- [Nous Research](https://nousresearch.com/) — Hermes Agent foundational patterns
- [browser-use](https://github.com/browser-use) — Browser Harness bitter-lesson approach
- The [BABOK](https://www.iiba.org/career-resources/a-business-analysis-professional-s-foundation-for-success/) — names for the BA techniques the bundled skills derive from

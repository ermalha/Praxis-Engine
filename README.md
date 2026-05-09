# Praxis

> **An open-source, agent-led framework for IT business analysis.**

Praxis is a continuously-running analytical agent that performs the work of an
IT business/functional analyst. It drives the analytical process autonomously,
executes mechanical work itself, and delegates to a human operator only when
an action requires human commit (sending email, scheduling meetings, publishing
institutional artifacts).

Praxis is **not** a chatbot, copilot, or wrapper around an issue tracker. It's
an agent with a typed engagement model, a sufficiency-checking discipline, a
stakeholder-aware elicitation planner, and a human work-queue.

Inspired by [Hermes Agent](https://github.com/NousResearch/hermes-agent)
(Nous Research) and [Browser Harness](https://github.com/browser-use/browser-harness)
(browser-use), Praxis takes their architectural patterns — single agent class,
progressive-disclosure skills, plugin/registry tools, file-based artifacts,
provider-agnostic transport — and adds three things specific to BA work:

1. **Proactive wake cycle** instead of reactive turn-taking
2. **Sufficiency Gate** before any artifact production
3. **Structured engagement model** instead of flat memory files

---

## Status

🚧 **Active development.** The full architecture and 15-chunk build plan are
in `PROJECT.md` and `chunks/`. Track progress in `chunks/STATUS.md`.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Required |
| [uv](https://docs.astral.sh/uv/) | latest | Package manager |
| git | any | For source install |
| LLM API key | — | Anthropic, OpenAI, or OpenRouter. Not needed for offline/local models via `openai_compat`. |

### Offline vs. online operation

| Mode | What you need | Command |
|---|---|---|
| **Online** (cloud LLM) | API key for your provider | `uv run praxis chat` |
| **Offline** (local LLM) | Ollama / vLLM / LM Studio running locally | `uv run praxis chat` (configure `openai_compat` provider) |
| **Offline** (no LLM) | Nothing | `uv run praxis engagement …` (manage engagement model only) |

---

## Quick start

```bash
# Install (once published to PyPI)
uv pip install praxis-ba[all]

# Or from source
git clone https://github.com/ermalha/Praxis-Engine.git
cd Praxis-Engine
uv sync --extra dev --extra all

# Set up a profile with a model
uv run praxis profile create alice \
  --provider anthropic --model claude-sonnet-4-20250514 \
  --api-key-env ANTHROPIC_API_KEY

# Configure your API key
export ANTHROPIC_API_KEY=sk-ant-...
uv run praxis config show

# Initialize an engagement
mkdir my-project && cd my-project
uv run praxis init --name "My Project" --methodology agile

# Talk to the agent
uv run praxis chat

# Or let it run autonomously
uv run praxis run

# Or use the TUI
uv run praxis tui
```

---

## Key features

- **Agent-led, human-gated** — the agent drives; humans commit consequential actions
- **Provider-agnostic** — Anthropic, OpenAI, OpenRouter, or any OpenAI-compatible local server (Ollama, vLLM, LM Studio, etc.)
- **Local-first** — all engagement state on disk in human-readable formats; works fully offline
- **Optional integrations** — Jira, Confluence, email, browser harness, generic webhooks; the agent is fully functional without any of them
- **Typed engagement model** — glossary, stakeholders, decisions, open questions, system landscape, risks, assumptions/constraints, timeline
- **Sufficiency Gate** — before producing any artifact, the agent self-evaluates whether it has enough information and either produces or elicits
- **Structured work-queue** — typed, prioritized tasks the agent assigns to itself or to the human operator
- **Bundled skill library** — 12 production-grade BABOK-aligned skills covering interview prep, story drafting, INVEST checking, ADR authoring, decision matrices, RACI, BPMN modeling, traceability, gap analysis, status reporting, risk register entries, stakeholder analysis
- **CLI- and TUI-first** — no web server, no port conflicts, works over SSH

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

See `PROJECT.md` for the full architecture and `docs/architecture.md` for diagrams.

---

## Documentation

- **`PROJECT.md`** — Architecture, principles, tech stack
- **`chunks/`** — Build briefs, one per feature area
- **`docs/concepts/`** — Core concepts (engagement model, sufficiency gate, work-queue, agent-led-vs-reactive)
- **`docs/how-to/`** — Practical guides (first chat, connect Jira, author a skill, etc.)
- **`docs/reference/`** — API, schemas, keybinds, config
- **`CONTRIBUTING.md`** — How to contribute

---

## License

MIT. See `LICENSE`.

---

## Acknowledgments

- [Nous Research](https://nousresearch.com/) for Hermes Agent — the foundational architecture
- [browser-use](https://github.com/browser-use) for Browser Harness — the bitter-lesson approach to web automation
- The [BABOK](https://www.iiba.org/career-resources/a-business-analysis-professional-s-foundation-for-success/) for naming the techniques the bundled skills derive from

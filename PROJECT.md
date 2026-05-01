# Praxis — An Agent-Led Framework for IT Business Analysis

> **This file is the always-on context. Claude Code reads this before every chunk.**
> Keep it under 500 lines. Update it when fundamentals change, never for chunk-level details.

---

## What Praxis is

Praxis is an open-source, agent-led framework that performs the work of an IT
business/functional analyst. It is **not** a chatbot, copilot, or wrapper around
an issue tracker. It is a continuously-running analytical agent that:

- Drives the analytical process autonomously (decides what to do, when, and why)
- Executes mechanical work itself (reading, drafting, modeling, searching)
- Delegates to a human operator when an action requires human commit (sending
  email, scheduling meetings, publishing institutional artifacts)
- Maintains a structured, durable engagement model on disk
- Self-evaluates information sufficiency before producing any artifact
- Routes elicitation questions to the right stakeholder based on a learned
  stakeholder-knowledge map
- Works fully offline against local files; integrations (Jira, Confluence,
  email, browser) are optional enrichment

Praxis takes architectural inspiration from Hermes Agent (Nous Research) — single
agent class, progressive-disclosure skills, plugin/registry tools, file-based
artifacts, model-agnostic transport — but diverges in three crucial ways:

1. **Proactive wake cycle** instead of reactive turn-taking
2. **Sufficiency Gate** before any artifact production
3. **Structured engagement model** instead of flat memory files

---

## Design Principles (non-negotiable)

| # | Principle | Implication |
|---|-----------|-------------|
| P1 | Agent-led, human-gated | Agent drives; human commits actions touching other humans or institutional artifacts |
| P2 | Sufficiency before output | Every artifact production runs a Sufficiency Gate first |
| P3 | Stakeholder-aware | Agent maintains a model of who knows what and who decides what |
| P4 | Human-as-tool with a real contract | Delegation produces structured, queueable work-items |
| P5 | Mode driven by sufficiency, not interface | Artifact-first when info is enough; conversation-first when it isn't |
| P6 | Local-first, sync-ready | All state on disk in human-readable formats; backends pluggable |
| P7 | Observable & auditable by default | Every decision/action emits a structured audit event |
| P8 | Methodology-agnostic | No hard-coded Agile/SAFe/waterfall; methodology is config |
| P9 | Progressive disclosure | Skills, knowledge, tools loaded only when needed |
| P10 | Composability over features | Small surface area, plug in everything, files on disk |
| P11 | LLM-agnostic | Provider abstraction with at minimum: Anthropic, OpenAI, OpenRouter, OpenAI-compatible |
| P12 | Integrations are optional enrichment | Praxis must be fully functional with zero external connections |
| P13 | CLI-first UI | TUI/CLI is the primary interface; no web UI in v1 |
| P14 | TDD-ish | Tests written alongside each chunk; acceptance test runs at end of chunk |

If a design choice violates any of these, stop and ask the human before proceeding.

---

## Architecture overview

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

Six core components (built across chunks 7–13):

1. **Orchestrator** — the agent loop with proactive wake cycle (chunk 12)
2. **Engagement Model** — typed memory stores on disk (chunk 7)
3. **Sufficiency Gate** — information-needs analysis before output (chunk 9)
4. **Elicitation Planner** — who/what/how to ask (chunk 10)
5. **Human Work-Queue** — typed, persistent, prioritized (chunk 11)
6. **Tool Surface** — registry + skills + integrations (chunks 5–6, 14)

---

## Tech stack (locked)

| Layer | Choice |
|-------|--------|
| Language | Python 3.11+ |
| Package manager | `uv` (lockfile-based) |
| LLM transport | Provider abstraction: Anthropic native, OpenAI Chat Completions, OpenRouter, OpenAI-compatible (Ollama/vLLM/LM Studio/etc.) |
| CLI / TUI | `typer` for commands, `textual` for the work-queue TUI, `rich` for output formatting |
| Storage | SQLite + FTS5 for state/audit/conversation; YAML/MD files for engagement model and artifacts |
| Config | Pydantic v2 models; YAML on disk |
| Logging/audit | `structlog` → JSONL files |
| HTTP | `httpx` (async-capable) |
| Testing | `pytest`, `pytest-asyncio`, `respx` for HTTP mocks, `pytest-cov` |
| Lint/format/type | `ruff`, `mypy --strict` on `praxis/` package |
| Browser layer | Browser Harness symlink (post-install optional script) |
| Optional integrations | Jira REST, Confluence REST, IMAP/SMTP, generic webhooks — all behind feature flags |

---

## Repo structure (single repo, single package, monorepo-friendly internal layout)

```
praxis/
├── pyproject.toml
├── uv.lock
├── README.md
├── PROJECT.md               # this file
├── CONTRIBUTING.md
├── LICENSE                  # MIT
├── .github/workflows/       # CI: lint, type, test, coverage
├── docs/
│   ├── architecture.md
│   ├── design-principles.md
│   ├── concepts/
│   ├── how-to/
│   └── reference/
├── chunks/                  # build briefs (this directory)
├── src/
│   └── praxis/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli/             # typer commands
│       ├── tui/             # textual app(s)
│       ├── core/
│       │   ├── orchestrator.py
│       │   ├── agent.py
│       │   ├── sufficiency.py
│       │   ├── elicitation.py
│       │   └── prompt.py
│       ├── transport/       # LLM providers
│       │   ├── base.py
│       │   ├── anthropic.py
│       │   ├── openai.py
│       │   ├── openrouter.py
│       │   └── compat.py
│       ├── engagement/      # typed memory
│       │   ├── glossary.py
│       │   ├── stakeholders.py
│       │   ├── decisions.py
│       │   ├── questions.py
│       │   └── ...
│       ├── storage/         # SQLite + file IO
│       ├── tools/           # tool registry + built-ins
│       ├── skills/          # skill loader
│       ├── workqueue/       # human work-item queue
│       ├── audit/           # structured logging
│       ├── config/          # Pydantic models, profiles
│       └── integrations/    # optional connectors (lazy-loaded)
│           ├── jira/
│           ├── confluence/
│           ├── email/
│           └── webhook/
├── skills/                  # bundled starter skill library (data, not code)
│   ├── elicitation/
│   ├── analysis/
│   ├── modeling/
│   ├── requirements/
│   ├── decision/
│   ├── communication/
│   └── governance/
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

User-runtime data lives outside the repo:

```
~/.praxis/                   # global: profiles, shared skills, model configs
├── profiles/
│   └── default/
├── skills/                  # user-installed skills (in addition to bundled)
└── config.yaml

<project>/.praxis/           # per-engagement state
├── engagement/              # glossary, stakeholders, decisions, questions, etc.
├── artifacts/               # stories, specs, models, matrices, reports
├── state/                   # SQLite, work-queue, audit log
└── skills/                  # engagement-specific skills (auto-created, human-promoted)
```

---

## Cross-chunk conventions (every chunk follows these)

### Code style
- `ruff` config (in `pyproject.toml`) — line length 100, default rule set + I, N, UP, B, A, C4, RET, SIM, ARG
- `mypy --strict` on the `praxis/` package; integrations may relax to non-strict
- All public functions have type hints and docstrings
- Docstrings: Google style
- No `print()` in library code — use `structlog` logger
- No `assert` for runtime checks — use proper exceptions

### Errors
- Define a `PraxisError` base exception in `src/praxis/__init__.py`
- Subclass per subsystem: `ConfigError`, `StorageError`, `TransportError`, `ToolError`, `SkillError`, `EngagementError`
- Never silently swallow exceptions; log + re-raise or convert to a typed error

### Logging
- Use `structlog` everywhere
- Every component logs with a `component=` field
- Audit events (chunk 1 sets up the writer) go to `~/.praxis/audit.jsonl` and per-engagement `.praxis/state/audit.jsonl`

### Configuration
- All config via Pydantic v2 models in `praxis/config/`
- Layered resolution: defaults → `~/.praxis/config.yaml` → `<project>/.praxis/config.yaml` → env vars (`PRAXIS_*`) → CLI flags
- Profiles isolate config + storage + skills (Hermes pattern)

### Testing
- Every public function has at least one unit test
- Every chunk has at least one integration test demonstrating end-to-end behavior of that chunk's deliverable
- Coverage threshold: 80% on `praxis/` package (relaxed for integrations)
- Tests use `respx` for HTTP mocks; never hit real APIs in tests
- Fixtures in `tests/conftest.py`

### Commits
- Conventional Commits: `feat(scope): ...`, `fix(scope): ...`, `test(scope): ...`, `docs(scope): ...`, `chore: ...`
- One logical change per commit
- Commit at meaningful checkpoints during a chunk, not just at end

### Documentation
- Every chunk produces or updates docs in `docs/`
- Architecture docs use Mermaid for diagrams
- Reference docs auto-generated where possible (Pydantic schemas, CLI help)

---

## How to work on a chunk

When starting a chunk:

1. Read this `PROJECT.md` in full
2. Read the specific `chunks/NN-name.md` brief
3. Read the `chunks/00-conventions.md` (cross-cutting rules and patterns)
4. Read any prior chunks listed as dependencies
5. Review existing code in directories touched by this chunk
6. Plan: list the files to create/modify and the test approach BEFORE writing code
7. Implement test-first where practical (TDD-ish): write failing test → make it pass → refactor
8. Run the chunk's acceptance test at the end
9. Update relevant docs
10. Commit with a clear message referencing the chunk

If anything in the chunk brief is ambiguous, **stop and ask** rather than guess.

---

## Glossary of Praxis-specific terms

- **Engagement** — a project, programme, or workstream Praxis is helping with. One engagement = one `.praxis/` directory.
- **Profile** — a user identity / configuration scope under `~/.praxis/profiles/<name>/`. Multiple profiles can run side-by-side.
- **Wake cycle** — the orchestrator's proactive iteration loop. Triggered by schedule, event, or manual `/wake`.
- **Sufficiency Gate** — the typed self-check the agent runs before producing any artifact.
- **Work-item** — a typed, queued task assigned to either the agent itself or the human operator.
- **Skill** — a SKILL.md-format procedural-knowledge artifact (BABOK technique, project pattern, etc.).
- **Artifact** — a deliverable produced by the agent (story, spec, model, matrix, report).
- **Engagement Model** — the typed memory of a single engagement (glossary, stakeholders, decisions, etc.).
- **Stakeholder-knowledge map** — the part of the engagement model that records who knows what and who decides what.
- **Audit event** — an immutable, structured log entry capturing a state change or decision.

---

## Status & next chunk

Each chunk's brief specifies its dependencies. Always work in chunk-number order
unless the brief explicitly says you can parallelize. The current state of the
build is tracked in `chunks/STATUS.md`.

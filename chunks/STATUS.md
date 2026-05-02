# Praxis Build Status

Track the build of Praxis chunk-by-chunk. Update this file at the end of each
chunk by checking the box.

## Phase 1 — Foundations

- [x] **01 — Project Skeleton & Dev Environment** (`chunks/01-skeleton.md`)
- [x] **02 — Configuration & Profiles** (`chunks/02-config-profiles.md`)
- [x] **03 — Storage Layer** (`chunks/03-storage.md`)
- [x] **04 — LLM Transport Layer** (`chunks/04-transport.md`)

## Phase 2 — Agent Core

- [x] **05 — Tool Registry & Execution** (`chunks/05-tools.md`)
- [x] **06 — Skill System** (`chunks/06-skills.md`)
- [x] **07 — Engagement Model API** (`chunks/07-engagement-model.md`)
- [x] **08 — Conversation Loop** (`chunks/08-conversation-loop.md`) — **Mini-Hermes milestone**

## Phase 3 — Praxis Distinctives

- [x] **09 — Sufficiency Gate** (`chunks/09-sufficiency-gate.md`)
- [ ] **10 — Elicitation Planner** (`chunks/10-elicitation-planner.md`)
- [ ] **11 — Human Work-Queue** (`chunks/11-work-queue.md`)
- [ ] **12 — Wake Cycle / Orchestrator** (`chunks/12-wake-cycle.md`) — **Praxis-distinctive milestone**

## Phase 4 — Real-World Surface

- [ ] **13 — TUI** (`chunks/13-tui.md`)
- [ ] **14 — Integrations Bundle** (`chunks/14-integrations.md`)
- [ ] **15 — Starter Skill Library** (`chunks/15-skills-library.md`)

---

## Quality gates per chunk

Every chunk's "Definition of done" requires:

- [ ] All deliverables in the brief produced
- [ ] Acceptance test in `tests/integration/test_chunk_NN.py` passes
- [ ] `pytest` green (no skipped tests without justification)
- [ ] `ruff check .` green
- [ ] `ruff format --check .` green
- [ ] `mypy src/praxis` green
- [ ] Coverage ≥ 80% on the chunk's subsystem
- [ ] Docs in `docs/` updated where the brief specified
- [ ] This file updated with the chunk's checkbox checked
- [ ] Conventional Commits used; one logical change per commit
- [ ] CI green on the resulting push

## Defensible cut-lines

If you ever need to ship something before the full 15 chunks:

- **After chunk 8** — A working CLI chat agent with engagement memory, skills, and tools. Useful as a "Hermes-for-BAs" alone.
- **After chunk 12** — A fully agent-led BA assistant via CLI. The Praxis vision delivered, just less ergonomic than with the TUI.
- **After chunk 13** — A daily-driveable analyst tool. No external integrations yet; everything local.

## Definition of v0.1.0 release

All 15 chunks complete + a `tests/e2e/test_full_engagement.py` that exercises a
realistic week-long engagement scenario end-to-end against mocked LLMs.

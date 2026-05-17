# Changelog

All notable changes to Praxis are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and Praxis adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.1] — 2026-05-17

**Theme:** Trustable surface + proactive cycle.

The v0.2.0 real-world scenario test (`~/praxis-realworld-eval/final-report.md`)
classified the release as YELLOW because the most discoverable commands
(`ask`, `queue`, `wake`) misbehaved on first contact — `ask` hallucinated
without engagement context, `queue` hid agent items by default, `wake` piled
duplicates and ignored new state, and several `--json` outputs were
unparseable. v0.2.1 closes those findings.

### Fixed

- **D-028** — `praxis ask` is engagement-aware (`-e/--engagement`) and is
  primed with a flag-uncertainty system prompt so it stops inventing firm
  requirements. Closes **RW-002**, **RW-006**, **RW-007**.
- **D-029** — `ask`, `chat`, `doctor`, `check`, `artifact`, `elicit` now
  resolve the active default profile when `--profile` is omitted (matches
  the existing `run`/`wake` pattern). Closes **RW-001**.
- **D-030** — All `--json` outputs go through `typer.echo(json.dumps(...))`
  instead of Rich's wrapping renderer, so long string values no longer
  break `jq` / `python -m json.tool`. 21 sites across 9 CLI modules.
  Closes **RW-017**.
- **D-031** — `praxis queue` default now shows all assignees (was: human
  only). Adds `--assignee {human,agent}` and `--human-only` for filtering;
  `--all` keeps its status-axis semantic. Closes **RW-010**.
- **D-035** — `WakeReport.audit_event_count` reports the real number of
  audit events emitted during a wake cycle (was always 0). Implemented via
  a new `praxis.audit.counted()` context manager. `tokens_used` remains 0
  because v0.2.x wake handlers are rule-based; transport token plumbing
  will be added if/when wake starts calling the LLM inline.
  Closes **RW-012**.

### Added / Changed

- **D-032** — `WorkQueueRepo.enqueue_deduped(*, dedup_key, ...) ->
  (item, was_created)`. All four wake handlers route through it with a
  stable per-task dedup key, so repeat wakes against the same engagement
  state stop piling up identical work items. Closes **RW-011**.
- **D-033** — Wake reads the most recent prior wake report's `ended_at`
  and diffs the engagement state against that timestamp. New
  `StateChange` model + `WakeReport.state_changes_since_last_wake` field.
  Each diff entry produces a deduped `REVIEW_ARTIFACT` agent task so the
  agent reacts to decisions/constraints/risks/answered-questions added
  between cycles. First wake (no prior report) emits no diff tasks.
  Closes **RW-015**.
- **D-034** — Wake replaces the vague `"Re-evaluate: spec"` placeholder
  with an actionable `AGENT_FOLLOW_UP` titled
  `"Elicit drafts for {kind}: {target}"`. Payload carries the sufficiency
  report file; description points the operator at
  `praxis elicit --latest`. Closes **RW-016**.

### Quality

- **471 tests passing** (was 439 at v0.2.0), coverage 84.07%.
- All four gates green per commit: `pytest`, `ruff check`, `ruff format`,
  `mypy --strict src/praxis`.
- 8 conventional commits, one logical change each (`D-028..D-035`).

### Known limitations

- `wake.tokens_used` still reports 0 — accurate for v0.2.x (no LLM in
  wake cycle), but cosmetically surprising. Will be wired up if/when
  wake gains inline LLM calls.
- D-034 enqueues an elicit task; it does NOT auto-execute. The "Option B"
  inline-elicit variant was deferred to a future release because it would
  change wake from coordinator to executor.
- Three TUI screens promised in the v0.3.0 objectives (live Backlog,
  Priorities, Artifact Viewer) are still v0.3.0 work — not in v0.2.1.

---

## [0.2.0] — 2026-05-12

Initial public release tested in `~/praxis-realworld-eval/final-report.md`.
See git log for details prior to 0.2.1.

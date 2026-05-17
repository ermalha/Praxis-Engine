# Changelog

All notable changes to Praxis are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and Praxis adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] — 2026-05-17

**Theme:** Agent-led, end-to-end + live TUI workspace.

Closes the v0.2.0 retest's remaining minor/nit findings (Batches 3 + 4)
and ships the three TUI screens promised in the v0.3.0 objectives —
the analyst's TUI now reflects engagement state in near-real-time.

### Pipeline coherence (Batch 3)

- **D-036** — `praxis check` prints a `Next: run praxis elicit --latest
  -e <engagement>` hint when the verdict is `insufficient`. Sufficient
  verdicts and `--json` mode get no hint. Closes **RW-003**.
- **D-037** — `artifact generate` auto-binds the latest matching
  sufficiency report (`scope-brief↔spec`, `backlog`, `traceability`).
  `ArtifactResult.sufficiency_verdict` and `sufficiency_report_path`
  are populated; pretty mode emits a dim "Bound sufficiency report"
  line. Closes **RW-009**.
- **D-038** — Sufficiency gate's engagement context now includes full
  decision bodies (capped 300 chars), constraints (type + statement),
  and recent assumptions. The system prompt instructs the model to
  consult these first and cite IDs in `have`. Closes **RW-004**.
- **D-039** — Wake-generated work items now populate
  `related_artifact_ids` (insufficient handler ← sufficiency report
  stem) and `related_question_ids` (state-change handler ← answered
  question id), making them traceable to the engagement state that
  triggered them. Closes **RW-013**.

### Polish (Batch 4)

- **D-040** — `praxis status` title uses `load_engagement_config(eng).name`
  (was the dir name); metric table covers all entity types, work-item
  splits (human/agent active/total), last wake, last sufficiency verdict;
  a second panel lists top 3 critical open questions. Closes **RW-005**.
- **D-041** — `praxis artifact list` accepts `--profile` for CLI
  consistency with `artifact generate`. Closes **RW-008**.
- **D-042** — `praxis queue commit` accepts `--message` / `-m` as
  aliases for `--note` / `-n`. Closes **RW-014**.
- **D-043** — New `praxis.safety` subsystem with PII detector (SSN
  regex + Luhn-validated card numbers). `ask` / `chat` print a stderr
  warning before sending PII-looking input to the LLM; never blocks.
  `PRAXIS_PII_GUARD=off` silences. Closes **RW-018**.

### TUI workspace

- **D-044** — Backlog and Work Queue screens auto-refresh every 3
  seconds (Textual `set_interval`) so agent-driven state changes appear
  without a manual reload. `r` keybind preserved for manual refresh.
- **D-045** — New **Priorities** screen (screen 8). Four sections: top
  critical open questions, oldest unanswered questions, top active
  work items, and insufficient artifacts needing elicitation. Read-
  only, auto-refresh on 3s.
- **D-046** — New **Artifact Viewer** screen (screen 9). DataTable
  on the left, Textual `Markdown` widget on the right rendering the
  selected artifact's contents. Coexists with Backlog (regenerate
  action deferred to a future release — requires transport plumbing
  inside the TUI).

### Quality

- **529 tests passing** (was 471 at v0.2.1, +58), coverage 84.36%.
- All four gates green per commit: `pytest`, `ruff check`,
  `ruff format`, `mypy --strict src/praxis`.
- 11 conventional commits since v0.2.1 (D-036…D-046).

### Known limitations / deferred work

- TUI **regenerate** action is not wired into the Artifact Viewer.
  Requires profile/model/transport plumbing inside the Textual app;
  candidate for v0.4.
- TUI **Markdown render** is the standard `textual.widgets.Markdown`
  with default styling — no syntax highlighting customisation.
- Test coverage for Textual screens is **introspection-only** (binding
  + on_mount source check); full pilot-driver tests would be useful
  but out of scope for v0.3.0.
- D-038's verdict-improvement claim is verified by prompt-construction
  tests only; manual real-LLM re-run of the §10.2 retest scenario is
  recommended to confirm verdicts materially improve when decisions
  are persisted.

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

# Changelog

All notable changes to Praxis are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and Praxis adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.4.0] — 2026-05-23

**Theme:** Adoption surface — scriptable chat, friendlier errors, completed CRUD.

Three focused features that close the v0.4.0 Tier 2 plan (D-050 / D-051 /
D-052). All three target adoption: making the CLI usable from scripts /
CI, making transport failures self-actionable, and completing the gaps
in the engagement-entity verbs that previous releases left behind.

### Added

- **D-050** — `praxis chat --message/-m "..."` runs **one** turn through
  the full `ChatRuntime` (tools, session, slash commands) and exits 0.
  The REPL banner is suppressed so stdout stays clean for callers piping
  into `jq` or similar. PII guard (D-043) still fires on the single
  turn. Difference vs. `praxis ask`: `chat -m` keeps the runtime, so the
  agent can call engagement / queue tools; `ask` is stateless.
- **D-052** — Completed CRUD verbs on `praxis engagement assumption`
  and `praxis engagement constraint`:
  - `assumption get|update|remove`
  - `constraint get|update|remove`

  Updates are partial (only supplied flags are written) and preserve
  untouched fields including the `validated` flag on assumptions. Both
  `get` variants support `--json` for scripting. Closes **NEW-001**.
- **D-052** — `praxis engagement question open` now accepts
  `--answerers <stakeholder-ids>` and `--blocks <artifact-ids>` (both
  comma-separated). The repo accepted these fields since 0.2.x; only
  the CLI binding was missing. Closes **NEW-004**.

### Changed

- **D-051** — Transport errors are now provider-specific and actionable.
  New `praxis.transport.errors.translate_provider_exception()` duck-types
  on `type(exc).__module__` + class name (both OpenAI and Anthropic
  SDKs share the Stainless-generated exception hierarchy) and maps each
  kind to a tailored message:

  - `auth`         → names the env var to set
  - `permission`   → names the model the key lacks access to
  - `rate_limit`   → suggests retry / tier upgrade
  - `not_found`    → names the missing model
  - `bad_request`  → carries the SDK's detail
  - `server_error` → tells the user to retry later
  - `connection`   → blames the network with the SDK's detail
  - `timeout`      → identifies a timed-out request

  Each `TransportError` carries `details["kind"]` so future retry logic
  can branch programmatically without string-matching. Unknown
  exceptions fall through to today's generic message — behaviour is
  **strictly additive**, no existing assertion breaks. Closes
  **NEW-003**.

### Breaking (CLI)

- **D-050** — `praxis chat --model` no longer accepts the `-m` short
  alias. `-m` is now bound to `--message`, matching `git commit -m` and
  `praxis queue commit -m` convention. The full `--model gpt-4.1`
  long form still works. `--model -m` is intact on `artifact`, `check`,
  and `elicit` (those have no `--message` conflict).

### Documentation

- **D-050** — `docs/how-to/first-engagement.md` gains a "Scripting and
  CI" section with a `chat -m` vs `ask` comparison table.

### Quality

- **571 tests passing** (+32 since v0.3.1), coverage **84.42%**.
- All four gates green per commit: `pytest`, `ruff check`,
  `ruff format`, `mypy --strict src/praxis`.
- 5 conventional commits since v0.3.1 (D-050 ×2 / D-051 / D-052 + bump).

### Known limitations / deferred to v1.0.0

- **D-055** — Multi-engagement awareness (`praxis engagements list/
  show/switch`, registry, TUI header) deferred. Larger feature; queued
  for a dedicated cycle.
- **D-053 / D-054 / D-056** — Superseded by v1.0.0 plan items
  (D-067 TUI regenerate, D-062 pilot tests, D-066 `doctor` expansion).
  See `~/praxis-realworld-eval/v1.0.0-plan.md` in the eval workspace.

---

## [0.3.1] — 2026-05-23

**Theme:** Automation patch + adoption walkthrough.

A small follow-up release closing the one finding surfaced during the
v0.3.0 retest (RW-019) plus the two adoption-friction items called out
by the Hermes external audit. No runtime-behavior changes beyond the
structlog routing fix; the rest is install path, documentation, and
verification.

### Fixed

- **D-047** — Configure structlog at package import: route console
  output to stderr (`PrintLoggerFactory(file=sys.stderr)`), filter at
  WARNING level by default, opt-in DEBUG via `PRAXIS_DEBUG=1`. The
  default factory previously wrote to stdout, which corrupted
  `praxis ... --json | jq` pipelines whenever an audit event fired.
  Audit JSONL on-disk writes are unaffected — those use direct file
  opens, not structlog. Closes **RW-019**.

### Added

- **D-048** — README now leads with a one-command install:
  `uv tool install --python 3.12 "praxis-ba[all] @ git+...@v0.3.1"`.
  Drops `praxis` onto your PATH in an isolated environment. The
  `git clone + uv sync` form is retained as "Development install."
  A real PyPI publish is queued for a future release.
- **D-049** — New `docs/how-to/first-engagement.md` — a full
  setup-to-output walkthrough (~540 lines) verified by cold-run on a
  fresh sandbox. Every output block is real captured stdout, not
  hand-written. Documents the actual `.praxis/` layout
  (`config.yaml` + `engagement/` subdir), the 5-column sufficiency
  table including the `Blocker` column, and the full timestamp in the
  status snapshot's `Last sufficiency` value.

### Changed

- **D-049** — README's "Five-minute tour" (~140 lines of step-by-step
  commands) replaced with a 22-line "Quick start" that links to the
  new how-to. The logo, analytical-loop diagram, and TUI gallery are
  retained at their original positions.
- **D-049** — `CONTRIBUTING.md` adds a "must remain runnable" line
  pointing at the new how-to; CI exercises the non-LLM steps on every
  push (`tests/integration/test_tour_offline.py`, 7 tests).

### Quality

- **539 tests passing** (+10 since v0.3.0), coverage **84.39%**.
- All four gates green per commit: `pytest`, `ruff check`,
  `ruff format`, `mypy --strict src/praxis`.
- 7 conventional commits since v0.3.0 (D-047 / D-049 ×3 / D-048 +
  one image-restoration commit + version bump).

### Known limitations / deferred work

- Real `pip install praxis-ba` from PyPI is still queued (D-048
  Option A); the `uv tool install` form documented here is the
  supported one-command install path until then.
- The how-to's LLM-using steps (ask, check, elicit, artifact generate)
  are exercised by the documented cold-run procedure, not by CI.
- All Hermes-review items that aren't part of v0.3.1 (architectural
  hardening — TUI wake plumbing, EngagementSnapshot read model, atomic
  writes, real Textual pilot tests, etc.) are queued for v1.0.0 (see
  the v1.0.0 plan in the eval workspace).

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

# Chunk 13 — TUI (the analyst's daily home)

**Phase:** Real-World Surface | **Estimated effort:** 5 hours | **Dependencies:** 01–12

---

## Context

Up to now, Praxis is fully usable via CLI. This chunk delivers the **TUI** —
a Textual-based terminal application that becomes the analyst's daily home:
a live work-queue, the conversation pane, the engagement browser, and the
audit timeline, all in one place. Like Claude Code, like Hermes' interface,
no web server, no browser, no port conflicts.

This chunk does NOT add new functionality. It surfaces what chunks 1–12
already deliver in a single, ergonomic workspace.

---

## Scope

### App structure (`src/praxis/tui/app.py`)

A Textual `App` with four screens:

1. **WorkQueueScreen** (default) — prioritized queue with detail pane
2. **ConversationScreen** — chat with the agent (wraps `praxis chat`)
3. **EngagementScreen** — browse glossary, stakeholders, decisions, etc.
4. **AuditScreen** — live tail of audit events; filter, search

Footer shows: profile, engagement, model, last wake, pending items count.
Header shows: active screen, keybinds.

Global keybinds:
- `1`/`2`/`3`/`4` — switch screens
- `q` — quit
- `?` — help overlay
- `r` — refresh current screen
- `w` — trigger manual wake (calls `orchestrator.wake_once`)
- `a` — show last 5 audit events as flash overlay

### WorkQueueScreen

Two-pane layout:
- Left: queue list (priority, title, type, age) — sortable
- Right: detail of selected item (description, payload pretty-printed,
  related artifacts/questions/stakeholders, action buttons)

Actions on selected item:
- `Enter` — start (status → IN_PROGRESS)
- `c` — commit (DONE) — opens a textarea modal for completion note + return data
- `r` — reject — opens textarea for rationale
- `d` — defer — opens date picker (until)
- `e` — open the payload in `$EDITOR` (e.g., to edit a drafted email before commit)
- `o` — "open in browser" — for items with a URL payload (e.g., a Jira link)

When the agent is running (orchestrator mode), the queue updates live —
new items appear, transitions reflect immediately. Implemented via a
`watchdog` observer on `<engagement>/.praxis/state/workqueue.jsonl`.

### ConversationScreen

A Textual chat widget wrapping the chunk-8 `Agent.stream_turn`. Streamed
text appears as it arrives; tool calls render as collapsible panels;
approval prompts appear as modal dialogs.

Special: when the orchestrator is also running in the same engagement, this
screen surfaces "the agent has a question for you" notifications inline (a
yellow bar across the bottom).

### EngagementScreen

Tabbed view of:
- Glossary (searchable table)
- Stakeholders (table, expand for detail)
- Decisions (list of ADRs with markdown preview)
- Open Questions (filtered by status)
- Systems / Risks / Assumptions / Constraints / Timeline

Read-only by default. `Ctrl-E` opens the underlying file in `$EDITOR` for power users.

### AuditScreen

Live tail of `audit.jsonl`:
- Filter by event type, actor, component, time range
- Search by subject id or correlation id
- Click an event to see the full payload pretty-printed
- Export filtered view to `audit-export.jsonl`

### Live updates

A background `FileWatcher` watches:
- `<engagement>/.praxis/state/workqueue.jsonl`
- `<engagement>/.praxis/state/audit.jsonl`
- `<engagement>/.praxis/state/wake-reports/`

Posts Textual messages so screens refresh.

### CLI

```
praxis tui                         # opens the TUI
praxis tui --screen queue          # opens directly to the queue screen
```

`praxis run` and `praxis tui` are typically used together (in two terminals
or via a `--with-orchestrator` flag that runs the orchestrator in a thread).

For v1, recommend two terminals; the integrated mode is a stretch goal here:

```
praxis tui --with-orchestrator     # background orchestrator + foreground TUI
```

---

## Deliverables

- `src/praxis/tui/` — app, screens, widgets
- `praxis tui` and `praxis tui --with-orchestrator` CLI commands
- File watcher for live updates
- Tests:
  - Smoke: app launches and quits cleanly with `tmp_engagement`
  - Each screen renders without errors against a populated engagement
  - Action keybinds dispatch the right backend calls (mock the repos and
    assert the calls)
  - File-change events trigger refresh
- `tests/integration/test_chunk_13.py` — uses `Pilot` (Textual's test driver)
- `docs/how-to/use-the-tui.md` with screenshots
- `docs/reference/keybinds.md`
- Update `chunks/STATUS.md`

---

## Acceptance test

```python
async def test_tui_smoke(tmp_engagement_with_data):
    app = PraxisApp(engagement_path=tmp_engagement_with_data)
    async with app.run_test() as pilot:
        # default screen is queue
        assert isinstance(app.screen, WorkQueueScreen)
        # press 3 to go to engagement screen
        await pilot.press("3")
        assert isinstance(app.screen, EngagementScreen)
        # press q to quit
        await pilot.press("q")
    # no exceptions
```

---

## Explicit non-goals

- No web UI — explicitly out of scope until a future v2 if community demand
- No charts/graphs — text + tables only
- No multi-engagement view — one engagement per TUI session

---

## Notes

- Textual is fast-evolving; pin the version in `pyproject.toml` extras.
- Mouse support is on by default in Textual; expose mouse actions where
  natural but never make them required (terminal-over-SSH must work).
- All TUI state mutations go through the same repo APIs as CLI commands;
  no shortcut paths. This guarantees audit consistency.
- Color theme follows terminal default; provide `light` and `dark` variants
  via Textual's CSS.

---

## Definition of done

- All deliverables present
- TUI launches against a real engagement and is genuinely useful
- Acceptance test passes
- `pytest`, `ruff`, `mypy` green (mypy can be relaxed on tui/ subpackage if needed)
- `chunks/STATUS.md` updated

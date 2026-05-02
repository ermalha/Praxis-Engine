# Storage Schema Reference

Praxis uses **SQLite + FTS5** for runtime state and **YAML/Markdown files**
for the engagement model. Both are managed through the `praxis.storage`
subsystem.

---

## SQLite Database

Located at `<engagement>/.praxis/state/praxis.db`. Created automatically by
`init_engagement()`. Uses WAL journal mode and enforces foreign keys.

### sessions

Tracks conversation sessions.

| Column | Type | Constraints |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `parent_id` | TEXT | FK → sessions(id), nullable |
| `profile` | TEXT | NOT NULL |
| `started_at` | TEXT | NOT NULL (ISO 8601) |
| `ended_at` | TEXT | nullable (ISO 8601) |
| `summary` | TEXT | nullable |
| `metadata_json` | TEXT | NOT NULL, default `'{}'` |

### messages

Stores conversation turns within sessions.

| Column | Type | Constraints |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `session_id` | TEXT | NOT NULL, FK → sessions(id) |
| `turn` | INTEGER | NOT NULL |
| `role` | TEXT | NOT NULL (`user`, `assistant`, `system`, `tool`) |
| `content` | TEXT | NOT NULL |
| `tool_calls_json` | TEXT | nullable |
| `created_at` | TEXT | NOT NULL (ISO 8601) |

**Unique constraint:** `(session_id, turn)`
**Index:** `idx_messages_session` on `session_id`

### messages_fts (FTS5 virtual table)

Full-text search index over message content. Kept in sync by triggers
(`messages_ai`, `messages_ad`, `messages_au`).

Indexed columns: `content`, `role`
Unindexed columns: `session_id`, `message_id`

### workitems

The human work-queue: questions, tasks, and reviews awaiting action.

| Column | Type | Constraints |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `type` | TEXT | NOT NULL |
| `status` | TEXT | NOT NULL (`pending`, `in_progress`, `completed`, `cancelled`) |
| `priority` | TEXT | NOT NULL (`low`, `medium`, `high`, `critical`) |
| `payload_json` | TEXT | NOT NULL |
| `created_at` | TEXT | NOT NULL (ISO 8601) |
| `updated_at` | TEXT | NOT NULL (ISO 8601) |
| `deadline` | TEXT | nullable (ISO 8601) |
| `completed_at` | TEXT | nullable (ISO 8601) |

**Index:** `idx_workitems_status` on `(status, priority)`

### audit

SQLite mirror of the JSONL audit trail. Allows structured queries.

| Column | Type | Constraints |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `timestamp` | TEXT | NOT NULL (ISO 8601) |
| `profile` | TEXT | NOT NULL |
| `engagement` | TEXT | nullable |
| `actor` | TEXT | NOT NULL (`agent`, `human`, `system`) |
| `component` | TEXT | NOT NULL |
| `event_type` | TEXT | NOT NULL |
| `subject_id` | TEXT | nullable |
| `correlation_id` | TEXT | nullable |
| `payload_json` | TEXT | NOT NULL, default `'{}'` |

**Indexes:** `idx_audit_time` on `timestamp`, `idx_audit_event` on `(event_type, timestamp)`

### _migrations

Tracks which schema migrations have been applied.

| Column | Type | Constraints |
|---|---|---|
| `version` | INTEGER | PRIMARY KEY |
| `name` | TEXT | NOT NULL |
| `applied_at` | TEXT | NOT NULL (ISO 8601) |

---

## Migrations

SQL migrations live in `src/praxis/storage/migrations/` and are numbered
`NNN_description.sql`. The `run_migrations()` function applies them in
order, skipping any already recorded in `_migrations`.

---

## File-based Storage

The `praxis.storage.files` module provides typed helpers:

- `read_yaml_typed(path, Model)` / `write_yaml_typed(path, obj)` —
  round-trip Pydantic models as YAML
- `read_markdown_with_frontmatter(path, Model)` /
  `write_markdown_with_frontmatter(path, frontmatter, body)` — Markdown
  with validated YAML frontmatter

All writes are atomic: write to `<path>.tmp`, `fsync`, rename.

---

## Audit Trail

Audit events are emitted via `praxis.audit.emit()` and written to:

1. **Global JSONL** — `~/.praxis/audit.jsonl`
2. **Per-engagement JSONL** — `<engagement>/.praxis/state/audit.jsonl`
3. **Per-engagement SQLite** — the `audit` table above

The `tail()` and `query()` functions in `praxis.audit` read from the JSONL
files.

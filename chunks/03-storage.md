# Chunk 03 — Storage Layer

**Phase:** Foundations | **Estimated effort:** 4–5 hours | **Dependencies:** 01, 02

---

## Context

Two distinct storage mechanisms work side by side throughout Praxis:

1. **SQLite (with FTS5)** for runtime state — sessions, messages, work-items, audit mirror
2. **Plain files (YAML/MD)** for the engagement model and artifacts — human-readable, version-controllable, agent-curated

This chunk builds both, plus the proper structured audit subsystem (replacing
the chunk-02 stub).

---

## Scope

### SQLite layer (`src/praxis/storage/`)

- `db.py` — connection management, per-engagement DB at `<engagement>/.praxis/state/praxis.db`. Use connection pooling via `sqlite3` with `check_same_thread=False` and a per-thread connection registry.
- `migrations/` — directory of versioned SQL migrations (`001_init.sql`, etc.). A migration runner applies missing migrations on first connect.
- `schema.sql` — initial schema (also `migrations/001_init.sql`):

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES sessions(id),
    profile TEXT NOT NULL,
    started_at TEXT NOT NULL,        -- ISO 8601 UTC
    ended_at TEXT,
    summary TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    turn INTEGER NOT NULL,
    role TEXT NOT NULL,              -- user | assistant | tool | system
    content TEXT NOT NULL,
    tool_calls_json TEXT,            -- nullable
    created_at TEXT NOT NULL,
    UNIQUE(session_id, turn)
);

CREATE INDEX idx_messages_session ON messages(session_id);

CREATE VIRTUAL TABLE messages_fts USING fts5(
    content, role, session_id UNINDEXED, message_id UNINDEXED,
    content='messages', content_rowid='rowid'
);

-- triggers to keep FTS in sync (insert, update, delete on messages)

CREATE TABLE workitems (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    priority TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deadline TEXT,
    completed_at TEXT
);

CREATE INDEX idx_workitems_status ON workitems(status, priority);

CREATE TABLE audit (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    profile TEXT NOT NULL,
    engagement TEXT,
    actor TEXT NOT NULL,
    component TEXT NOT NULL,
    event_type TEXT NOT NULL,
    subject_id TEXT,
    correlation_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_audit_time ON audit(timestamp);
CREATE INDEX idx_audit_event ON audit(event_type, timestamp);
```

- `repos/sessions.py`, `repos/messages.py`, `repos/workitems.py`, `repos/audit.py` — typed repository classes with `create / get / list / update / delete` methods. All take Pydantic models, never raw dicts.

### File-based engagement storage (`src/praxis/storage/files.py`)

A thin helper that file-based subsystems use:

```python
def read_yaml_typed(path: Path, model: type[T]) -> T: ...
def write_yaml_typed(path: Path, obj: BaseModel) -> None: ...   # atomic write
def read_markdown_with_frontmatter(path: Path, frontmatter_model: type[T]) -> tuple[T, str]: ...
def write_markdown_with_frontmatter(path: Path, frontmatter: BaseModel, body: str) -> None: ...
```

Atomic writes use `<path>.tmp` + fsync + rename. Read errors raise `StorageError`
with the path and Pydantic validation details.

### Audit subsystem (`src/praxis/audit/`)

Replace the chunk-02 stub:

- `models.py` — `AuditEvent` Pydantic model (see `00-conventions.md` §4)
- `writer.py` — `emit(event_type: str, **payload) -> AuditEvent`
  - Resolves current profile and engagement from a `ContextVar`
  - Writes JSONL to `~/.praxis/audit.jsonl` and (if engagement context is set) the per-engagement audit log
  - Mirrors to SQLite `audit` table (if engagement DB available)
  - Returns the constructed event
- `context.py` — `set_audit_context(profile, engagement) → contextmanager`
- `reader.py` — `tail(n=100)`, `query(event_type=None, since=None, ...)` for the `praxis audit tail` and `praxis audit query` commands

Every later chunk uses `praxis.audit.emit(...)` for state changes.

### CLI additions

- `praxis audit tail [-n 50] [--engagement E]`
- `praxis audit query [--type T] [--since 2026-05-01] [--json]`

---

## Deliverables

- All files under `src/praxis/storage/` and `src/praxis/audit/`
- Migration runner that applies all migrations in order on connect
- Repository classes for sessions, messages, workitems, audit
- File helpers (yaml/markdown frontmatter)
- CLI: `praxis audit tail`, `praxis audit query`
- Update `praxis init` (chunk 02) to create `state/praxis.db` with initial migration
- Update `tests/conftest.py`: add `db_engagement` fixture (creates engagement + DB)
- Unit tests per repository
- Unit tests for file helpers (round-trip, atomic write, validation errors)
- Unit tests for audit emission and context
- `tests/integration/test_chunk_03.py` — end-to-end: init engagement → emit events → tail → query
- `docs/reference/storage-schema.md`
- Update `chunks/STATUS.md`

---

## Acceptance test

```python
def test_storage_end_to_end(tmp_engagement):
    # tmp_engagement is a fixture that creates a fresh engagement dir
    db_path = tmp_engagement / ".praxis" / "state" / "praxis.db"
    assert db_path.exists()

    with set_audit_context(profile="default", engagement=tmp_engagement):
        ev1 = emit("test.event_one", subject_id="s1", foo="bar")
        ev2 = emit("test.event_two", subject_id="s2", foo="baz")

    # JSONL has both events
    audit_file = tmp_engagement / ".praxis" / "state" / "audit.jsonl"
    lines = audit_file.read_text().splitlines()
    assert len(lines) == 2

    # SQLite has both events
    repo = AuditRepo(db_path)
    rows = repo.list(limit=10)
    assert len(rows) == 2
    assert {r.event_type for r in rows} == {"test.event_one", "test.event_two"}

    # FTS works on messages
    msgs_repo = MessagesRepo(db_path)
    sess_repo = SessionsRepo(db_path)
    sess = sess_repo.create(Session(...))
    msgs_repo.append(sess.id, Message(role="user", content="hello world"))
    hits = msgs_repo.fts_search("hello")
    assert len(hits) == 1

    # Round-trip YAML
    glossary_path = tmp_engagement / ".praxis" / "engagement" / "glossary.yaml"
    write_yaml_typed(glossary_path, Glossary(terms=[Term(term="foo", definition="bar")]))
    loaded = read_yaml_typed(glossary_path, Glossary)
    assert loaded.terms[0].term == "foo"
```

Plus `pytest && ruff check && mypy src/praxis` all pass.

---

## Explicit non-goals

- No actual engagement model schemas (chunk 7 — only the file helpers exist here)
- No conversation logic (chunk 8)
- No real workitem business logic (chunk 11)
- No remote storage backend — local SQLite + files only

---

## Notes

- Use `sqlite3` from stdlib, not an ORM. The schema is small enough that raw
  SQL + Pydantic at the boundary is cleaner than SQLAlchemy.
- Connections must enable `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL`.
- Pydantic `model_dump_json()` is the canonical serializer for `payload_json` columns.
- The audit JSONL files are append-only; never rewrite them.
- FTS5 triggers must keep `messages_fts` in sync with `messages` on insert/update/delete.

---

## Definition of done

- All deliverables present
- Acceptance test passes
- `pytest`, `ruff`, `mypy` green
- `chunks/STATUS.md` updated

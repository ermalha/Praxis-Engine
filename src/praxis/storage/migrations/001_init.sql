-- Praxis initial schema: sessions, messages (with FTS5), workitems, audit

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES sessions(id),
    profile TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    summary TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    turn INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(session_id, turn)
);

CREATE INDEX idx_messages_session ON messages(session_id);

CREATE VIRTUAL TABLE messages_fts USING fts5(
    content, role, session_id UNINDEXED, message_id UNINDEXED,
    content='messages', content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content, role, session_id, message_id)
    VALUES (new.rowid, new.content, new.role, new.session_id, new.id);
END;

CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content, role, session_id, message_id)
    VALUES ('delete', old.rowid, old.content, old.role, old.session_id, old.id);
END;

CREATE TRIGGER messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content, role, session_id, message_id)
    VALUES ('delete', old.rowid, old.content, old.role, old.session_id, old.id);
    INSERT INTO messages_fts(rowid, content, role, session_id, message_id)
    VALUES (new.rowid, new.content, new.role, new.session_id, new.id);
END;

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

-- Migration tracking (IF NOT EXISTS because bootstrap creates this first)
CREATE TABLE IF NOT EXISTS _migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

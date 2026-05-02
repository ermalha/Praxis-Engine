"""SQLite connection management and migration runner.

Each engagement has its own database at ``<engagement>/.praxis/state/praxis.db``.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

import structlog

from praxis.errors import StorageError

logger = structlog.get_logger(component="storage")

_MIGRATIONS_PACKAGE = "praxis.storage.migrations"

# Thread-local connection registry
_local = threading.local()


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Get or create a thread-local SQLite connection for *db_path*.

    Enables WAL mode, foreign keys, and returns rows as ``sqlite3.Row``.

    Args:
        db_path: Path to the SQLite database file.
    """
    key = str(db_path.resolve())
    registry: dict[str, sqlite3.Connection] = getattr(_local, "connections", {})
    if key in registry:
        return registry[key]

    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
    except sqlite3.Error as exc:
        raise StorageError(f"Failed to open database: {exc}", path=str(db_path)) from exc

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    _local.connections = registry
    registry[key] = conn
    return conn


def close_connection(db_path: Path) -> None:
    """Close and remove the thread-local connection for *db_path*."""
    key = str(db_path.resolve())
    registry: dict[str, sqlite3.Connection] = getattr(_local, "connections", {})
    conn = registry.pop(key, None)
    if conn is not None:
        conn.close()


def run_migrations(db_path: Path) -> int:
    """Apply any pending SQL migrations to the database.

    Migrations are read from ``praxis/storage/migrations/NNN_*.sql`` and applied
    in version order. Already-applied versions are skipped.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        The number of migrations applied.
    """
    conn = get_connection(db_path)

    # Ensure _migrations table exists (it's in 001 but we need it for bootstrapping)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _migrations "
        "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )

    applied: set[int] = {
        row[0] for row in conn.execute("SELECT version FROM _migrations").fetchall()
    }

    migration_files = _discover_migrations()
    count = 0

    for version, name, sql in migration_files:
        if version in applied:
            continue
        logger.info("storage.migration.applying", version=version, name=name)
        try:
            conn.executescript(sql)
            conn.execute(
                "INSERT OR IGNORE INTO _migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, datetime.now(UTC).isoformat()),
            )
            conn.commit()
            count += 1
        except sqlite3.Error as exc:
            raise StorageError(
                f"Migration {version} ({name}) failed: {exc}",
                version=version,
                name=name,
            ) from exc

    return count


def init_db(db_path: Path) -> sqlite3.Connection:
    """Open a database and apply all pending migrations.

    This is the standard way to get a ready-to-use database connection.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        The connection with all migrations applied.
    """
    conn = get_connection(db_path)
    run_migrations(db_path)
    return conn


def _discover_migrations() -> list[tuple[int, str, str]]:
    """Read migration files from the package, sorted by version number."""
    results: list[tuple[int, str, str]] = []
    migration_dir = resources.files(_MIGRATIONS_PACKAGE)

    for item in sorted(migration_dir.iterdir(), key=lambda t: str(t)):
        name = item.name if hasattr(item, "name") else str(item)
        if not name.endswith(".sql"):
            continue
        # Extract version from filename like "001_init.sql"
        try:
            version = int(name.split("_")[0])
        except (ValueError, IndexError):
            continue
        sql = item.read_text(encoding="utf-8")
        results.append((version, name, sql))

    return sorted(results, key=lambda t: t[0])

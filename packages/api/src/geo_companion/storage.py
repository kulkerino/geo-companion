"""SQLite schema foundation; content activation and learner flows arrive in later tasks."""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATION_ID = "0001_contract_foundation"
MIGRATION_PATH = Path(__file__).resolve().parents[2] / "migrations" / f"{MIGRATION_ID}.sql"


def initialize_database(path: Path) -> Path:
    """Create a local SQLite database and apply the first idempotent migration."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (migration_id TEXT PRIMARY KEY NOT NULL)"
        )
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE migration_id = ?", (MIGRATION_ID,)
        ).fetchone()
        if applied is None:
            connection.executescript(MIGRATION_PATH.read_text())
            connection.execute(
                "INSERT INTO schema_migrations (migration_id) VALUES (?)", (MIGRATION_ID,)
            )
    return path

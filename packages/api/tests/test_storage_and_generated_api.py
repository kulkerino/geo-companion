from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path


def test_sqlite_foundation_applies_the_initial_contract_migration(tmp_path: Path) -> None:
    from geo_companion.storage import initialize_database

    database_path = initialize_database(tmp_path / "runtime.sqlite3")

    with sqlite3.connect(database_path) as connection:
        migration = connection.execute(
            "SELECT migration_id FROM schema_migrations ORDER BY migration_id"
        ).fetchall()
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()

    assert migration == [("0001_contract_foundation",)]
    assert {name for (name,) in tables} >= {
        "content_pack_versions",
        "practice_attempts",
        "schema_migrations",
        "study_progress",
    }


def test_committed_openapi_snapshot_and_types_are_current() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [sys.executable, "packages/api/scripts/generate_api_contract.py", "--check"],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_types_preserve_nullable_contract_fields() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    generated_types_path = repository_root / "apps" / "web" / "src" / "api" / "generated.ts"
    generated_types = generated_types_path.read_text()

    assert "note?: string | null;" in generated_types
    assert "coordinate?: Coordinate | null;" in generated_types

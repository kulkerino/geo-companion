from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


def test_sqlite_foundation_applies_the_initial_contract_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import geo_companion.storage as storage

    application_data = tmp_path / "application-data"
    monkeypatch.setattr(storage, "application_data_dir", lambda: application_data)
    database_path = storage.initialize_database(application_data / "runtime.sqlite3")

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


def test_sqlite_foundation_rejects_paths_outside_application_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import geo_companion.storage as storage

    application_data = tmp_path / "application-data"
    monkeypatch.setattr(storage, "application_data_dir", lambda: application_data)

    allowed_path = application_data / "state" / "runtime.sqlite3"
    assert storage.initialize_database(allowed_path) == allowed_path

    with pytest.raises(ValueError, match="application-data"):
        storage.initialize_database(tmp_path / "vault" / "runtime.sqlite3")

    escape_target = tmp_path / "vault"
    escape_target.mkdir()
    escape_link = application_data / "escape"
    try:
        escape_link.symlink_to(escape_target, target_is_directory=True)
    except OSError as error:  # Windows without Developer Mode or admin rights
        pytest.skip(f"cannot create a symlink here: {error}")
    with pytest.raises(ValueError, match="application-data"):
        storage.initialize_database(escape_link / "runtime.sqlite3")


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


def test_generated_client_requires_request_bodies_and_concrete_path_parameters() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    generated_types_path = repository_root / "apps" / "web" / "src" / "api" / "generated.ts"
    generated_types = generated_types_path.read_text()

    assert "submit_feedback_api_v1_feedback_post(body: Feedback)" in generated_types
    assert (
        "get_practice_round_api_v1_practice_rounds__round_id__get(round_id: string)"
        in generated_types
    )
    assert (
        "submit_practice_answer_api_v1_practice_rounds__round_id__answers_post(" in generated_types
    )
    assert "round_id: string, body: PracticeAnswerSubmission" in generated_types

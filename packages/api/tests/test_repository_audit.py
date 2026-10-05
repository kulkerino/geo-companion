from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
AUDIT_SCRIPT = REPOSITORY_ROOT / "tools" / "audit_repository.py"


def run_audit(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), "--root", str(root)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_repository_audit_accepts_a_clean_working_tree(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "project.md").write_text("Safe documentation.\n")

    result = run_audit(tmp_path)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_repository_audit_ignores_python_bytecode_cache(tmp_path: Path) -> None:
    cache_file = tmp_path / "packages" / "__pycache__" / "cached.pyc"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text('{"api_' + 'key": "do-not-commit"}\n')

    result = run_audit(tmp_path)

    assert result.returncode == 0


def test_repository_audit_accepts_secret_scan_documentation(tmp_path: Path) -> None:
    (tmp_path / "audit-notes.md").write_text(
        "The audit reports possible secret: packages/runtime/cache.sqlite.\n"
    )

    result = run_audit(tmp_path)

    assert result.returncode == 0


def test_repository_audit_rejects_force_added_ignored_runtime_file(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("data/local/\n")
    runtime_file = tmp_path / "data" / "local" / "private-pack" / "image.jpg"
    runtime_file.parent.mkdir(parents=True)
    runtime_file.write_text("not a forbidden suffix\n")
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "add", "--force", runtime_file.relative_to(tmp_path)], cwd=tmp_path, check=True
    )

    result = run_audit(tmp_path)

    assert result.returncode == 1
    assert "tracked ignored file: data/local/private-pack/image.jpg" in result.stdout


def test_repository_audit_rejects_private_key_material(tmp_path: Path) -> None:
    private_key_file = tmp_path / "keys" / "identity.pem"
    private_key_file.parent.mkdir()
    private_key_file.write_text("-----BEGIN " + "PRIVATE KEY-----\nprivate material\n")

    result = run_audit(tmp_path)

    assert result.returncode == 1
    assert "keys/identity.pem" in result.stdout


def test_repository_audit_scans_secret_beyond_one_megabyte(tmp_path: Path) -> None:
    large_file = tmp_path / "logs" / "large.txt"
    large_file.parent.mkdir()
    large_file.write_text("x" * 1_000_001 + "\nAPI_" + "KEY=do-not-commit\n")

    result = run_audit(tmp_path)

    assert result.returncode == 1
    assert "logs/large.txt" in result.stdout


@pytest.mark.parametrize(
    ("relative_path", "contents"),
    [
        ("runtime/cache.sqlite", "SQLite format 3\x00"),
        ("models/MODEL.ONNX", "model bytes"),
        ("secrets/config.json", '{"api_' + 'key": "do-not-commit"}\n'),
        (".env", "API_" + "KEY=do-not-commit\n"),
    ],
)
def test_repository_audit_rejects_forbidden_runtime_or_secret_fixture(
    tmp_path: Path, relative_path: str, contents: str
) -> None:
    forbidden_file = tmp_path / relative_path
    forbidden_file.parent.mkdir(parents=True, exist_ok=True)
    forbidden_file.write_text(contents)

    result = run_audit(tmp_path)

    assert result.returncode == 1
    assert relative_path in result.stdout

"""Fail when a working tree contains forbidden runtime artifacts or secrets."""

from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "dist",
        "node_modules",
    }
)
FORBIDDEN_SUFFIXES = frozenset(
    {".db", ".onnx", ".pth", ".pt", ".safetensors", ".sqlite", ".sqlite3"}
)
SECRET_PATTERN = re.compile(
    r"(?im)(?:^|[,{])\s*[\"']?(?:api[_-]?key|secret|token|password)[\"']?\s*[:=]\s*"
    r"(?:[\"'][^\"'\r\n]{8,}[\"']|[^\s#\"']{8,})"
)
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
CONTENT_PATTERNS = (SECRET_PATTERN, PRIVATE_KEY_PATTERN)
SCAN_CHUNK_SIZE = 64 * 1024
SCAN_OVERLAP = 1024


def find_audit_violations(root: Path) -> list[str]:
    """Return deterministic descriptions of forbidden files beneath ``root``."""
    violations = [f"tracked ignored file: {path}" for path in _tracked_ignored_files(root)]
    for path in _audited_files(root):
        relative_path = path.relative_to(root).as_posix()
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            violations.append(f"forbidden artifact: {relative_path}")
        elif _contains_secret(path):
            violations.append(f"possible secret: {relative_path}")
    return violations


def _tracked_ignored_files(root: Path) -> list[str]:
    tracked_files = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if tracked_files.returncode != 0 or not tracked_files.stdout:
        return []

    ignored_files = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "--no-index", "-z", "--stdin"],
        check=False,
        capture_output=True,
        input=tracked_files.stdout,
    )
    if ignored_files.returncode not in {0, 1}:
        return []
    return sorted(path for path in ignored_files.stdout.decode().split("\0") if path)


def _audited_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        relative_path = path.relative_to(root)
        if any(part in EXCLUDED_DIRECTORIES for part in relative_path.parts):
            continue
        if path.is_file() and not path.is_symlink():
            yield path


def _contains_secret(path: Path) -> bool:
    with path.open(encoding="utf-8", errors="ignore") as file_handle:
        tail = ""
        while chunk := file_handle.read(SCAN_CHUNK_SIZE):
            text = tail + chunk
            if any(pattern.search(text) is not None for pattern in CONTENT_PATTERNS):
                return True
            tail = text[-SCAN_OVERLAP:]
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="working tree to audit")
    args = parser.parse_args()
    root = args.root.resolve()

    violations = find_audit_violations(root)
    for violation in violations:
        print(violation)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())

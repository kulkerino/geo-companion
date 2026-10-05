"""Fail when a working tree contains forbidden runtime artifacts or secrets."""

from __future__ import annotations

import argparse
import re
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


def find_audit_violations(root: Path) -> list[str]:
    """Return deterministic descriptions of forbidden files beneath ``root``."""
    violations: list[str] = []
    for path in _audited_files(root):
        relative_path = path.relative_to(root).as_posix()
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            violations.append(f"forbidden artifact: {relative_path}")
        elif _contains_secret(path):
            violations.append(f"possible secret: {relative_path}")
    return violations


def _audited_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        relative_path = path.relative_to(root)
        if any(part in EXCLUDED_DIRECTORIES for part in relative_path.parts):
            continue
        if path.is_file() and not path.is_symlink():
            yield path


def _contains_secret(path: Path) -> bool:
    if path.stat().st_size > 1_000_000:
        return False
    return SECRET_PATTERN.search(path.read_text(encoding="utf-8", errors="ignore")) is not None


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

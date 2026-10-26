"""Runtime paths that must never resolve inside the repository."""

import os
from pathlib import Path

from platformdirs import user_data_path


def application_data_dir() -> Path:
    """Return a per-user data path that is outside any Git worktree."""
    configured = os.environ.get("GEO_COMPANION_DATA_DIR")
    candidate = (
        Path(configured)
        if configured
        else user_data_path(appname="geo-companion", appauthor=False, ensure_exists=False)
    )
    if not is_inside_repository(candidate):
        return candidate

    fallback = Path.home() / ".local" / "share" / "geo-companion"
    if is_inside_repository(fallback):
        msg = "Unable to resolve an application-data directory outside a Git worktree."
        raise RuntimeError(msg)
    return fallback


def is_inside_repository(path: Path) -> bool:
    """True when ``path`` resolves inside this repository; runtime data must never go there."""
    repository_root = Path(__file__).resolve().parents[4]
    return path.resolve().is_relative_to(repository_root)

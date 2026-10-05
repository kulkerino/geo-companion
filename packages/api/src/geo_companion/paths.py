"""Runtime paths that must never resolve inside the repository."""

from pathlib import Path

from platformdirs import user_data_path


def application_data_dir() -> Path:
    """Return a per-user data path that is outside any Git worktree."""
    candidate = user_data_path(appname="geo-companion", appauthor=False, ensure_exists=False)
    if not _is_inside_git_worktree(candidate):
        return candidate

    fallback = Path.home() / ".local" / "share" / "geo-companion"
    if _is_inside_git_worktree(fallback):
        msg = "Unable to resolve an application-data directory outside a Git worktree."
        raise RuntimeError(msg)
    return fallback


def _is_inside_git_worktree(path: Path) -> bool:
    resolved_path = path.resolve()
    return any((ancestor / ".git").exists() for ancestor in (resolved_path, *resolved_path.parents))

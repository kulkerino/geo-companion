"""Runtime paths that must never resolve inside the repository."""

from pathlib import Path

from platformdirs import user_data_path


def application_data_dir() -> Path:
    """Return the per-user application-data directory without creating it."""
    return user_data_path(appname="geo-companion", appauthor=False, ensure_exists=False)

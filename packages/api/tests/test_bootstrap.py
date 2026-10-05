from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("unsafe_relative_path", [".", "runtime-data"])
def test_application_data_path_ignores_xdg_override_inside_repository(
    monkeypatch: pytest.MonkeyPatch, unsafe_relative_path: str
) -> None:
    repository_root = Path(__file__).resolve().parents[3]
    monkeypatch.setenv("XDG_DATA_HOME", str(repository_root / unsafe_relative_path))

    from geo_companion.paths import application_data_dir

    app_data_path = application_data_dir()

    assert not app_data_path.resolve().is_relative_to(repository_root.resolve())


def test_application_data_path_is_outside_repository() -> None:
    module_spec = importlib.util.find_spec("geo_companion.paths")

    assert module_spec is not None, "application-data path module must exist"

    from geo_companion.paths import application_data_dir

    app_data_path = application_data_dir()
    repository_root = Path(__file__).resolve().parents[3]
    assert app_data_path.is_absolute()
    assert not app_data_path.is_relative_to(repository_root)


def test_health_endpoint_reports_local_service() -> None:
    module_spec = importlib.util.find_spec("geo_companion.main")

    assert module_spec is not None, "FastAPI application module must exist"

    from fastapi.testclient import TestClient
    from geo_companion.main import app

    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "geo-companion"}

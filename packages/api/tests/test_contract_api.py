from __future__ import annotations

from fastapi.testclient import TestClient


def test_contract_routes_are_versioned_and_have_safe_empty_or_not_found_behavior() -> None:
    from geo_companion.main import app

    client = TestClient(app)

    packs = client.get("/api/v1/packs")
    lessons = client.get("/api/v1/lessons")
    next_round = client.get("/api/v1/practice/rounds/next")
    study = client.get("/api/v1/study/progress/missing-lesson")

    assert packs.status_code == 200
    assert packs.json() == {"packs": []}
    assert lessons.status_code == 200
    assert lessons.json() == {"lessons": []}
    assert next_round.status_code == 404
    assert next_round.json()["detail"] == "No active cleared practice round is available."
    assert study.status_code == 404
    assert study.json()["detail"] == "No study progress exists for lesson 'missing-lesson'."


def test_openapi_advertises_versioned_learning_contracts() -> None:
    from geo_companion.main import app

    paths = app.openapi()["paths"]

    assert "/api/v1/packs" in paths
    assert "/api/v1/lessons" in paths
    assert "/api/v1/practice/rounds/next" in paths
    assert "/api/v1/study/progress/{lesson_id}" in paths

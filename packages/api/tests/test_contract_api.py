from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest


def request(app: object, method: str, path: str, json: object | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


@pytest.fixture(autouse=True)
def isolated_local_learner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import geo_companion.main as main
    from geo_companion.learning import LearningService

    monkeypatch.setattr(main, "learning_service", LearningService(tmp_path / "runtime.sqlite3"))


def test_contract_routes_are_versioned_and_have_safe_empty_or_not_found_behavior() -> None:
    from geo_companion.main import app

    packs = request(app, "GET", "/api/v1/packs")
    lessons = request(app, "GET", "/api/v1/lessons")
    next_round = request(app, "GET", "/api/v1/practice/rounds/next")
    study = request(app, "GET", "/api/v1/study/progress/missing-lesson")

    assert packs.status_code == 200
    assert packs.json()["packs"][0]["pack_id"] == "starter-original-diagrams"
    assert lessons.status_code == 200
    assert len(lessons.json()["lessons"]) == 3
    assert next_round.status_code == 200
    assert "answer" not in next_round.json()
    assert study.status_code == 404
    assert study.json()["detail"] == "No study progress exists for lesson 'missing-lesson'."


def test_openapi_advertises_versioned_learning_contracts() -> None:
    from geo_companion.main import app

    paths = app.openapi()["paths"]

    assert "/api/v1/packs" in paths
    assert "/api/v1/lessons" in paths
    assert "/api/v1/practice/rounds/next" in paths
    assert "/api/v1/study/progress/{lesson_id}" in paths


def test_feedback_rejects_an_unknown_revealed_attempt() -> None:
    from geo_companion.main import app

    response = request(
        app,
        "POST",
        "/api/v1/feedback",
        {
            "attempt_id": "missing-attempt",
            "round_id": "starter-diagram-01",
            "rating": 3,
            "note": "Useful explanation.",
        },
    )

    assert response.status_code == 404

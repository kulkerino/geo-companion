from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import httpx
import pytest

FIRST_ROUND = "starter-place-01"


def api(app: object, method: str, path: str, json: object | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_dummy_provider_is_deterministic_labelled_and_sometimes_abstains() -> None:
    from geo_companion.contracts import PracticeRoundPublic
    from geo_companion.models import DummyProvider
    from geo_companion.starter_pack import PRACTICE_ROUNDS

    provider = DummyProvider()
    predictions = [provider.predict(PracticeRoundPublic.from_round(r)) for r in PRACTICE_ROUNDS]

    assert predictions == [
        DummyProvider().predict(PracticeRoundPublic.from_round(r)) for r in PRACTICE_ROUNDS
    ]
    assert provider.info.is_placeholder is True
    assert provider.info.runtime == "dummy"
    assert provider.info.required_for_learning is False
    assert "not image analysis" in provider.info.description
    assert any(not candidates for candidates in predictions)
    assert sum(1 for candidates in predictions if candidates) >= 5
    for candidates in predictions:
        assert len(candidates) in {0, 3}


def test_dummy_provider_never_sees_the_authored_answer() -> None:
    from geo_companion.contracts import PracticeRound, PracticeRoundPublic, SourceTruthAnswer
    from geo_companion.models import DummyProvider
    from geo_companion.starter_pack import PRACTICE_ROUNDS

    original = PRACTICE_ROUNDS[0]
    relabelled = PracticeRound(
        **{
            **original.model_dump(exclude={"answer"}),
            "answer": SourceTruthAnswer(
                **{**original.answer.model_dump(), "country_code": "FR"}
            ),
        }
    )
    provider = DummyProvider()

    # The provider's input type has no answer field, so changing the key cannot change output.
    assert "answer" not in PracticeRoundPublic.model_fields
    assert provider.predict(PracticeRoundPublic.from_round(relabelled)) == provider.predict(
        PracticeRoundPublic.from_round(original)
    )


def test_provider_selection_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    from geo_companion.models import DummyProvider, provider_from_environment

    monkeypatch.delenv("GEO_COMPANION_MODEL", raising=False)
    assert isinstance(provider_from_environment(), DummyProvider)
    monkeypatch.setenv("GEO_COMPANION_MODEL", "none")
    assert provider_from_environment() is None
    monkeypatch.setenv("GEO_COMPANION_MODEL", "gpt")
    with pytest.raises(ValueError, match="dummy"):
        provider_from_environment()


@pytest.mark.parametrize(
    "fields",
    [
        {"candidates": (), "abstained": False},
        {"candidates": ({"country_code": "FR", "confidence": 0.5},), "abstained": True},
        {
            "candidates": (
                {"country_code": "FR", "confidence": 0.2},
                {"country_code": "DE", "confidence": 0.5},
            ),
            "abstained": False,
        },
        {
            "candidates": (
                {"country_code": "FR", "confidence": 0.5},
                {"country_code": "FR", "confidence": 0.2},
            ),
            "abstained": False,
        },
        {
            "candidates": (
                {"country_code": "FR", "confidence": 0.7},
                {"country_code": "DE", "confidence": 0.6},
            ),
            "abstained": False,
        },
    ],
)
def test_prediction_contract_rejects_inconsistent_candidates(fields: dict[str, object]) -> None:
    from geo_companion.contracts import ModelPredictionResult
    from geo_companion.models import DummyProvider
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ModelPredictionResult.model_validate(
            {
                "attempt_id": "a",
                "round_id": FIRST_ROUND,
                "model": DummyProvider.info.model_dump(),
                **fields,
            }
        )


def test_prediction_requires_an_answered_attempt_and_is_stored_once(tmp_path: Path) -> None:
    from geo_companion.contracts import PracticeAnswerSubmission
    from geo_companion.learning import LearningService
    from geo_companion.models import DummyProvider

    database = tmp_path / "runtime.sqlite3"
    service = LearningService(database, provider=DummyProvider())
    with pytest.raises(KeyError):
        service.model_prediction("never-answered")

    attempt = service.submit_practice(FIRST_ROUND, PracticeAnswerSubmission(skipped=True))
    first = service.model_prediction(attempt.attempt_id)
    reopened = LearningService(database, provider=DummyProvider())

    assert reopened.model_prediction(attempt.attempt_id) == first
    assert first.origin == "model_prediction"
    assert first.round_id == FIRST_ROUND
    with sqlite3.connect(database) as connection:
        rows = connection.execute("SELECT COUNT(*) FROM learner_model_predictions").fetchone()
    assert rows == (1,)
    # A model opinion never changes the authored answer or the learner's history.
    assert reopened.submit_practice(
        FIRST_ROUND, PracticeAnswerSubmission(country_code="SK")
    ).answer == attempt.answer
    assert [item["answer_origin"] for item in reopened.attempt_history(FIRST_ROUND)] == [
        "authored",
        "authored",
    ]


def test_without_a_model_learning_still_works_and_predictions_are_unavailable(
    tmp_path: Path,
) -> None:
    from geo_companion.contracts import PracticeAnswerSubmission
    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3", provider=None)
    attempt = service.submit_practice(FIRST_ROUND, PracticeAnswerSubmission(country_code="SK"))

    assert attempt.is_correct is True
    assert service.model_status().active is None
    with pytest.raises(LookupError, match="No local model"):
        service.model_prediction(attempt.attempt_id)


def test_model_api_is_post_answer_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import geo_companion.main as main
    from geo_companion.learning import LearningService
    from geo_companion.models import DummyProvider

    monkeypatch.setattr(
        main,
        "learning_service",
        LearningService(tmp_path / "runtime.sqlite3", provider=DummyProvider()),
    )
    paths = main.app.openapi()["paths"]
    model_paths = [path for path in paths if "model" in path]
    assert model_paths == [
        "/api/v1/models",
        "/api/v1/practice/attempts/{attempt_id}/model-prediction",
    ]

    status = api(main.app, "GET", "/api/v1/models")
    unknown = api(main.app, "GET", "/api/v1/practice/attempts/unknown/model-prediction")
    answers = f"/api/v1/practice/rounds/{FIRST_ROUND}/answers"
    reveal = api(main.app, "POST", answers, {"skipped": True})
    attempt_id = reveal.json()["attempt_id"]
    prediction = api(main.app, "GET", f"/api/v1/practice/attempts/{attempt_id}/model-prediction")

    assert status.json()["active"]["model_id"] == "dummy-placeholder"
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "The attempt was not found for this learner."
    assert prediction.status_code == 200
    assert prediction.json()["model"]["is_placeholder"] is True
    assert prediction.json()["origin"] == "model_prediction"


def test_model_api_reports_no_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import geo_companion.main as main
    from geo_companion.learning import LearningService

    monkeypatch.setattr(
        main, "learning_service", LearningService(tmp_path / "runtime.sqlite3", provider=None)
    )
    answers = f"/api/v1/practice/rounds/{FIRST_ROUND}/answers"
    reveal = api(main.app, "POST", answers, {"skipped": True})
    attempt_id = reveal.json()["attempt_id"]
    prediction = api(main.app, "GET", f"/api/v1/practice/attempts/{attempt_id}/model-prediction")

    assert api(main.app, "GET", "/api/v1/models").json() == {"active": None}
    assert prediction.status_code == 404
    assert prediction.json()["detail"] == "No local model is enabled."

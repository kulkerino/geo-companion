# ruff: noqa: E501
from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest


def test_sm2_first_second_and_lapsed_reviews_are_deterministic(tmp_path: Path) -> None:
    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3")
    reviewed_at = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)

    first = service.grade_lesson("road-sign-shapes", 5, reviewed_at)
    second = service.grade_lesson("road-sign-shapes", 4, reviewed_at)
    lapsed = service.grade_lesson("road-sign-shapes", 2, reviewed_at)

    assert (first.repetitions, first.interval_days, first.ease_factor) == (1, 1, 2.6)
    assert (second.repetitions, second.interval_days, second.ease_factor) == (2, 6, 2.6)
    assert (lapsed.repetitions, lapsed.interval_days, lapsed.ease_factor) == (0, 1, 2.28)
    assert lapsed.next_review_on == date(2026, 10, 8)


def test_lesson_quiz_hides_key_until_answer_then_returns_cited_explanation(tmp_path: Path) -> None:
    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3")
    lesson = service.lesson_public("road-sign-shapes")

    assert "correct_choice" not in lesson.model_dump_json()
    result = service.answer_quiz("road-sign-shapes", "sign-shapes-q1", "A warning")

    assert result.is_correct is True
    assert "triangle" in result.explanation.lower()
    assert result.citations[0].rights_status == "cleared"


def test_practice_public_payload_has_no_answer_or_coordinates_and_reveals_after_submission(
    tmp_path: Path,
) -> None:
    from geo_companion.contracts import PracticeAnswerSubmission
    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3")
    public_round = service.next_round()

    assert "answer" not in public_round.model_dump_json()
    assert "latitude" not in public_round.model_dump_json()
    result = service.submit_practice(
        public_round.round_id,
        PracticeAnswerSubmission(skipped=True, uncertain=True),
    )

    assert result.submission.skipped is True
    assert result.answer.answer_origin == "source_truth"
    assert result.answer.coordinate.latitude == pytest.approx(48.15)


def test_attempt_feedback_report_and_retry_are_persisted_without_promoting_a_dispute(
    tmp_path: Path,
) -> None:
    from geo_companion.contracts import Feedback, PracticeAnswerSubmission
    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3")
    round_ = service.next_round()
    attempt = service.submit_practice(
        round_.round_id,
        PracticeAnswerSubmission(skipped=True, uncertain=True),
    )
    service.record_feedback(
        Feedback(
            round_id=round_.round_id,
            rating=1,
            note="The fixture label is unclear.",
            reported_issue=True,
        ),
        attempt.attempt_id,
    )
    retry = service.submit_practice(
        round_.round_id,
        PracticeAnswerSubmission(
            country_code="SK", coordinate={"latitude": 48.15, "longitude": 17.11}
        ),
    )

    history = service.attempt_history(round_.round_id)
    assert len(history) == 2
    assert history[0]["reported_issue"] is True
    assert history[0]["answer_origin"] == "source_truth"
    assert retry.is_correct is True
    assert "user_correction" not in str(history)


def test_api_starter_slice_is_offline_and_keeps_answers_out_of_preanswer_responses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import geo_companion.main as main
    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3")
    monkeypatch.setattr(main, "learning_service", service)

    async def api_call(method: str, path: str, json: object | None = None) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json)

    lessons = asyncio.run(api_call("GET", "/api/v1/lessons"))
    lesson = asyncio.run(api_call("GET", "/api/v1/lessons/road-sign-shapes"))
    round_response = asyncio.run(api_call("GET", "/api/v1/practice/rounds/next"))
    payload = round_response.json()

    assert lessons.status_code == 200 and len(lessons.json()["lessons"]) == 3
    assert lesson.status_code == 200 and "correct_choice" not in lesson.text
    assert round_response.status_code == 200
    assert "answer" not in payload and "coordinate" not in payload

    reveal = asyncio.run(
        api_call(
            "POST",
            f"/api/v1/practice/rounds/{payload['round_id']}/answers",
            {"skipped": True, "uncertain": True},
        )
    )
    assert reveal.status_code == 200
    assert reveal.json()["answer"]["answer_origin"] == "source_truth"

from __future__ import annotations

import asyncio
import re
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

FIRST_ROUND = "starter-place-01"
SECOND_ROUND = "starter-place-02"


def answer_tokens() -> set[str]:
    from geo_companion.starter_pack import STARTER_DIAGRAMS

    return {
        token
        for evidence in STARTER_DIAGRAMS
        for token in (evidence.country_code.casefold(), evidence.country_name.casefold())
    }


def assert_no_answer(payload: str) -> None:
    tokens = set(re.findall(r"[^\W\d_]+", payload.casefold()))
    assert not tokens & answer_tokens(), payload
    assert "authored teaching target" not in payload.casefold()
    assert "country_code" not in payload and "latitude" not in payload


def test_sm2_first_second_and_lapsed_reviews_are_deterministic(tmp_path: Path) -> None:
    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3")
    reviewed_at = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)

    first = service.schedule_review(FIRST_ROUND, 5, reviewed_at)
    second = service.schedule_review(FIRST_ROUND, 4, reviewed_at)
    lapsed = service.schedule_review(FIRST_ROUND, 2, reviewed_at)

    assert (first.repetitions, first.interval_days, first.ease_factor) == (1, 1, 2.6)
    assert (second.repetitions, second.interval_days, second.ease_factor) == (2, 6, 2.6)
    assert (lapsed.repetitions, lapsed.interval_days, lapsed.ease_factor) == (0, 1, 2.28)
    assert lapsed.next_review_on == date(2026, 10, 8)


def test_sm2_uses_the_prior_ease_for_the_third_success_interval(tmp_path: Path) -> None:
    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3")
    reviewed_at = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)

    service.schedule_review(FIRST_ROUND, 5, reviewed_at)
    service.schedule_review(FIRST_ROUND, 5, reviewed_at)
    third = service.schedule_review(FIRST_ROUND, 3, reviewed_at)

    assert (third.repetitions, third.interval_days, third.ease_factor) == (3, 16, 2.56)


def test_schedule_rejects_unknown_rounds_and_invalid_quality(tmp_path: Path) -> None:
    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3")
    reviewed_at = datetime(2026, 10, 7, tzinfo=UTC)

    with pytest.raises(KeyError):
        service.schedule_review("road-sign-shapes", 4, reviewed_at)
    with pytest.raises(ValueError):
        service.schedule_review(FIRST_ROUND, 6, reviewed_at)


def test_public_round_and_clue_hide_the_answer_until_submission(tmp_path: Path) -> None:
    from geo_companion.contracts import PracticeAnswerSubmission
    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3")
    public_round = service.next_round()

    assert_no_answer(public_round.model_dump_json())
    assert_no_answer(service.clue(public_round.round_id).model_dump_json())
    result = service.submit_practice(
        public_round.round_id, PracticeAnswerSubmission(skipped=True, uncertain=True)
    )

    assert result.is_correct is False
    assert result.answer.country_code == "SK"
    assert result.answer.coordinate is None
    assert result.answer.answer_origin == "authored"
    assert "Authored teaching target" in result.answer.explanation
    assert result.study_progress is not None
    assert result.study_progress.round_id == public_round.round_id


def test_default_or_malformed_guesses_never_become_correct(tmp_path: Path) -> None:
    from geo_companion.contracts import PracticeAnswerSubmission
    from geo_companion.learning import LearningService
    from pydantic import ValidationError

    service = LearningService(tmp_path / "runtime.sqlite3")
    for invalid in ({}, {"country_code": ""}, {"country_code": "sk"}, {"country_code": "S1"}):
        with pytest.raises(ValidationError):
            PracticeAnswerSubmission.model_validate(invalid)

    wrong = service.submit_practice(FIRST_ROUND, PracticeAnswerSubmission(country_code="CZ"))
    skipped = service.submit_practice(FIRST_ROUND, PracticeAnswerSubmission(skipped=True))

    assert wrong.is_correct is False
    assert skipped.is_correct is False


def test_feedback_marks_only_the_revealed_attempt_without_promoting_a_dispute(
    tmp_path: Path,
) -> None:
    from geo_companion.contracts import Feedback, PracticeAnswerSubmission
    from geo_companion.learning import LearningService
    from geo_companion.starter_pack import PRACTICE_ROUNDS

    service = LearningService(tmp_path / "runtime.sqlite3")
    attempt = service.submit_practice(
        FIRST_ROUND, PracticeAnswerSubmission(skipped=True, uncertain=True)
    )
    service.record_feedback(
        Feedback(
            attempt_id=attempt.attempt_id,
            round_id=FIRST_ROUND,
            rating=1,
            note="The panel wording is unclear.",
            reported_issue=True,
        )
    )
    retry = service.submit_practice(FIRST_ROUND, PracticeAnswerSubmission(country_code="SK"))
    with pytest.raises(KeyError):
        service.record_feedback(
            Feedback(attempt_id=attempt.attempt_id, round_id=SECOND_ROUND, rating=2)
        )

    history = service.attempt_history(FIRST_ROUND)
    assert [item["attempt_id"] for item in history] == [attempt.attempt_id, retry.attempt_id]
    assert [item["reported_issue"] for item in history] == [True, False]
    assert {item["answer_origin"] for item in history} == {"authored"}
    assert retry.is_correct is True
    assert retry.answer == PRACTICE_ROUNDS[0].answer


def test_retry_keeps_the_same_round_and_next_round_advances_without_skipping(
    tmp_path: Path,
) -> None:
    from geo_companion.contracts import PracticeAnswerSubmission
    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3")
    first = service.next_round()
    service.submit_practice(first.round_id, PracticeAnswerSubmission(skipped=True))

    retried = service.round_public(first.round_id)
    service.submit_practice(retried.round_id, PracticeAnswerSubmission(country_code="SK"))
    following = service.next_round()

    assert first.round_id == retried.round_id == FIRST_ROUND
    assert retried.asset_id == first.asset_id
    assert following.round_id == SECOND_ROUND
    assert len(service.attempt_history(FIRST_ROUND)) == 2


def test_next_round_wraps_after_the_last_round(tmp_path: Path) -> None:
    from geo_companion.contracts import PracticeAnswerSubmission
    from geo_companion.learning import LearningService
    from geo_companion.starter_pack import PRACTICE_ROUNDS

    service = LearningService(tmp_path / "runtime.sqlite3")
    service.submit_practice(PRACTICE_ROUNDS[-1].round_id, PracticeAnswerSubmission(skipped=True))

    assert service.next_round().round_id == FIRST_ROUND


def test_uncertain_correct_schedules_less_aggressively_than_confident_correct(
    tmp_path: Path,
) -> None:
    from geo_companion.contracts import PracticeAnswerSubmission
    from geo_companion.learning import LearningService

    confident_service = LearningService(tmp_path / "confident.sqlite3")
    uncertain_service = LearningService(tmp_path / "uncertain.sqlite3")
    confident = [
        confident_service.submit_practice(FIRST_ROUND, PracticeAnswerSubmission(country_code="SK"))
        for _ in range(3)
    ]
    uncertain = [
        uncertain_service.submit_practice(
            FIRST_ROUND, PracticeAnswerSubmission(country_code="SK", uncertain=True)
        )
        for _ in range(3)
    ]

    assert all(result.is_correct for result in (*confident, *uncertain))
    confident_schedule = [result.study_progress for result in confident]
    uncertain_schedule = [result.study_progress for result in uncertain]
    assert [(p.interval_days, p.ease_factor) for p in confident_schedule if p] == [
        (1, 2.5),
        (6, 2.5),
        (15, 2.5),
    ]
    assert [(p.interval_days, p.ease_factor) for p in uncertain_schedule if p] == [
        (1, 2.36),
        (6, 2.22),
        (13, 2.08),
    ]


def test_next_review_orders_by_computed_due_date_not_last_review(tmp_path: Path) -> None:
    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3")
    # Reviewed earlier but due later: 2026-10-01 + 6 days = 2026-10-07.
    service.schedule_review(FIRST_ROUND, 5, datetime(2026, 10, 1, tzinfo=UTC))
    service.schedule_review(FIRST_ROUND, 5, datetime(2026, 10, 1, tzinfo=UTC))
    # Reviewed later but due sooner: 2026-10-03 + 1 day = 2026-10-04.
    service.schedule_review(SECOND_ROUND, 1, datetime(2026, 10, 3, tzinfo=UTC))

    review = service.next_review().progress
    assert review is not None
    assert (review.round_id, review.next_review_on) == (SECOND_ROUND, date(2026, 10, 4))


def test_review_date_uses_utc_for_offset_timestamps(tmp_path: Path) -> None:
    from datetime import timedelta, timezone

    from geo_companion.learning import LearningService

    service = LearningService(tmp_path / "runtime.sqlite3")
    late_evening_west = datetime(2026, 10, 7, 23, 30, tzinfo=timezone(timedelta(hours=-5)))

    progress = service.schedule_review(FIRST_ROUND, 4, late_evening_west)

    assert progress.last_reviewed_on == date(2026, 10, 8)


def test_clean_start_has_no_review_and_state_persists_in_a_new_service(tmp_path: Path) -> None:
    from geo_companion.contracts import PracticeAnswerSubmission
    from geo_companion.learning import LearningService

    database = tmp_path / "runtime.sqlite3"
    service = LearningService(database)
    assert service.next_review().progress is None
    with pytest.raises(KeyError):
        service.progress(FIRST_ROUND)

    result = service.submit_practice(FIRST_ROUND, PracticeAnswerSubmission(country_code="SK"))
    reopened = LearningService(database)

    assert reopened.progress(FIRST_ROUND) == result.study_progress
    assert reopened.next_review().progress == result.study_progress
    assert reopened.next_round().round_id == SECOND_ROUND
    assert reopened.attempt_history(FIRST_ROUND)[0]["attempt_id"] == result.attempt_id


def test_api_practice_slice_is_offline_and_keeps_answers_out_of_preanswer_responses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import geo_companion.main as main
    from geo_companion.learning import LearningService

    monkeypatch.setattr(main, "learning_service", LearningService(tmp_path / "runtime.sqlite3"))

    async def api_call(method: str, path: str, json: object | None = None) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json)

    next_round = asyncio.run(api_call("GET", "/api/v1/practice/rounds/next"))
    round_id = next_round.json()["round_id"]
    same_round = asyncio.run(api_call("GET", f"/api/v1/practice/rounds/{round_id}"))
    clue = asyncio.run(api_call("GET", f"/api/v1/practice/rounds/{round_id}/clue"))
    for response in (next_round, same_round, clue):
        assert response.status_code == 200
        assert_no_answer(response.text)
    assert same_round.json() == next_round.json()

    lowercase = asyncio.run(
        api_call("POST", f"/api/v1/practice/rounds/{round_id}/answers", {"country_code": "sk"})
    )
    missing = asyncio.run(api_call("GET", "/api/v1/practice/rounds/missing"))
    retired_lessons = asyncio.run(api_call("GET", "/api/v1/lessons"))
    assert lowercase.status_code == 422
    assert missing.status_code == 404
    assert retired_lessons.status_code == 404

    reveal = asyncio.run(
        api_call(
            "POST",
            f"/api/v1/practice/rounds/{round_id}/answers",
            {"country_code": "SK", "uncertain": True},
        )
    )
    progress = asyncio.run(api_call("GET", f"/api/v1/study/progress/{round_id}"))
    review = asyncio.run(api_call("GET", "/api/v1/study/review/next"))
    assert reveal.status_code == 200
    assert reveal.json()["is_correct"] is True
    assert reveal.json()["answer"]["answer_origin"] == "authored"
    assert progress.json() == reveal.json()["study_progress"]
    assert review.json()["progress"]["round_id"] == round_id
    assert "next_review_on" in review.json()["progress"]

from __future__ import annotations

import asyncio
import random
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from geo_companion.contracts import (
    AnswerOrigin,
    AssetKind,
    Citation,
    ModelCandidate,
    ModelInfo,
    PracticeAnswerSubmission,
    PracticeRound,
    PracticeRoundPublic,
    RaceStartRequest,
    SourceTruthAnswer,
)
from geo_companion.learning import LearningService
from geo_companion.models import DummyProvider
from geo_companion.race import RaceOrderError, RaceService, RaceUnavailableError
from geo_companion.starter_pack import PRACTICE_ROUNDS

ATTRIBUTION = PRACTICE_ROUNDS[0].asset_attribution
COUNTRIES = ("SK", "CZ", "PT", "FR", "DE", "IT", "ES", "PL", "AT", "HU", "SE", "NO")


def photo_round(index: int) -> PracticeRound:
    return PracticeRound(
        round_id=f"photo-{index:02d}",
        asset_id=f"{index:02d}.jpg",
        asset_kind=AssetKind.PHOTO,
        asset_attribution=ATTRIBUTION,
        asset_description="Street-level photo.",
        answer=SourceTruthAnswer(
            country_code=COUNTRIES[index % len(COUNTRIES)],
            explanation="Source truth.",
            citations=(Citation(**ATTRIBUTION.model_dump()),),
            answer_origin=AnswerOrigin.SOURCE_TRUTH,
        ),
    )


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value


class BrokenProvider(DummyProvider):
    def predict(self, round_: PracticeRoundPublic) -> tuple[ModelCandidate, ...]:
        raise RuntimeError("the model process went away")


def make(
    tmp_path: Path,
    photos: int = 10,
    provider: DummyProvider | None = None,
    allow_placeholder: bool = True,
) -> tuple[LearningService, RaceService, Clock]:
    learning = LearningService(
        tmp_path / "runtime.sqlite3",
        provider=provider if provider is not None else DummyProvider(),
        rounds=PRACTICE_ROUNDS + tuple(photo_round(i) for i in range(photos)),
    )
    clock = Clock()
    races = RaceService(
        learning, allow_placeholder_model=allow_placeholder, rng=random.Random(7), now=clock
    )
    return learning, races, clock


def answer_of(learning: LearningService, round_id: str) -> str:
    return learning._round(round_id).answer.country_code


def test_a_race_needs_a_real_model_and_enough_photo_rounds(tmp_path: Path) -> None:
    learning = LearningService(tmp_path / "a.sqlite3", provider=None, rounds=PRACTICE_ROUNDS)
    assert "no local model" in (RaceService(learning).unavailable_reason() or "")

    _, placeholder, _ = make(tmp_path / "b", allow_placeholder=False)
    assert "placeholder" in (placeholder.unavailable_reason() or "")
    with pytest.raises(RaceUnavailableError, match="placeholder"):
        placeholder.start(RaceStartRequest())

    _, too_few, _ = make(tmp_path / "c", photos=4)
    assert "at least 5 photo rounds" in (too_few.unavailable_reason() or "")

    _, ready, _ = make(tmp_path / "d")
    assert ready.unavailable_reason() is None


def test_a_full_race_scores_both_players_and_counts_as_practice(tmp_path: Path) -> None:
    learning, races, _ = make(tmp_path)
    started = races.start(RaceStartRequest())
    assert started.rounds_total == 5
    assert started.model.model_id == "dummy-placeholder"

    model_wins = learner_wins = 0
    for position in range(1, 6):
        public = races.round(started.race_id, position)
        assert public.round.asset_kind is AssetKind.PHOTO
        assert "answer" not in public.model_dump_json()
        truth = answer_of(learning, public.round.round_id)
        # Right on odd rounds, wrong on even rounds.
        guess = truth if position % 2 else ("ZZ" if truth != "ZZ" else "YY")
        result = races.answer(
            started.race_id, position, PracticeAnswerSubmission(country_code=guess)
        )
        expected_model = DummyProvider().predict(public.round)
        model_right = bool(expected_model) and expected_model[0].country_code == truth
        assert result.learner_points == int(position % 2 == 1)
        assert result.model_points == int(model_right)
        assert result.model_prediction is not None
        assert result.model_prediction.attempt_id == result.reveal.attempt_id
        learner_wins += result.learner_points
        model_wins += result.model_points
        assert result.score.learner == learner_wins
        assert result.score.model == model_wins
        assert result.finished is (position == 5)
        # The race answer is an ordinary attempt with a spaced-repetition schedule.
        assert result.reveal.study_progress is not None
        assert learning.progress(public.round.round_id).repetitions >= 0

    summary = races.summary(started.race_id)
    assert summary.finished_at is not None
    assert (summary.score.learner, summary.score.model) == (3, model_wins)
    assert len({row.round_id for row in summary.rounds}) == 5
    assert all(row.answered and row.answer_country_code for row in summary.rounds)
    assert summary.model_missed_rounds == 0


def test_the_summary_hides_answers_of_rounds_not_answered_yet(tmp_path: Path) -> None:
    _, races, _ = make(tmp_path)
    race_id = races.start(RaceStartRequest()).race_id
    races.round(race_id, 1)
    races.answer(race_id, 1, PracticeAnswerSubmission(skipped=True))
    rows = races.summary(race_id).rounds
    assert rows[0].answered and rows[0].answer_country_code is not None
    assert rows[0].learner_country_code is None
    for row in rows[1:]:
        assert not row.answered
        assert row.answer_country_code is None
        assert row.model_country_code is None


def test_rounds_must_be_played_in_order_and_answered_once(tmp_path: Path) -> None:
    _, races, _ = make(tmp_path)
    race_id = races.start(RaceStartRequest()).race_id
    with pytest.raises(RaceOrderError, match="earlier"):
        races.round(race_id, 2)
    with pytest.raises(RaceOrderError, match="Open the race round"):
        races.answer(race_id, 1, PracticeAnswerSubmission(skipped=True))
    races.round(race_id, 1)
    races.answer(race_id, 1, PracticeAnswerSubmission(skipped=True))
    with pytest.raises(RaceOrderError, match="already answered"):
        races.answer(race_id, 1, PracticeAnswerSubmission(skipped=True))
    with pytest.raises(KeyError):
        races.round(race_id, 6)
    with pytest.raises(KeyError):
        races.summary("no-such-race")


def test_reopening_a_round_does_not_restart_its_clock(tmp_path: Path) -> None:
    _, races, clock = make(tmp_path)
    race_id = races.start(RaceStartRequest(time_limit_seconds=30)).race_id
    first = races.round(race_id, 1)
    clock.value += timedelta(seconds=20)
    assert races.round(race_id, 1).started_at == first.started_at


def test_a_late_answer_scores_nothing_and_counts_as_a_skip(tmp_path: Path) -> None:
    learning, races, clock = make(tmp_path)
    race_id = races.start(RaceStartRequest(time_limit_seconds=30)).race_id
    public = races.round(race_id, 1)
    truth = answer_of(learning, public.round.round_id)

    clock.value += timedelta(seconds=34)  # inside the 5 s grace
    on_time = races.answer(race_id, 1, PracticeAnswerSubmission(country_code=truth))
    assert (on_time.timed_out, on_time.learner_points) == (False, 1)

    public = races.round(race_id, 2)
    clock.value += timedelta(seconds=36)
    truth = answer_of(learning, public.round.round_id)
    late = races.answer(race_id, 2, PracticeAnswerSubmission(country_code=truth))
    assert late.timed_out is True
    assert late.learner_points == 0
    assert late.reveal.submission.skipped is True


def test_a_failing_model_loses_only_that_round(tmp_path: Path) -> None:
    learning, races, _ = make(tmp_path, provider=BrokenProvider())
    race_id = races.start(RaceStartRequest()).race_id
    races.round(race_id, 1)
    result = races.answer(race_id, 1, PracticeAnswerSubmission(skipped=True))
    assert result.model_unavailable is True
    assert result.model_prediction is None
    assert result.model_points == 0
    assert races.summary(race_id).model_missed_rounds == 1


def test_a_different_model_after_a_restart_cannot_play_an_old_race(tmp_path: Path) -> None:
    learning, races, _ = make(tmp_path)
    race_id = races.start(RaceStartRequest()).race_id

    class NewerDummy(DummyProvider):
        info = ModelInfo(**{**DummyProvider.info.model_dump(), "version": "0.2.0"})

    learning.provider = NewerDummy()
    races.round(race_id, 1)
    result = races.answer(race_id, 1, PracticeAnswerSubmission(skipped=True))
    assert result.model_unavailable is True
    assert races.summary(race_id).model.version == "0.1.0"


def test_new_races_avoid_the_rounds_of_recent_races(tmp_path: Path) -> None:
    _, races, _ = make(tmp_path, photos=10)
    first = {row.round_id for row in races.summary(races.start(RaceStartRequest()).race_id).rounds}
    second = {row.round_id for row in races.summary(races.start(RaceStartRequest()).race_id).rounds}
    assert first.isdisjoint(second)
    third = {row.round_id for row in races.summary(races.start(RaceStartRequest()).race_id).rounds}
    assert len(third) == 5


def test_races_store_the_model_version_for_later_comparison(tmp_path: Path) -> None:
    learning, races, _ = make(tmp_path)
    races.start(RaceStartRequest())
    with sqlite3.connect(learning.database_path) as connection:
        assert connection.execute("SELECT model_id, model_version FROM races").fetchall() == [
            ("dummy-placeholder", "0.1.0")
        ]


def test_time_limits_are_bounded() -> None:
    with pytest.raises(ValueError):
        RaceStartRequest(time_limit_seconds=5)
    with pytest.raises(ValueError):
        RaceStartRequest(time_limit_seconds=601)
    assert RaceStartRequest().time_limit_seconds is None


def api(app: object, method: str, path: str, json: object | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_race_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from geo_companion import main

    learning, races, _ = make(tmp_path, allow_placeholder=False)
    monkeypatch.setattr(main, "learning_service", learning)
    monkeypatch.setattr(main, "race_service", races)

    # The app never races the placeholder.
    assert api(main.app, "GET", "/api/v1/races/availability").json() == {
        "available": False,
        "reason": "Race mode needs a real model; the placeholder model cannot race.",
    }
    assert api(main.app, "POST", "/api/v1/races", {}).status_code == 409

    races.allow_placeholder_model = True
    assert api(main.app, "GET", "/api/v1/races/availability").json()["available"] is True
    assert api(main.app, "POST", "/api/v1/races", {"time_limit_seconds": 3}).status_code == 422
    started = api(main.app, "POST", "/api/v1/races", {"time_limit_seconds": 60})
    assert started.status_code == 201
    race_id = started.json()["race_id"]

    assert api(main.app, "GET", f"/api/v1/races/{race_id}/rounds/2").status_code == 409
    public = api(main.app, "GET", f"/api/v1/races/{race_id}/rounds/1")
    assert public.status_code == 200
    assert "answer" not in public.json()["round"]
    answered = api(main.app, "POST", f"/api/v1/races/{race_id}/rounds/1/answers", {"skipped": True})
    assert answered.status_code == 200
    assert answered.json()["score"] == {"learner": 0, "model": answered.json()["model_points"]}
    again = api(main.app, "POST", f"/api/v1/races/{race_id}/rounds/1/answers", {"skipped": True})
    assert again.status_code == 409
    summary = api(main.app, "GET", f"/api/v1/races/{race_id}").json()
    assert summary["rounds"][1]["answer_country_code"] is None
    assert api(main.app, "GET", "/api/v1/races/unknown").status_code == 404
    assert api(main.app, "GET", "/api/v1/races/unknown/rounds/1").status_code == 404

    schema = main.app.openapi()["components"]["schemas"]
    assert "answer" not in schema["RaceRoundPublic"]["properties"]
    assert "answer" not in schema["PracticeRoundPublic"]["properties"]


def test_a_class_race_scores_normally_but_leaves_study_review_alone(tmp_path: Path) -> None:
    from geo_companion.contracts import RacePlayer

    learning, races, _ = make(tmp_path)
    started = races.start(RaceStartRequest(player=RacePlayer.CLASS))
    assert started.player is RacePlayer.CLASS
    public = races.round(started.race_id, 1)
    truth = answer_of(learning, public.round.round_id)
    result = races.answer(started.race_id, 1, PracticeAnswerSubmission(country_code=truth))
    assert result.learner_points == 1
    assert result.reveal.study_progress is None
    assert learning.next_review().progress is None
    assert races.summary(started.race_id).player is RacePlayer.CLASS

    solo = races.start(RaceStartRequest())
    assert races.summary(solo.race_id).player is RacePlayer.YOU


def test_an_old_races_table_gains_the_player_column(tmp_path: Path) -> None:
    database = tmp_path / "runtime.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE races (race_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, "
            "model_id TEXT NOT NULL, model_version TEXT NOT NULL, model_json TEXT NOT NULL, "
            "time_limit_seconds INTEGER, created_at TEXT NOT NULL, finished_at TEXT)"
        )
    learning = LearningService(
        database,
        provider=DummyProvider(),
        rounds=PRACTICE_ROUNDS + tuple(photo_round(i) for i in range(6)),
    )
    races = RaceService(learning, allow_placeholder_model=True)
    assert races.summary(races.start(RaceStartRequest()).race_id).player.value == "you"

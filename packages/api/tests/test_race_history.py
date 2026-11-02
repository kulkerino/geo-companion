from __future__ import annotations

from pathlib import Path

import pytest
from geo_companion.contracts import (
    ModelCandidate,
    ModelInfo,
    PracticeAnswerSubmission,
    PracticeRoundPublic,
    RacePlayer,
    RaceStartRequest,
)
from geo_companion.learning import LearningService
from geo_companion.models import DummyProvider
from geo_companion.race import RaceService, RaceUnavailableError
from geo_companion.race_history import RaceHistoryService, photo_set_id
from test_race import BrokenProvider, answer_of, api, make


def play(
    learning: LearningService,
    races: RaceService,
    right: int,
    player: RacePlayer = RacePlayer.YOU,
) -> str:
    """Finish one race, answering the first ``right`` rounds correctly and skipping the rest."""
    race_id = races.start(RaceStartRequest(player=player)).race_id
    for position in range(1, 6):
        public = races.round(race_id, position)
        submission = (
            PracticeAnswerSubmission(country_code=answer_of(learning, public.round.round_id))
            if position <= right
            else PracticeAnswerSubmission(skipped=True)
        )
        races.answer(race_id, position, submission)
    return race_id


class OracleProvider(DummyProvider):
    """Always right: a stand-in for a better, later model version."""

    def __init__(self, learning: LearningService) -> None:
        super().__init__()
        self.learning = learning
        self.info = ModelInfo(**{**DummyProvider().info.model_dump(), "version": "0.2.0"})

    def predict(self, round_: PracticeRoundPublic) -> tuple[ModelCandidate, ...]:
        code = self.learning._round(round_.round_id).answer.country_code
        return (ModelCandidate(country_code=code, confidence=0.9),)


def test_history_counts_only_finished_races_and_never_shows_answers(tmp_path: Path) -> None:
    learning, races, _ = make(tmp_path)
    history = RaceHistoryService(races)
    assert history.history().overall.races == 0

    finished = [play(learning, races, right=5), play(learning, races, right=0)]
    unfinished = races.start(RaceStartRequest()).race_id
    races.round(unfinished, 1)

    result = history.history()
    assert [entry.race_id for entry in result.races] == list(reversed(finished))
    assert unfinished not in result.model_dump_json()
    overall = result.overall
    assert (overall.races, overall.rounds, overall.learner_points) == (2, 10, 5)
    model_points = sum(races.summary(race_id).score.model for race_id in finished)
    assert overall.model_points == model_points
    assert overall.learner_wins + overall.model_wins + overall.draws == 2
    assert len(result.by_model) == 1
    assert result.by_model[0].tally == overall
    # Totals and scores only: no round ids, answers or guesses.
    dumped = result.model_dump_json()
    assert "round_id" not in dumped
    assert "country_code" not in dumped


def test_class_races_are_left_out_of_your_history(tmp_path: Path) -> None:
    learning, races, _ = make(tmp_path)
    yours = play(learning, races, right=2)
    class_race = play(learning, races, right=5, player=RacePlayer.CLASS)

    result = RaceHistoryService(races).history()
    assert [entry.race_id for entry in result.races] == [yours]
    assert class_race not in result.model_dump_json()
    assert (result.overall.races, result.overall.learner_points) == (1, 2)
    assert [record.tally.races for record in result.by_model] == [1]


def test_history_keeps_a_record_per_model_version(tmp_path: Path) -> None:
    learning, races, _ = make(tmp_path)
    play(learning, races, right=1)
    learning.provider = OracleProvider(learning)
    play(learning, races, right=1)

    records = RaceHistoryService(races).history().by_model
    assert [record.model.version for record in records] == ["0.1.0", "0.2.0"]
    oracle = records[1].tally
    assert (oracle.learner_points, oracle.model_points, oracle.model_wins) == (1, 5, 1)


def test_benchmarks_compare_model_versions_on_the_same_photos(tmp_path: Path) -> None:
    learning, races, clock = make(tmp_path)
    history = RaceHistoryService(races, now=clock)
    empty = history.benchmarks()
    assert empty.runs == ()
    assert empty.can_run is True
    assert empty.photo_rounds == 10
    assert empty.photo_set_id == photo_set_id([f"photo-{i:02d}" for i in range(10)])

    dummy = history.run_benchmark()
    assert dummy.rounds == 10
    assert dummy.correct + dummy.abstained + dummy.failed <= 10
    assert dummy.accuracy == dummy.correct / 10
    # Deterministic models are run once per photo set.
    assert history.run_benchmark() == dummy

    learning.provider = OracleProvider(learning)
    oracle = history.run_benchmark()
    assert (oracle.correct, oracle.accuracy) == (10, 1.0)

    runs = history.benchmarks().runs
    assert [run.model.version for run in runs] == ["0.1.0", "0.2.0"]
    assert {run.photo_set_id for run in runs} == {empty.photo_set_id}
    # A benchmark is not practice: it adds no attempts or reviews.
    assert learning.attempt_history("photo-00") == []


def test_a_failing_model_scores_nothing_on_the_photos_it_fails(tmp_path: Path) -> None:
    _, races, _ = make(tmp_path, provider=BrokenProvider())
    run = RaceHistoryService(races).run_benchmark()
    assert (run.correct, run.failed, run.accuracy) == (0, 10, 0.0)


def test_the_placeholder_and_no_model_cannot_benchmark(tmp_path: Path) -> None:
    _, races, _ = make(tmp_path, allow_placeholder=False)
    history = RaceHistoryService(races)
    assert history.benchmarks().can_run is False
    assert "placeholder" in (history.benchmarks().reason or "")
    with pytest.raises(RaceUnavailableError):
        history.run_benchmark()


def test_photo_set_ids_ignore_order_and_change_with_the_photos() -> None:
    assert photo_set_id(["b", "a"]) == photo_set_id(["a", "b"])
    assert photo_set_id(["a", "b"]) != photo_set_id(["a", "c"])
    assert photo_set_id(["a", "b"]).startswith("photos-2-")


def test_race_history_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from geo_companion import main

    learning, races, _ = make(tmp_path, allow_placeholder=False)
    monkeypatch.setattr(main, "learning_service", learning)
    monkeypatch.setattr(main, "race_service", races)
    monkeypatch.setattr(main, "race_history_service", None)

    # "history" is a route of its own, not a race id.
    empty = api(main.app, "GET", "/api/v1/races/history")
    assert empty.status_code == 200
    assert empty.json()["overall"]["races"] == 0
    assert api(main.app, "POST", "/api/v1/models/benchmarks").status_code == 409
    assert api(main.app, "GET", "/api/v1/models/benchmarks").json()["can_run"] is False

    races.allow_placeholder_model = True
    play(learning, races, right=2)
    assert api(main.app, "GET", "/api/v1/races/history").json()["overall"]["learner_points"] == 2
    run = api(main.app, "POST", "/api/v1/models/benchmarks")
    assert run.status_code == 200
    assert api(main.app, "GET", "/api/v1/models/benchmarks").json()["runs"] == [run.json()]

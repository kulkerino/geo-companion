"""Race mode: the learner and the enabled model guess the same photo rounds.

A race is a thin record over things that already exist. The learner's answer is an ordinary
practice attempt (so it feeds spaced repetition), and the model's guess is the stored
post-answer prediction for that attempt. The model only ever sees the public round, and it is
deterministic, so asking it after the learner answers is as fair as asking it before, and no
route ever shows a round's answer or the model's guess before the learner has answered.
See docs/race-mode-plan.md.
"""

from __future__ import annotations

import random
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from geo_companion.contracts import (
    RACE_ROUNDS,
    AssetKind,
    ModelInfo,
    ModelPredictionResult,
    PracticeAnswerSubmission,
    PracticeRoundPublic,
    RacePlayer,
    RaceRoundPublic,
    RaceRoundResult,
    RaceRoundSummary,
    RaceScore,
    RaceStarted,
    RaceStartRequest,
    RaceSummary,
)
from geo_companion.learning import LearningService

# Rounds of the most recent races are avoided when enough other photo rounds exist.
RECENT_RACES_AVOIDED = 3
# Network and rendering delay allowed past the time limit before an answer counts as late.
TIME_LIMIT_GRACE = timedelta(seconds=5)


class RaceUnavailableError(RuntimeError):
    """A race cannot start: no real model is enabled, or there are too few photo rounds."""


class RaceOrderError(RuntimeError):
    """A race round was requested or answered out of order, or answered twice."""


class RaceService:
    def __init__(
        self,
        learning: LearningService,
        *,
        allow_placeholder_model: bool = False,
        rng: random.Random | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.learning = learning
        # kulo, 2026-11-02: no racing the placeholder in the app; tests opt in explicitly.
        self.allow_placeholder_model = allow_placeholder_model
        self.rng = rng or random.Random()
        self.now = now
        with self.learning._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS races (
                    race_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL,
                    model_id TEXT NOT NULL, model_version TEXT NOT NULL,
                    model_json TEXT NOT NULL, time_limit_seconds INTEGER,
                    created_at TEXT NOT NULL, finished_at TEXT
                );
                CREATE TABLE IF NOT EXISTS race_rounds (
                    race_id TEXT NOT NULL, position INTEGER NOT NULL, round_id TEXT NOT NULL,
                    started_at TEXT, attempt_id TEXT, learner_points INTEGER,
                    model_points INTEGER, model_country_code TEXT,
                    timed_out INTEGER NOT NULL DEFAULT 0,
                    model_unavailable INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (race_id, position)
                );
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(races)")}
            if "player" not in columns:
                connection.execute(
                    "ALTER TABLE races ADD COLUMN player TEXT NOT NULL DEFAULT 'you'"
                )

    def _photo_round_ids(self) -> list[str]:
        return [r.round_id for r in self.learning.rounds if r.asset_kind is AssetKind.PHOTO]

    def unavailable_reason(self) -> str | None:
        """Why a race cannot start right now, or None when it can."""
        provider = self.learning.provider
        if provider is None:
            return "Race mode needs a model, and no local model is enabled."
        if provider.info.is_placeholder and not self.allow_placeholder_model:
            return "Race mode needs a real model; the placeholder model cannot race."
        if len(self._photo_round_ids()) < RACE_ROUNDS:
            return f"Race mode needs a photo pack with at least {RACE_ROUNDS} photo rounds."
        return None

    def start(self, request: RaceStartRequest) -> RaceStarted:
        reason = self.unavailable_reason()
        if reason is not None:
            raise RaceUnavailableError(reason)
        provider = self.learning.provider
        assert provider is not None
        race_id = str(uuid.uuid4())
        with self.learning._connect() as connection:
            recent = {
                row["round_id"]
                for row in connection.execute(
                    "SELECT round_id FROM race_rounds WHERE race_id IN (SELECT race_id FROM "
                    "races WHERE learner_id = ? ORDER BY created_at DESC LIMIT ?)",
                    (self.learning.learner_id, RECENT_RACES_AVOIDED),
                )
            }
            photo_ids = self._photo_round_ids()
            fresh = [round_id for round_id in photo_ids if round_id not in recent]
            used = [round_id for round_id in photo_ids if round_id in recent]
            self.rng.shuffle(fresh)
            self.rng.shuffle(used)
            chosen = (fresh + used)[:RACE_ROUNDS]
            connection.execute(
                "INSERT INTO races (race_id, learner_id, model_id, model_version, model_json, "
                "time_limit_seconds, created_at, player) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    race_id,
                    self.learning.learner_id,
                    provider.info.model_id,
                    provider.info.version,
                    provider.info.model_dump_json(),
                    request.time_limit_seconds,
                    self.now().isoformat(),
                    request.player.value,
                ),
            )
            connection.executemany(
                "INSERT INTO race_rounds (race_id, position, round_id) VALUES (?, ?, ?)",
                [(race_id, position, round_id) for position, round_id in enumerate(chosen, 1)],
            )
        return RaceStarted(
            race_id=race_id,
            model=provider.info,
            rounds_total=len(chosen),
            time_limit_seconds=request.time_limit_seconds,
            player=request.player,
        )

    def _race(self, connection: sqlite3.Connection, race_id: str) -> sqlite3.Row:
        race: sqlite3.Row | None = connection.execute(
            "SELECT * FROM races WHERE race_id = ? AND learner_id = ?",
            (race_id, self.learning.learner_id),
        ).fetchone()
        if race is None:
            raise KeyError(race_id)
        return race

    def _rows(self, connection: sqlite3.Connection, race_id: str) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM race_rounds WHERE race_id = ? ORDER BY position", (race_id,)
        ).fetchall()

    def _round_row(
        self, connection: sqlite3.Connection, race_id: str, position: int
    ) -> tuple[sqlite3.Row, list[sqlite3.Row]]:
        self._race(connection, race_id)
        rows = self._rows(connection, race_id)
        if not 1 <= position <= len(rows):
            raise KeyError(f"{race_id}/{position}")
        if any(row["attempt_id"] is None for row in rows[: position - 1]):
            raise RaceOrderError("Answer the earlier race rounds first.")
        return rows[position - 1], rows

    def round(self, race_id: str, position: int) -> RaceRoundPublic:
        """Show one round's public payload and start its clock on the first request."""
        with self.learning._connect() as connection:
            race = self._race(connection, race_id)
            row, rows = self._round_row(connection, race_id, position)
            started_at = row["started_at"]
            if started_at is None:
                started_at = self.now().isoformat()
                connection.execute(
                    "UPDATE race_rounds SET started_at = ? WHERE race_id = ? AND position = ?",
                    (started_at, race_id, position),
                )
        return RaceRoundPublic(
            race_id=race_id,
            position=position,
            rounds_total=len(rows),
            round=self.learning.round_public(row["round_id"]),
            started_at=datetime.fromisoformat(started_at),
            time_limit_seconds=race["time_limit_seconds"],
        )

    def _model_guess(self, race_model: ModelInfo, attempt_id: str) -> ModelPredictionResult | None:
        """The stored post-answer prediction, or None if the race's model cannot answer."""
        provider = self.learning.provider
        # A restart with another model must not let a different model play this race.
        if provider is None or provider.info != race_model:
            return None
        try:
            return self.learning.model_prediction(attempt_id)
        except Exception:  # noqa: BLE001 - any model failure costs the model this round only
            return None

    def answer(
        self, race_id: str, position: int, submission: PracticeAnswerSubmission
    ) -> RaceRoundResult:
        with self.learning._connect() as connection:
            race = self._race(connection, race_id)
            row, rows = self._round_row(connection, race_id, position)
        if row["attempt_id"] is not None:
            raise RaceOrderError("This race round is already answered.")
        if row["started_at"] is None:
            raise RaceOrderError("Open the race round before answering it.")
        limit = race["time_limit_seconds"]
        late = limit is not None and self.now() > (
            datetime.fromisoformat(row["started_at"]) + timedelta(seconds=limit) + TIME_LIMIT_GRACE
        )
        # A late answer counts as a skip, for the points and for spaced repetition alike.
        if late:
            submission = PracticeAnswerSubmission(skipped=True)
        player = RacePlayer(race["player"])
        reveal = self.learning.submit_practice(
            row["round_id"], submission, record_review=player is RacePlayer.YOU
        )
        race_model = ModelInfo.model_validate_json(race["model_json"])
        prediction = self._model_guess(race_model, reveal.attempt_id)
        model_country = (
            None
            if prediction is None or prediction.abstained
            else prediction.candidates[0].country_code
        )
        answer = reveal.answer.country_code
        learner_points = int(reveal.is_correct)
        model_points = int(model_country == answer)
        with self.learning._connect() as connection:
            updated = connection.execute(
                "UPDATE race_rounds SET attempt_id = ?, learner_points = ?, model_points = ?, "
                "model_country_code = ?, timed_out = ?, model_unavailable = ? "
                "WHERE race_id = ? AND position = ? AND attempt_id IS NULL",
                (
                    reveal.attempt_id,
                    learner_points,
                    model_points,
                    model_country,
                    int(late),
                    int(prediction is None),
                    race_id,
                    position,
                ),
            )
            if updated.rowcount != 1:
                raise RaceOrderError("This race round is already answered.")
            finished = position == len(rows)
            if finished:
                connection.execute(
                    "UPDATE races SET finished_at = ? WHERE race_id = ?",
                    (self.now().isoformat(), race_id),
                )
            score = self._score(self._rows(connection, race_id))
        return RaceRoundResult(
            race_id=race_id,
            position=position,
            reveal=reveal,
            model_prediction=prediction,
            model_unavailable=prediction is None,
            timed_out=late,
            learner_points=learner_points,
            model_points=model_points,
            score=score,
            finished=finished,
        )

    @staticmethod
    def _score(rows: list[sqlite3.Row]) -> RaceScore:
        return RaceScore(
            learner=sum(row["learner_points"] or 0 for row in rows),
            model=sum(row["model_points"] or 0 for row in rows),
        )

    def summary(self, race_id: str) -> RaceSummary:
        with self.learning._connect() as connection:
            race = self._race(connection, race_id)
            rows = self._rows(connection, race_id)
            attempts = {
                attempt["attempt_id"]: attempt["submission_json"]
                for attempt in connection.execute(
                    "SELECT attempt_id, submission_json FROM learner_practice_attempts "
                    "WHERE learner_id = ?",
                    (self.learning.learner_id,),
                )
                if attempt["attempt_id"] in {row["attempt_id"] for row in rows}
            }
        summaries = []
        for row in rows:
            round_public: PracticeRoundPublic = self.learning.round_public(row["round_id"])
            answered = row["attempt_id"] is not None
            submission = (
                PracticeAnswerSubmission.model_validate_json(attempts[row["attempt_id"]])
                if answered
                else None
            )
            summaries.append(
                RaceRoundSummary(
                    position=row["position"],
                    round_id=row["round_id"],
                    asset_id=round_public.asset_id,
                    answered=answered,
                    # The answer is shown only for rounds the learner has already answered.
                    answer_country_code=(
                        self.learning._round(row["round_id"]).answer.country_code
                        if answered
                        else None
                    ),
                    learner_country_code=None if submission is None else submission.country_code,
                    model_country_code=row["model_country_code"],
                    learner_points=row["learner_points"],
                    model_points=row["model_points"],
                    timed_out=bool(row["timed_out"]),
                    model_unavailable=bool(row["model_unavailable"]),
                )
            )
        return RaceSummary(
            race_id=race_id,
            model=ModelInfo.model_validate_json(race["model_json"]),
            time_limit_seconds=race["time_limit_seconds"],
            player=RacePlayer(race["player"]),
            created_at=datetime.fromisoformat(race["created_at"]),
            finished_at=(
                None if race["finished_at"] is None else datetime.fromisoformat(race["finished_at"])
            ),
            rounds=tuple(summaries),
            score=self._score(rows),
            model_missed_rounds=sum(row["model_unavailable"] for row in rows),
        )

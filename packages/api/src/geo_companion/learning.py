"""Local deterministic Open Practice loop backed by SQLite; it makes no network calls."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from geo_companion.contracts import (
    Feedback,
    PracticeAnswerResult,
    PracticeAnswerSubmission,
    PracticeClue,
    PracticeRound,
    PracticeRoundPublic,
    StudyProgress,
    StudyReview,
)
from geo_companion.starter_pack import PRACTICE_ROUNDS

# SM-2 quality per practice outcome. Uncertainty on a correct answer lowers the quality so the
# round's ease drops and later intervals grow more slowly than for a confident correct answer.
QUALITY_CONFIDENT_CORRECT = 4
QUALITY_UNCERTAIN_CORRECT = 3
QUALITY_INCORRECT = 2
QUALITY_SKIPPED = 1


class LearningService:
    """Own one pseudonymous learner's local history and immutable starter content."""

    learner_id = "local-learner"

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS learner_review_schedule (
                    learner_id TEXT NOT NULL, round_id TEXT NOT NULL,
                    repetitions INTEGER NOT NULL, interval_days INTEGER NOT NULL,
                    ease_factor REAL NOT NULL, last_reviewed_on TEXT NOT NULL,
                    PRIMARY KEY (learner_id, round_id)
                );
                CREATE TABLE IF NOT EXISTS learner_practice_attempts (
                    attempt_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, round_id TEXT NOT NULL,
                    submission_json TEXT NOT NULL, is_correct INTEGER NOT NULL,
                    answer_origin TEXT NOT NULL, reported_issue INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS learner_feedback (
                    feedback_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, attempt_id TEXT,
                    round_id TEXT NOT NULL, rating INTEGER NOT NULL, note TEXT,
                    reported_issue INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(learner_practice_attempts)")
            }
            if "reported_issue" not in columns:
                connection.execute(
                    "ALTER TABLE learner_practice_attempts "
                    "ADD COLUMN reported_issue INTEGER NOT NULL DEFAULT 0"
                )

    @staticmethod
    def _round(round_id: str) -> PracticeRound:
        round_ = next((item for item in PRACTICE_ROUNDS if item.round_id == round_id), None)
        if round_ is None:
            raise KeyError(round_id)
        return round_

    def next_round(self) -> PracticeRoundPublic:
        """Advance past the most recently attempted round, so retries never skip a round."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT round_id FROM learner_practice_attempts WHERE learner_id = ? "
                "ORDER BY rowid DESC LIMIT 1",
                (self.learner_id,),
            ).fetchone()
        round_ids = [item.round_id for item in PRACTICE_ROUNDS]
        if row is None or row["round_id"] not in round_ids:
            index = 0
        else:
            index = (round_ids.index(row["round_id"]) + 1) % len(PRACTICE_ROUNDS)
        return PracticeRoundPublic.from_round(PRACTICE_ROUNDS[index])

    def round_public(self, round_id: str) -> PracticeRoundPublic:
        return PracticeRoundPublic.from_round(self._round(round_id))

    def clue(self, round_id: str) -> PracticeClue:
        return PracticeClue(round_id=round_id, clue=self._round(round_id).clue)

    def submit_practice(
        self, round_id: str, submission: PracticeAnswerSubmission
    ) -> PracticeAnswerResult:
        round_ = self._round(round_id)
        is_correct = (
            not submission.skipped and submission.country_code == round_.answer.country_code
        )
        attempt_id = str(uuid.uuid4())
        submitted_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO learner_practice_attempts (attempt_id, learner_id, round_id, "
                "submission_json, is_correct, answer_origin, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    attempt_id,
                    self.learner_id,
                    round_id,
                    submission.model_dump_json(),
                    int(is_correct),
                    round_.answer.answer_origin.value,
                    submitted_at.isoformat(),
                ),
            )
        if submission.skipped:
            quality = QUALITY_SKIPPED
        elif not is_correct:
            quality = QUALITY_INCORRECT
        elif submission.uncertain:
            quality = QUALITY_UNCERTAIN_CORRECT
        else:
            quality = QUALITY_CONFIDENT_CORRECT
        return PracticeAnswerResult(
            round_id=round_id,
            answer=round_.answer,
            attempt_id=attempt_id,
            is_correct=is_correct,
            submission=submission,
            study_progress=self.schedule_review(round_id, quality, submitted_at),
        )

    def record_feedback(self, feedback: Feedback) -> None:
        with self._connect() as connection:
            attempt = connection.execute(
                "SELECT round_id FROM learner_practice_attempts "
                "WHERE attempt_id = ? AND learner_id = ?",
                (feedback.attempt_id, self.learner_id),
            ).fetchone()
            if attempt is None or attempt["round_id"] != feedback.round_id:
                raise KeyError(feedback.attempt_id)
            connection.execute(
                "UPDATE learner_practice_attempts SET reported_issue = ? WHERE attempt_id = ?",
                (int(feedback.reported_issue), feedback.attempt_id),
            )
            connection.execute(
                "INSERT INTO learner_feedback VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    self.learner_id,
                    feedback.attempt_id,
                    feedback.round_id,
                    feedback.rating,
                    feedback.note,
                    int(feedback.reported_issue),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def attempt_history(self, round_id: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT attempt_id, answer_origin, is_correct, reported_issue "
                "FROM learner_practice_attempts WHERE learner_id = ? AND round_id = ? "
                "ORDER BY rowid",
                (self.learner_id, round_id),
            ).fetchall()
        return [
            {
                "attempt_id": row["attempt_id"],
                "answer_origin": row["answer_origin"],
                "is_correct": bool(row["is_correct"]),
                "reported_issue": bool(row["reported_issue"]),
            }
            for row in rows
        ]

    def schedule_review(self, round_id: str, quality: int, reviewed_at: datetime) -> StudyProgress:
        """Apply SM-2: the interval uses the prior ease factor, then the ease is updated."""
        self._round(round_id)
        if not 0 <= quality <= 5:
            raise ValueError("quality must be between 0 and 5")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT repetitions, interval_days, ease_factor FROM learner_review_schedule "
                "WHERE learner_id = ? AND round_id = ?",
                (self.learner_id, round_id),
            ).fetchone()
            repetitions, interval, ease = (0, 0, 2.5) if row is None else tuple(row)
            if quality < 3:
                repetitions, interval = 0, 1
            elif repetitions == 0:
                repetitions, interval = 1, 1
            elif repetitions == 1:
                repetitions, interval = 2, 6
            else:
                repetitions, interval = repetitions + 1, max(1, round(interval * ease))
            ease = round(max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)), 2)
            progress = StudyProgress(
                round_id=round_id,
                repetitions=repetitions,
                interval_days=interval,
                ease_factor=ease,
                last_reviewed_on=reviewed_at.astimezone(UTC).date(),
            )
            connection.execute(
                "INSERT INTO learner_review_schedule VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(learner_id, round_id) DO UPDATE SET "
                "repetitions=excluded.repetitions, interval_days=excluded.interval_days, "
                "ease_factor=excluded.ease_factor, last_reviewed_on=excluded.last_reviewed_on",
                (
                    self.learner_id,
                    round_id,
                    progress.repetitions,
                    progress.interval_days,
                    progress.ease_factor,
                    progress.last_reviewed_on.isoformat(),
                ),
            )
        return progress

    def _schedule_rows(self) -> list[StudyProgress]:
        known = {item.round_id for item in PRACTICE_ROUNDS}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT round_id, repetitions, interval_days, ease_factor, last_reviewed_on "
                "FROM learner_review_schedule WHERE learner_id = ?",
                (self.learner_id,),
            ).fetchall()
        return [StudyProgress(**dict(row)) for row in rows if row["round_id"] in known]

    def progress(self, round_id: str) -> StudyProgress:
        match = next((item for item in self._schedule_rows() if item.round_id == round_id), None)
        if match is None:
            raise KeyError(round_id)
        return match

    def next_review(self) -> StudyReview:
        """Return the round with the earliest computed due date (last review + interval)."""
        queue = sorted(self._schedule_rows(), key=lambda item: (item.next_review_on, item.round_id))
        return StudyReview(progress=queue[0] if queue else None)

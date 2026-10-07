"""Local deterministic learning loop backed by SQLite; it makes no network calls."""
# ruff: noqa: E501

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from geo_companion.contracts import (
    Feedback,
    LessonPublic,
    PracticeAnswerResult,
    PracticeAnswerSubmission,
    PracticeRoundPublic,
    QuizAnswerResult,
    QuizItemPublic,
    StudyProgress,
)
from geo_companion.starter_pack import LESSONS, PRACTICE_ROUNDS


class LearningService:
    """Own one pseudonymous learner's local history and immutable starter content."""

    learner_id = "local-learner"

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS learner_study_progress (
                    learner_id TEXT NOT NULL, lesson_id TEXT NOT NULL,
                    repetitions INTEGER NOT NULL, interval_days INTEGER NOT NULL,
                    ease_factor REAL NOT NULL, last_reviewed_on TEXT NOT NULL,
                    PRIMARY KEY (learner_id, lesson_id)
                );
                CREATE TABLE IF NOT EXISTS learner_practice_attempts (
                    attempt_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, round_id TEXT NOT NULL,
                    submission_json TEXT NOT NULL, is_correct INTEGER NOT NULL,
                    answer_origin TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS learner_feedback (
                    feedback_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, attempt_id TEXT,
                    round_id TEXT NOT NULL, rating INTEGER NOT NULL, note TEXT,
                    reported_issue INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                """
            )

    def lessons(self) -> tuple[LessonPublic, ...]:
        return tuple(self._public_lesson(lesson) for lesson in LESSONS)

    def _public_lesson(self, lesson: object) -> LessonPublic:
        from geo_companion.contracts import Lesson

        assert isinstance(lesson, Lesson)
        return LessonPublic(
            lesson_id=lesson.lesson_id,
            title=lesson.title,
            body=lesson.body,
            citations=lesson.citations,
            quiz_items=tuple(
                QuizItemPublic(
                    quiz_id=item.quiz_id,
                    prompt=item.prompt,
                    choices=item.choices,
                )
                for item in lesson.quiz_items
            ),
        )

    def lesson_public(self, lesson_id: str) -> LessonPublic:
        for lesson in LESSONS:
            if lesson.lesson_id == lesson_id:
                return self._public_lesson(lesson)
        raise KeyError(lesson_id)

    def answer_quiz(self, lesson_id: str, quiz_id: str, selected_choice: str) -> QuizAnswerResult:
        lesson = next((item for item in LESSONS if item.lesson_id == lesson_id), None)
        if lesson is None:
            raise KeyError(lesson_id)
        quiz = next((item for item in lesson.quiz_items if item.quiz_id == quiz_id), None)
        if quiz is None:
            raise KeyError(quiz_id)
        if selected_choice not in quiz.choices:
            raise ValueError("selected_choice must be one of the offered choices")
        return QuizAnswerResult(
            lesson_id=lesson_id,
            quiz_id=quiz_id,
            selected_choice=selected_choice,
            is_correct=selected_choice == quiz.correct_choice,
            explanation=quiz.explanation,
            citations=quiz.citations,
        )

    def next_round(self) -> PracticeRoundPublic:
        return PracticeRoundPublic.from_round(PRACTICE_ROUNDS[0])

    def submit_practice(
        self, round_id: str, submission: PracticeAnswerSubmission
    ) -> PracticeAnswerResult:
        round_ = next((item for item in PRACTICE_ROUNDS if item.round_id == round_id), None)
        if round_ is None:
            raise KeyError(round_id)
        is_correct = (
            not submission.skipped and submission.country_code == round_.answer.country_code
        )
        attempt_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO learner_practice_attempts VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    attempt_id,
                    self.learner_id,
                    round_id,
                    submission.model_dump_json(),
                    int(is_correct),
                    "source_truth",
                    now,
                ),
            )
        return PracticeAnswerResult(
            round_id=round_id,
            answer=round_.answer,
            attempt_id=attempt_id,
            is_correct=is_correct,
            submission=submission,
        )

    def record_feedback(self, feedback: Feedback, attempt_id: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO learner_feedback VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    self.learner_id,
                    attempt_id,
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
                """SELECT a.answer_origin, f.reported_issue FROM learner_practice_attempts a
                LEFT JOIN learner_feedback f ON f.attempt_id = a.attempt_id
                WHERE a.round_id = ? ORDER BY a.created_at""",
                (round_id,),
            ).fetchall()
        return [
            {"answer_origin": row["answer_origin"], "reported_issue": bool(row["reported_issue"])}
            for row in rows
        ]

    def grade_lesson(self, lesson_id: str, quality: int, reviewed_at: datetime) -> StudyProgress:
        if lesson_id not in {lesson.lesson_id for lesson in LESSONS}:
            raise KeyError(lesson_id)
        if not 0 <= quality <= 5:
            raise ValueError("quality must be between 0 and 5")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT repetitions, interval_days, ease_factor FROM learner_study_progress WHERE learner_id=? AND lesson_id=?",
                (self.learner_id, lesson_id),
            ).fetchone()
            repetitions, interval, ease = (0, 0, 2.5) if row is None else tuple(row)
            ease = max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            if quality < 3:
                repetitions, interval = 0, 1
            elif repetitions == 0:
                repetitions, interval = 1, 1
            elif repetitions == 1:
                repetitions, interval = 2, 6
            else:
                repetitions, interval = repetitions + 1, max(1, round(interval * ease))
            progress = StudyProgress(
                lesson_id=lesson_id,
                repetitions=repetitions,
                interval_days=interval,
                ease_factor=round(ease, 2),
                last_reviewed_on=reviewed_at.date(),
            )
            connection.execute(
                """INSERT INTO learner_study_progress VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(learner_id, lesson_id) DO UPDATE SET repetitions=excluded.repetitions,
                interval_days=excluded.interval_days, ease_factor=excluded.ease_factor,
                last_reviewed_on=excluded.last_reviewed_on""",
                (
                    self.learner_id,
                    lesson_id,
                    repetitions,
                    interval,
                    round(ease, 2),
                    reviewed_at.date().isoformat(),
                ),
            )
        return progress

    def progress(self, lesson_id: str) -> StudyProgress:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT repetitions, interval_days, ease_factor, last_reviewed_on FROM learner_study_progress WHERE learner_id=? AND lesson_id=?",
                (self.learner_id, lesson_id),
            ).fetchone()
        if row is None:
            raise KeyError(lesson_id)
        return StudyProgress(lesson_id=lesson_id, **dict(row))

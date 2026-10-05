"""Versioned domain contracts for offline Geo Companion content and study state."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ContractModel(BaseModel):
    """Strict, immutable API/domain value object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def model_copy(
        self, *, update: Mapping[str, Any] | None = None, deep: bool = False
    ) -> Self:
        """Forbid copying with updates so content versions cannot be rewritten."""
        if update:
            msg = "Contract models are immutable; create a new version instead."
            raise TypeError(msg)
        return super().model_copy(deep=deep)


class RightsStatus(StrEnum):
    CLEARED = "cleared"
    REFERENCE_ONLY = "reference-only"
    QUARANTINED = "quarantined"


class AnswerOrigin(StrEnum):
    SOURCE_TRUTH = "source_truth"
    AUTHORED = "authored"
    USER_CORRECTION = "user_correction"
    MODEL_PREDICTION = "model_prediction"
    IMPORTED = "imported"


class Attribution(ContractModel):
    """Rights and provenance required for every published educational claim or asset."""

    source_title: str = Field(min_length=1)
    source_url: HttpUrl
    creator: str = Field(min_length=1)
    license_name: str = Field(min_length=1)
    license_url: HttpUrl
    attribution_text: str = Field(min_length=1)
    accessed_on: date
    reviewed_on: date
    geographic_scope: str = Field(min_length=1)
    rights_status: RightsStatus


class Citation(Attribution):
    """A citation is an attribution attached to a claim."""


class QuizItem(ContractModel):
    quiz_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    choices: tuple[str, ...] = Field(min_length=2)
    correct_choice: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    citations: tuple[Citation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def correct_choice_must_be_offered(self) -> QuizItem:
        if self.correct_choice not in self.choices:
            msg = "correct_choice must be one of choices"
            raise ValueError(msg)
        return self


class Lesson(ContractModel):
    lesson_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    citations: tuple[Citation, ...] = Field(min_length=1)
    quiz_items: tuple[QuizItem, ...]


class Coordinate(ContractModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class SourceTruthAnswer(ContractModel):
    """Pack-authored ground truth; never derived from learner or model activity."""

    country_code: str = Field(min_length=2, max_length=2)
    coordinate: Coordinate
    explanation: str = Field(min_length=1)
    citations: tuple[Citation, ...] = Field(min_length=1)
    answer_origin: Literal[AnswerOrigin.SOURCE_TRUTH, AnswerOrigin.AUTHORED]


class PracticeRound(ContractModel):
    round_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    asset_attribution: Attribution
    answer: SourceTruthAnswer


class PracticeRoundPublic(ContractModel):
    """Pre-submission contract deliberately omitting both answer and coordinates."""

    round_id: str
    asset_id: str
    asset_attribution: Attribution

    @classmethod
    def from_round(cls, round_: PracticeRound) -> PracticeRoundPublic:
        return cls(
            round_id=round_.round_id,
            asset_id=round_.asset_id,
            asset_attribution=round_.asset_attribution,
        )


class PracticeAnswerSubmission(ContractModel):
    country_code: str = Field(min_length=2, max_length=2)
    coordinate: Coordinate | None = None
    skipped: bool = False
    uncertain: bool = False


class PracticeReveal(ContractModel):
    round_id: str
    answer: SourceTruthAnswer


class UserCorrection(ContractModel):
    round_id: str = Field(min_length=1)
    country_code: str = Field(min_length=2, max_length=2)
    note: str = Field(min_length=1)
    origin: Literal[AnswerOrigin.USER_CORRECTION] = AnswerOrigin.USER_CORRECTION


class ImportedAnswer(ContractModel):
    round_id: str = Field(min_length=1)
    country_code: str = Field(min_length=2, max_length=2)
    import_reference: str = Field(min_length=1)
    origin: Literal[AnswerOrigin.IMPORTED] = AnswerOrigin.IMPORTED


class ModelPrediction(ContractModel):
    round_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    country_code: str = Field(min_length=2, max_length=2)
    confidence: float = Field(ge=0, le=1)
    origin: Literal[AnswerOrigin.MODEL_PREDICTION] = AnswerOrigin.MODEL_PREDICTION


class Feedback(ContractModel):
    round_id: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    note: str | None = Field(default=None, min_length=1)
    reported_issue: bool = False


class StudyProgress(ContractModel):
    lesson_id: str = Field(min_length=1)
    repetitions: int = Field(ge=0)
    interval_days: int = Field(ge=0)
    ease_factor: float = Field(ge=1.3)
    last_reviewed_on: date = Field(default_factory=date.today)

    @property
    def next_review_on(self) -> date:
        """Expose the simple schedule state without implementing SM-2 grading yet."""
        return self.last_reviewed_on + timedelta(days=self.interval_days)


class StudyGrade(ContractModel):
    lesson_id: str = Field(min_length=1)
    quality: int = Field(ge=0, le=5)
    reviewed_at: datetime


class ModelManifest(ContractModel):
    """Metadata for an optional local artifact; never a request to download one."""

    model_id: str = Field(min_length=1)
    artifact_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    runtime: Literal["onnx", "pytorch"]
    required_for_learning: Literal[False] = False


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    SHADOW = "shadow"
    PROMOTED = "promoted"
    REJECTED = "rejected"


class Experiment(ContractModel):
    experiment_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    status: ExperimentStatus
    answer_source: Literal[AnswerOrigin.SOURCE_TRUTH]


class PublicationError(ValueError):
    """Raised when an immutable pack is not eligible for activation/publication."""


class ContentPack(ContractModel):
    """An immutable content pack version; activation comes in a later task."""

    pack_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    created_at: datetime
    lessons: tuple[Lesson, ...]
    practice_rounds: tuple[PracticeRound, ...]

    def _attributions(self) -> tuple[Attribution, ...]:
        lesson_attributions: list[Attribution] = []
        for lesson in self.lessons:
            lesson_attributions.extend(lesson.citations)
            for quiz in lesson.quiz_items:
                lesson_attributions.extend(quiz.citations)
        round_attributions = tuple(
            attribution
            for round_ in self.practice_rounds
            for attribution in (round_.asset_attribution, *round_.answer.citations)
        )
        return (*lesson_attributions, *round_attributions)

    def is_publication_ready(self) -> bool:
        return all(item.rights_status is RightsStatus.CLEARED for item in self._attributions())

    def require_publication_ready(self) -> None:
        if not self.is_publication_ready():
            msg = "Only cleared content may be published or activated."
            raise PublicationError(msg)

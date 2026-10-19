"""Versioned domain contracts for offline Geo Companion content and study state."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, computed_field, model_validator


class ContractModel(BaseModel):
    """Strict, immutable API/domain value object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
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
    diagram_asset_id: str | None = None
    citations: tuple[Citation, ...] = Field(min_length=1)
    quiz_items: tuple[QuizItem, ...]


class Coordinate(ContractModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class SourceTruthAnswer(ContractModel):
    """Pack-authored ground truth; never derived from learner or model activity."""

    country_code: str = Field(min_length=2, max_length=2)
    coordinate: Coordinate | None = None
    explanation: str = Field(min_length=1)
    citations: tuple[Citation, ...] = Field(min_length=1)
    answer_origin: Literal[AnswerOrigin.SOURCE_TRUTH, AnswerOrigin.AUTHORED]


class PracticeRound(ContractModel):
    round_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    asset_attribution: Attribution
    asset_description: str = Field(
        default="Original educational practice diagram.",
        min_length=1,
        description="Accessible description of the visible evidence; must not name the answer.",
    )
    clue: str = Field(default="No authored clue is available for this round.", min_length=1)
    answer: SourceTruthAnswer


class PracticeRoundPublic(ContractModel):
    """Pre-submission contract deliberately omitting both answer and coordinates."""

    round_id: str
    asset_id: str
    asset_attribution: Attribution
    asset_description: str

    @classmethod
    def from_round(cls, round_: PracticeRound) -> PracticeRoundPublic:
        return cls(
            round_id=round_.round_id,
            asset_id=round_.asset_id,
            asset_attribution=round_.asset_attribution,
            asset_description=round_.asset_description,
        )


class PracticeClue(ContractModel):
    """An optional authored clue, distinct from the hidden answer."""

    round_id: str
    clue: str


class PracticeAnswerSubmission(ContractModel):
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    region_code: str | None = Field(default=None, min_length=1)
    coordinate: Coordinate | None = None
    skipped: bool = False
    uncertain: bool = False

    @model_validator(mode="after")
    def skip_and_guess_are_exclusive(self) -> PracticeAnswerSubmission:
        guess_fields = (self.country_code, self.region_code, self.coordinate)
        if self.skipped:
            if any(field is not None for field in guess_fields):
                msg = "Skipped practice answers cannot include country, region, or coordinates."
                raise ValueError(msg)
        elif self.country_code is None:
            msg = "Submitted practice answers require a country_code."
            raise ValueError(msg)
        return self


class PracticeReveal(ContractModel):
    round_id: str
    answer: SourceTruthAnswer


class PracticeAnswerResult(PracticeReveal):
    """Post-submission reveal with deterministic scoring and a local attempt identity."""

    attempt_id: str
    is_correct: bool
    submission: PracticeAnswerSubmission
    study_progress: StudyProgress | None = None


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


class ModelInfo(ContractModel):
    """Identity of the local prediction provider; learning never requires one."""

    model_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    runtime: Literal["dummy", "onnx", "pytorch"]
    is_placeholder: bool
    description: str = Field(min_length=1)
    required_for_learning: Literal[False] = False


class ModelStatus(ContractModel):
    """Which provider is enabled; ``active`` is null when the app runs without a model."""

    active: ModelInfo | None = None


class ModelCandidate(ContractModel):
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    confidence: float = Field(gt=0, le=1)


class ModelPredictionResult(ContractModel):
    """A post-answer model opinion for one attempt; never source truth and never a hint."""

    attempt_id: str = Field(min_length=1)
    round_id: str = Field(min_length=1)
    model: ModelInfo
    candidates: tuple[ModelCandidate, ...] = Field(max_length=5)
    abstained: bool
    origin: Literal[AnswerOrigin.MODEL_PREDICTION] = AnswerOrigin.MODEL_PREDICTION

    @model_validator(mode="after")
    def candidates_are_ranked_and_consistent(self) -> ModelPredictionResult:
        if self.abstained != (not self.candidates):
            msg = "A prediction abstains exactly when it has no candidates."
            raise ValueError(msg)
        confidences = [candidate.confidence for candidate in self.candidates]
        if confidences != sorted(confidences, reverse=True) or sum(confidences) > 1 + 1e-9:
            msg = "Candidates must be ordered by confidence and sum to at most 1."
            raise ValueError(msg)
        if len({candidate.country_code for candidate in self.candidates}) != len(confidences):
            msg = "Candidate countries must be distinct."
            raise ValueError(msg)
        return self


class Feedback(ContractModel):
    attempt_id: str = Field(min_length=1)
    round_id: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    note: str | None = Field(default=None, min_length=1)
    reported_issue: bool = False


class StudyProgress(ContractModel):
    """SM-2 review state for one practice round, derived only from local attempts."""

    round_id: str = Field(min_length=1)
    repetitions: int = Field(ge=0)
    interval_days: int = Field(ge=0)
    ease_factor: float = Field(ge=1.3)
    last_reviewed_on: date = Field(default_factory=date.today)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def next_review_on(self) -> date:
        """The due date the review queue is ordered by."""
        return self.last_reviewed_on + timedelta(days=self.interval_days)


class StudyReview(ContractModel):
    """The next local review; an empty queue is an expected clean-start state."""

    progress: StudyProgress | None = None


class ModelManifest(ContractModel):
    """Metadata for an optional local artifact; never a request to download one."""

    model_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    artifact_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    runtime: Literal["onnx", "pytorch"]
    required_for_learning: Literal[False] = False


class ModelArtifactReference(ContractModel):
    """Immutable identity used to bind experiments to an exact model artifact."""

    model_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    artifact_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @classmethod
    def from_manifest(cls, manifest: ModelManifest) -> ModelArtifactReference:
        return cls(
            model_id=manifest.model_id,
            version=manifest.version,
            artifact_hash=manifest.artifact_hash,
        )


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    SHADOW = "shadow"
    PROMOTED = "promoted"
    REJECTED = "rejected"


class Experiment(ContractModel):
    experiment_id: str = Field(min_length=1)
    model: ModelArtifactReference
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
        """An active pack requires every asset attribution and citation to be cleared.

        ``reference-only`` material may support research outside an active pack, but it can
        never make a pack publication-ready.
        """
        return all(item.rights_status is RightsStatus.CLEARED for item in self._attributions())

    def require_publication_ready(self) -> None:
        if not self.is_publication_ready():
            msg = "Only cleared content may be published or activated."
            raise PublicationError(msg)

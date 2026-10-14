"""FastAPI entrypoint for the loopback-only local service."""

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict

from geo_companion.contracts import (
    Feedback,
    PracticeAnswerResult,
    PracticeAnswerSubmission,
    PracticeClue,
    PracticeRoundPublic,
    StudyProgress,
    StudyReview,
)
from geo_companion.learning import LearningService
from geo_companion.paths import application_data_dir
from geo_companion.starter_pack import STARTER_PACK


# These small response models intentionally return no content until the Task 4 lifecycle exists.
class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PackSummary(ResponseModel):
    pack_id: str
    version: str
    content_hash: str


class PacksResponse(ResponseModel):
    packs: tuple[PackSummary, ...]


app = FastAPI(title="Geo Companion API", version="0.1.0")
learning_service: LearningService | None = None


def service() -> LearningService:
    """Open the local learner database lazily so schema/OpenAPI imports stay pure."""
    global learning_service
    if learning_service is None:
        learning_service = LearningService(application_data_dir() / "runtime.sqlite3")
    return learning_service


def round_not_found(round_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Practice round '{round_id}' was not found.",
    )


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    """Report that the local API process is accepting requests."""
    return {"status": "ok", "service": "geo-companion"}


@app.get("/api/v1/packs", response_model=PacksResponse)
async def list_packs() -> PacksResponse:
    """Expose the immutable bundled starter pack without a lifecycle/install flow."""
    return PacksResponse(
        packs=(
            PackSummary(
                pack_id=STARTER_PACK.pack_id,
                version=STARTER_PACK.version,
                content_hash=STARTER_PACK.content_hash,
            ),
        )
    )


@app.get("/api/v1/practice/rounds/next", response_model=PracticeRoundPublic)
async def next_practice_round() -> PracticeRoundPublic:
    """Serve an original diagram only; answers never leave this route before submission."""
    return service().next_round()


@app.get("/api/v1/practice/rounds/{round_id}", response_model=PracticeRoundPublic)
async def get_practice_round(round_id: str) -> PracticeRoundPublic:
    """Reopen one round's public payload, e.g. for a scheduled review; no answer is included."""
    try:
        return service().round_public(round_id)
    except KeyError as error:
        raise round_not_found(round_id) from error


@app.get("/api/v1/practice/rounds/{round_id}/clue", response_model=PracticeClue)
async def get_practice_clue(round_id: str) -> PracticeClue:
    """Reveal only the optional authored clue; this never releases the answer."""
    try:
        return service().clue(round_id)
    except KeyError as error:
        raise round_not_found(round_id) from error


@app.post("/api/v1/practice/rounds/{round_id}/answers", response_model=PracticeAnswerResult)
async def submit_practice_answer(
    round_id: str, submission: PracticeAnswerSubmission
) -> PracticeAnswerResult:
    """Persist the pseudonymous attempt and its review schedule, then reveal the answer."""
    try:
        return service().submit_practice(round_id, submission)
    except KeyError as error:
        raise round_not_found(round_id) from error


@app.post("/api/v1/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def submit_feedback(feedback: Feedback) -> None:
    """Persist local feedback; reports remain separate from verified source truth."""
    try:
        service().record_feedback(feedback)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The feedback attempt was not found for this learner.",
        ) from error


@app.get("/api/v1/study/progress/{round_id}", response_model=StudyProgress)
async def get_study_progress(round_id: str) -> StudyProgress:
    """Return persisted pseudonymous SM-2 state for one practice round."""
    try:
        return service().progress(round_id)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No study progress exists for round '{round_id}'.",
        ) from error


@app.get("/api/v1/study/review/next", response_model=StudyReview)
async def next_study_review() -> StudyReview:
    """Return the earliest-due local review without inventing one on clean start."""
    return service().next_review()

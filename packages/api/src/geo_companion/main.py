"""FastAPI entrypoint for the loopback-only local service."""
# ruff: noqa: E501

from datetime import UTC

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict

from geo_companion.contracts import (
    Feedback,
    LessonPublic,
    PracticeAnswerResult,
    PracticeAnswerSubmission,
    PracticeRoundPublic,
    QuizAnswerResult,
    QuizAnswerSubmission,
    StudyGrade,
    StudyProgress,
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


class LessonSummary(ResponseModel):
    lesson_id: str
    title: str


class LessonsResponse(ResponseModel):
    lessons: tuple[LessonSummary, ...]


app = FastAPI(title="Geo Companion API", version="0.1.0")
learning_service: LearningService | None = None


def service() -> LearningService:
    """Open the local learner database lazily so schema/OpenAPI imports stay pure."""
    global learning_service
    if learning_service is None:
        learning_service = LearningService(application_data_dir() / "runtime.sqlite3")
    return learning_service


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


@app.get("/api/v1/lessons", response_model=LessonsResponse)
async def list_lessons() -> LessonsResponse:
    """List the three original, cleared starter lessons."""
    return LessonsResponse(
        lessons=tuple(
            LessonSummary(lesson_id=item.lesson_id, title=item.title)
            for item in service().lessons()
        )
    )


@app.get("/api/v1/lessons/{lesson_id}", response_model=LessonPublic)
async def get_lesson(lesson_id: str) -> LessonPublic:
    """Return a safe lesson projection; its quiz key is not serialised."""
    try:
        return service().lesson_public(lesson_id)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Lesson '{lesson_id}' was not found."
        ) from error


@app.post("/api/v1/lessons/{lesson_id}/quizzes/{quiz_id}/answers", response_model=QuizAnswerResult)
async def submit_quiz_answer(
    lesson_id: str, quiz_id: str, submission: QuizAnswerSubmission
) -> QuizAnswerResult:
    """Check one deterministic quiz answer and release its cited explanation."""
    try:
        return service().answer_quiz(lesson_id, quiz_id, submission.selected_choice)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lesson or quiz was not found."
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error


@app.get("/api/v1/practice/rounds/next", response_model=PracticeRoundPublic)
async def next_practice_round() -> PracticeRoundPublic:
    """Serve an original diagram only; answers never leave this route before submission."""
    return service().next_round()


@app.post("/api/v1/practice/rounds/{round_id}/answers", response_model=PracticeAnswerResult)
async def submit_practice_answer(
    round_id: str, submission: PracticeAnswerSubmission
) -> PracticeAnswerResult:
    """Persist the pseudonymous attempt, then reveal independently sourced truth."""
    try:
        return service().submit_practice(round_id, submission)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Practice round '{round_id}' was not found.",
        ) from error


@app.post("/api/v1/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def submit_feedback(feedback: Feedback) -> None:
    """Persist local feedback; reports remain separate from verified source truth."""
    service().record_feedback(feedback)


@app.get("/api/v1/study/progress/{lesson_id}", response_model=StudyProgress)
async def get_study_progress(lesson_id: str) -> StudyProgress:
    """Return persisted pseudonymous SM-2 state for one lesson."""
    try:
        return service().progress(lesson_id)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No study progress exists for lesson '{lesson_id}'.",
        ) from error


@app.post("/api/v1/study/grades", response_model=StudyProgress)
async def record_study_grade(grade: StudyGrade) -> StudyProgress:
    """Apply standard SM-2 to the local review queue."""
    try:
        return service().grade_lesson(
            grade.lesson_id, grade.quality, grade.reviewed_at.astimezone(UTC)
        )
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lesson '{grade.lesson_id}' was not found.",
        ) from error

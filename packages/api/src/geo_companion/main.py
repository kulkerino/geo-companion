"""FastAPI entrypoint for the loopback-only local service."""

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict

from geo_companion.contracts import (
    Feedback,
    Lesson,
    PracticeAnswerSubmission,
    PracticeReveal,
    PracticeRoundPublic,
    StudyGrade,
    StudyProgress,
)


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


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    """Report that the local API process is accepting requests."""
    return {"status": "ok", "service": "geo-companion"}


@app.get("/api/v1/packs", response_model=PacksResponse)
def list_packs() -> PacksResponse:
    """List active packs; Task 4 will populate this from atomically activated storage."""
    return PacksResponse(packs=())


@app.get("/api/v1/lessons", response_model=LessonsResponse)
def list_lessons() -> LessonsResponse:
    """List lessons from active cleared packs; empty is safe before activation exists."""
    return LessonsResponse(lessons=())


@app.get("/api/v1/lessons/{lesson_id}", response_model=Lesson)
def get_lesson(lesson_id: str) -> Lesson:
    """Reserve the lesson detail contract without exposing unpublished content."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Lesson '{lesson_id}' was not found.",
    )


@app.get("/api/v1/practice/rounds/next", response_model=PracticeRoundPublic)
def next_practice_round() -> PracticeRoundPublic:
    """A pre-submit round would omit its answer; no activated round exists yet."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No active cleared practice round is available.",
    )


@app.post("/api/v1/practice/rounds/{round_id}/answers", response_model=PracticeReveal)
def submit_practice_answer(round_id: str, submission: PracticeAnswerSubmission) -> PracticeReveal:
    """Reserve post-submit reveal; Task 3 will grade and reveal verified source truth."""
    del submission
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Practice round '{round_id}' was not found.",
    )


@app.post("/api/v1/feedback", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def submit_feedback(feedback: Feedback) -> None:
    """Reject feedback until Task 3 adds local persistence rather than discarding it."""
    del feedback
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Feedback persistence is not implemented yet.",
    )


@app.get("/api/v1/study/progress/{lesson_id}", response_model=StudyProgress)
def get_study_progress(lesson_id: str) -> StudyProgress:
    """Expose a stable not-found contract before the learner scheduler is implemented."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No study progress exists for lesson '{lesson_id}'.",
    )


@app.post("/api/v1/study/grades", response_model=StudyProgress)
def record_study_grade(grade: StudyGrade) -> StudyProgress:
    """Reserve the SM-2 grade command without calculating a schedule in Task 2."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Lesson '{grade.lesson_id}' was not found.",
    )

"""FastAPI entrypoint for the loopback-only local service."""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from geo_companion.contracts import (
    PHOTO_UPLOAD_MAX_BYTES,
    PHOTO_UPLOAD_MEDIA_TYPES,
    Feedback,
    ModelPredictionResult,
    ModelStatus,
    PhotoGuessResult,
    PracticeAnswerResult,
    PracticeAnswerSubmission,
    PracticeClue,
    PracticeRoundPublic,
    StudyProgress,
    StudyReview,
)
from geo_companion.learning import LearningService, PracticePhotoError
from geo_companion.models import UnreadablePhotoError, provider_from_environment
from geo_companion.paths import application_data_dir
from geo_companion.photo_pack import PhotoPack, photo_pack_from_environment
from geo_companion.starter_pack import PRACTICE_ROUNDS, STARTER_PACK


# Pack responses list the bundled starter pack and the optional local photo pack until the
# Task 4 install lifecycle exists.
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
photo_pack: PhotoPack | None = None


def service() -> LearningService:
    """Open the local learner database lazily so schema/OpenAPI imports stay pure."""
    global learning_service, photo_pack
    if learning_service is None:
        photo_pack = photo_pack_from_environment()
        rounds = PRACTICE_ROUNDS if photo_pack is None else PRACTICE_ROUNDS + photo_pack.rounds
        learning_service = LearningService(
            application_data_dir() / "runtime.sqlite3",
            provider=provider_from_environment(images=photo_pack),
            rounds=rounds,
            practice_photo_hashes=frozenset() if photo_pack is None else photo_pack.asset_hashes,
        )
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
    """Expose the starter pack and any verified local photo pack, without an install flow."""
    service()
    packs = (STARTER_PACK,) if photo_pack is None else (STARTER_PACK, photo_pack.pack)
    return PacksResponse(
        packs=tuple(
            PackSummary(pack_id=pack.pack_id, version=pack.version, content_hash=pack.content_hash)
            for pack in packs
        )
    )


@app.get(
    "/api/v1/assets/{asset_id}",
    response_class=FileResponse,
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def get_photo_asset(asset_id: str) -> FileResponse:
    """Serve one verified photo of the local photo pack; its name reveals nothing."""
    service()
    path = None if photo_pack is None else photo_pack.asset_path(asset_id)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/v1/practice/rounds/next", response_model=PracticeRoundPublic)
async def next_practice_round() -> PracticeRoundPublic:
    """Serve the next diagram or photo round; answers never leave this route before submission."""
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


@app.get("/api/v1/models", response_model=ModelStatus)
async def model_status() -> ModelStatus:
    """Report the optional local model; ``active`` is null when none is enabled."""
    return service().model_status()


@app.get(
    "/api/v1/practice/attempts/{attempt_id}/model-prediction",
    response_model=ModelPredictionResult,
)
async def get_model_prediction(attempt_id: str) -> ModelPredictionResult:
    """Return the model's post-answer opinion; it requires an answered or skipped attempt."""
    try:
        return service().model_prediction(attempt_id)
    except LookupError as error:
        detail = (
            "The attempt was not found for this learner."
            if isinstance(error, KeyError)
            else str(error)
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from error


# The declared content type must match the upload's leading bytes.
def has_photo_signature(media_type: str, head: bytes) -> bool:
    if media_type == "image/jpeg":
        return head.startswith(b"\xff\xd8\xff")
    if media_type == "image/png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    return head[:4] == b"RIFF" and head[8:12] == b"WEBP"


async def read_photo_upload(request: Request) -> bytes:
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if media_type not in PHOTO_UPLOAD_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a JPEG, PNG or WebP photo.",
        )
    too_large = HTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail=f"The photo is larger than {PHOTO_UPLOAD_MAX_BYTES // (1024 * 1024)} MB.",
    )
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > PHOTO_UPLOAD_MAX_BYTES:
        raise too_large
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > PHOTO_UPLOAD_MAX_BYTES:
            raise too_large
    if not has_photo_signature(media_type, bytes(data[:12])):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The file is empty or is not the image type it claims to be.",
        )
    return bytes(data)


@app.post(
    "/api/v1/photo-guesses",
    response_model=PhotoGuessResult,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                media_type: {"schema": {"type": "string", "format": "binary"}}
                for media_type in PHOTO_UPLOAD_MEDIA_TYPES
            },
        }
    },
)
async def guess_photo(request: Request) -> PhotoGuessResult:
    """Ask the local model about the learner's own photo: a top-3 guess or an abstention.

    The photo is the raw request body. It is held in memory for this request only and is
    never written to disk or the database.
    """
    photo = await read_photo_upload(request)
    try:
        return service().photo_guess(photo)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except PracticePhotoError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except UnreadablePhotoError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
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

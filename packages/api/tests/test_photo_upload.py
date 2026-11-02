from __future__ import annotations

import asyncio
import hashlib
import io
import sqlite3
from pathlib import Path

import httpx
import pytest

# The dummy provider never decodes pixels, so a JPEG signature is enough for the API tests.
FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"learner photo" * 8
UPLOAD = "/api/v1/photo-guesses"


def upload(app: object, body: bytes, content_type: str = "image/jpeg") -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(UPLOAD, content=body, headers={"content-type": content_type})

    return asyncio.run(send())


@pytest.fixture
def main_with(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import geo_companion.main as main
    from geo_companion.learning import LearningService
    from geo_companion.models import DummyProvider

    def install(provider: object = DummyProvider(), hashes: frozenset[str] = frozenset()):
        service = LearningService(
            tmp_path / "runtime.sqlite3",
            provider=provider,
            practice_photo_hashes=hashes,
        )
        monkeypatch.setattr(main, "learning_service", service)
        return main.app, service

    return install


def test_dummy_photo_guess_is_deterministic_per_file_and_labelled() -> None:
    from geo_companion.models import DummyProvider

    provider = DummyProvider()
    photos = [FAKE_JPEG + bytes([index]) for index in range(20)]
    guesses = [provider.predict_photo(photo) for photo in photos]

    assert guesses == [DummyProvider().predict_photo(photo) for photo in photos]
    assert len(set(guesses)) > 1
    assert all(len(candidates) in {0, 3} for candidates in guesses)
    assert sum(1 for candidates in guesses if candidates) >= 5


def test_upload_returns_a_top_three_guess_and_stores_nothing(main_with) -> None:
    app, service = main_with()
    response = upload(app, FAKE_JPEG)

    assert response.status_code == 200
    body = response.json()
    assert body["model"]["model_id"] == "dummy-placeholder"
    assert body["model"]["is_placeholder"] is True
    assert body["origin"] == "model_prediction"
    assert body["abstained"] == (not body["candidates"])
    assert len(body["candidates"]) in {0, 3}
    assert upload(app, FAKE_JPEG).json() == body
    with sqlite3.connect(service.database_path) as connection:
        for table in ("learner_practice_attempts", "learner_model_predictions"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)


def test_upload_can_abstain(main_with) -> None:
    from geo_companion.models import DummyProvider

    class Unsure(DummyProvider):
        def predict_photo(self, photo: bytes) -> tuple[()]:
            return ()

    app, _ = main_with(Unsure())
    body = upload(app, FAKE_JPEG).json()

    assert body["abstained"] is True
    assert body["candidates"] == []


@pytest.mark.parametrize(
    ("body", "content_type", "status"),
    [
        (FAKE_JPEG, "text/plain", 415),
        (FAKE_JPEG, "image/gif", 415),
        (b"", "image/jpeg", 422),
        (b"<svg></svg>", "image/png", 422),
        (FAKE_JPEG, "image/webp", 422),
    ],
)
def test_upload_rejects_wrong_or_mislabelled_files(
    main_with, body: bytes, content_type: str, status: int
) -> None:
    app, _ = main_with()
    assert upload(app, body, content_type).status_code == status


def test_upload_rejects_files_over_the_size_limit(main_with) -> None:
    from geo_companion.contracts import PHOTO_UPLOAD_MAX_BYTES

    app, _ = main_with()
    response = upload(app, FAKE_JPEG + bytes(PHOTO_UPLOAD_MAX_BYTES))

    assert response.status_code == 413
    assert "MB" in response.json()["detail"]


def test_upload_without_a_model_is_unavailable(main_with) -> None:
    app, _ = main_with(None)
    response = upload(app, FAKE_JPEG)

    assert response.status_code == 404
    assert response.json()["detail"] == "No local model is enabled."


def test_practice_photos_cannot_be_uploaded_before_or_after_answering(main_with) -> None:
    # Otherwise a learner could ask the model about a photo round before answering it.
    practice = f"sha256:{hashlib.sha256(FAKE_JPEG).hexdigest()}"
    app, _ = main_with(hashes=frozenset({practice}))

    refused = upload(app, FAKE_JPEG)
    other = upload(app, FAKE_JPEG + b"edited")

    assert refused.status_code == 409
    assert "Compare with model" in refused.json()["detail"]
    assert other.status_code == 200


def test_openapi_declares_a_raw_photo_body() -> None:
    import geo_companion.main as main
    from geo_companion.contracts import PHOTO_UPLOAD_MEDIA_TYPES

    operation = main.app.openapi()["paths"][UPLOAD]["post"]
    content = operation["requestBody"]["content"]

    assert operation["requestBody"]["required"] is True
    assert tuple(content) == PHOTO_UPLOAD_MEDIA_TYPES
    assert all(media["schema"]["format"] == "binary" for media in content.values())
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PhotoGuessResult"
    }


def test_decoding_applies_orientation_and_refuses_bad_or_huge_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_module = pytest.importorskip("PIL.Image")
    import geo_companion.image_input as image_input

    rotated = image_module.new("RGB", (60, 40))
    exif = rotated.getexif()
    exif[0x0112] = 6  # EXIF orientation: rotate 90 degrees clockwise to display upright.
    encoded = io.BytesIO()
    rotated.save(encoded, format="JPEG", exif=exif)

    assert image_input.decode_upload(encoded.getvalue()).size == (40, 60)
    with pytest.raises(ValueError, match="decoded"):
        image_input.decode_upload(FAKE_JPEG)
    monkeypatch.setattr(image_input, "MAX_UPLOAD_PIXELS", 100)
    with pytest.raises(ValueError, match="megapixels"):
        image_input.decode_upload(encoded.getvalue())

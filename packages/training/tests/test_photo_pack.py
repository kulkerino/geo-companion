from __future__ import annotations

import asyncio
import csv
import json
from collections import Counter
from pathlib import Path

import httpx
import pytest
from conftest import write_ledger
from geo_companion.contracts import AssetKind, PracticeAnswerSubmission, PracticeRoundPublic
from geo_companion.learning import LearningService
from geo_companion.photo_pack import PhotoPack, PhotoPackError
from geo_training.cli import main
from geo_training.photo_pack import read_photo_records, select_photos
from PIL import Image

# Test-set-style rows: one large country, two smaller ones, one below the minimum count.
COUNTS = {"US": 30, "JP": 8, "KE": 6, "MC": 2}


def api(app: object, method: str, path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path)

    return asyncio.run(send())


def write_test_split(root: Path) -> tuple[Path, Path]:
    """Photos carrying EXIF GPS and a comment, with OSV-5M test column names."""
    images = root / "images"
    images.mkdir(parents=True)
    rows = []
    for country, count in COUNTS.items():
        for index in range(count):
            image_id = f"9{country}{index:03d}"
            exif = Image.Exif()
            exif[0x010E] = f"secret description {country}"  # ImageDescription
            exif[0x8825] = {1: "N", 2: (50.0, 5.0, 0.0)}  # GPSInfo
            Image.new("RGB", (64, 48), (index * 7 % 255, 90, 160)).save(
                images / f"{image_id}.jpg", exif=exif, comment=f"taken in {country}"
            )
            rows.append(
                {
                    "id": image_id,
                    "latitude": 10.5,
                    "longitude": -20.25,
                    "country": country,
                    "city": "Springfield",
                    "region": "Region",
                    "creator_username": f"mapper_{index}",
                }
            )
    metadata = root / "test.csv"
    with metadata.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return metadata, images


def build(tmp_path: Path, *extra: str, status: str = "cleared") -> int:
    metadata, images = write_test_split(tmp_path / "data")
    ledger = write_ledger(tmp_path / "ledger.json", status)
    return main(
        [
            "photo-pack", "--ledger", str(ledger), "--metadata", str(metadata),
            "--images", str(images), "--min-count", "5", "--out", str(tmp_path / "pack"), *extra,
        ]
    )  # fmt: skip


def test_selection_spreads_rounds_over_countries_and_hides_the_order(tmp_path: Path) -> None:
    metadata, images = write_test_split(tmp_path)
    records = read_photo_records(metadata, images)
    chosen = select_photos(records, rounds=12, min_count=5, seed=0)

    counts = Counter(photo.country for photo in chosen)
    assert counts == {"US": 4, "JP": 4, "KE": 4}  # MC has too few photos
    assert [photo.country for photo in chosen] != sorted(photo.country for photo in chosen)
    assert chosen == select_photos(records, rounds=12, min_count=5, seed=0)
    assert len(select_photos(records, rounds=100, min_count=5, seed=0)) == 44


def test_photo_pack_reveals_nothing_before_the_answer(tmp_path: Path) -> None:
    assert build(tmp_path, "--rounds", "9") == 0
    pack = PhotoPack(tmp_path / "pack" / "pack.json")
    assert len(pack.rounds) == 9
    assert pack.pack.is_publication_ready()

    for round_ in pack.rounds:
        public = PracticeRoundPublic.from_round(round_).model_dump_json()
        assert round_.asset_kind is AssetKind.PHOTO
        assert round_.answer.country_code not in round_.round_id.upper()
        for leak in ("mapper_", "Springfield", "10.5", round_.answer.country_code + '"', "9US"):
            assert leak not in public
        path = pack.asset_path(round_.asset_id)
        assert path is not None
        raw = path.read_bytes()
        assert b"secret" not in raw and b"taken in" not in raw
        with Image.open(path) as image:
            assert not image.getexif()
            assert "icc_profile" not in image.info and "comment" not in image.info
        citation = round_.answer.citations[0].attribution_text
        assert "mapper_" in citation and "Mapillary" in citation
        assert "Springfield" in round_.answer.explanation


def test_photo_pack_is_immutable_and_needs_a_cleared_ledger(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="cleared"):
        build(tmp_path / "a", status="quarantined")
    assert build(tmp_path / "b") == 0
    with pytest.raises(SystemExit, match="immutable"):
        main(
            [
                "photo-pack", "--ledger", str(tmp_path / "b" / "ledger.json"),
                "--metadata", str(tmp_path / "b" / "data" / "test.csv"),
                "--images", str(tmp_path / "b" / "data" / "images"),
                "--out", str(tmp_path / "b" / "pack"),
            ]
        )  # fmt: skip


def test_loading_refuses_a_tampered_photo_or_pack(tmp_path: Path) -> None:
    assert build(tmp_path, "--rounds", "3") == 0
    pack_file = tmp_path / "pack" / "pack.json"
    photo = next((tmp_path / "pack" / "assets").iterdir())
    original = photo.read_bytes()
    photo.write_bytes(original + b"\0")
    with pytest.raises(PhotoPackError, match="does not match"):
        PhotoPack(pack_file)
    photo.write_bytes(original)

    data = json.loads(pack_file.read_text())
    data["pack"]["practice_rounds"][0]["answer"]["country_code"] = "ZZ"
    pack_file.write_text(json.dumps(data))
    with pytest.raises(PhotoPackError, match="content hash"):
        PhotoPack(pack_file)


def test_photo_rounds_join_the_practice_loop(tmp_path: Path) -> None:
    from geo_companion.starter_pack import PRACTICE_ROUNDS

    assert build(tmp_path, "--rounds", "2") == 0
    pack = PhotoPack(tmp_path / "pack" / "pack.json")
    service = LearningService(tmp_path / "runtime.sqlite3", rounds=PRACTICE_ROUNDS + pack.rounds)

    last_starter = PRACTICE_ROUNDS[-1].round_id
    service.submit_practice(last_starter, PracticeAnswerSubmission(skipped=True))
    first_photo = service.next_round()
    assert first_photo.round_id == pack.rounds[0].round_id
    assert pack.image_path(first_photo) is not None
    truth = pack.rounds[0].answer.country_code
    result = service.submit_practice(
        first_photo.round_id, PracticeAnswerSubmission(country_code=truth)
    )
    assert result.is_correct
    assert service.progress(first_photo.round_id).repetitions == 1


def test_api_serves_only_listed_photos_of_the_loaded_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import geo_companion.main as main

    assert build(tmp_path, "--rounds", "2") == 0
    monkeypatch.setenv("GEO_COMPANION_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setenv("GEO_COMPANION_PHOTO_PACK", str(tmp_path / "pack" / "pack.json"))
    monkeypatch.setenv("GEO_COMPANION_MODEL", "none")
    monkeypatch.setattr(main, "learning_service", None)
    monkeypatch.setattr(main, "photo_pack", None)

    packs = api(main.app, "GET", "/api/v1/packs").json()["packs"]
    assert [pack["pack_id"] for pack in packs] == ["starter-original-diagrams", "osv5m-test-photos"]
    assert main.photo_pack is not None
    round_ = main.photo_pack.rounds[0]
    public = api(main.app, "GET", f"/api/v1/practice/rounds/{round_.round_id}").json()
    assert public["asset_kind"] == "photo" and "answer" not in public

    photo = api(main.app, "GET", f"/api/v1/assets/{round_.asset_id}")
    assert photo.status_code == 200
    assert photo.headers["content-type"] == "image/jpeg"
    assert photo.content == (tmp_path / "pack" / "assets" / round_.asset_id).read_bytes()
    for missing in ("place-panel-01.svg", "..%2Fpack.json", "unknown.jpg"):
        assert api(main.app, "GET", f"/api/v1/assets/{missing}").status_code == 404

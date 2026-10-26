"""Build a local photo pack of practice rounds from held-out OSV-5M test photos.

Nothing a learner sees before answering may give the answer away, so:

- round and asset ids are opaque hashes, and the rounds are shuffled, never sorted by country;
- each photo is decoded and re-encoded, which drops EXIF/XMP (GPS, capture time) and any
  other embedded metadata;
- the pre-answer attribution is the same generic dataset credit for every photo; the
  photographer, the place and the source image id are revealed only with the answer.

The test split is never used for training, so the model has not seen these photos either.
"""

from __future__ import annotations

import csv
import hashlib
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from geo_companion.contracts import (
    AnswerOrigin,
    AssetKind,
    Attribution,
    Citation,
    ContentPack,
    Coordinate,
    LocalPhotoPack,
    PackAsset,
    PracticeRound,
    SourceTruthAnswer,
)
from geo_companion.photo_pack import sha256_file
from geo_companion.starter_pack import content_hash
from PIL import Image, ImageOps

from geo_training.ledger import DatasetRecord

MAX_SIDE = 1280
JPEG_QUALITY = 88
CLUE = (
    "Look at what the photo shows: which side of the road traffic uses, the road markings, "
    "the signs and their script, the vegetation, and the architecture."
)
DESCRIPTION = "Street-level photo from the OpenStreetView-5M test set."
PRE_ANSWER_CREDIT = (
    "Photo from OpenStreetView-5M (Astruc et al., CVPR 2024) by a Mapillary contributor, "
    "CC BY-SA 4.0. The photographer is credited with the answer, so the credit cannot hint at "
    "the place."
)


@dataclass(frozen=True, slots=True)
class PhotoRecord:
    image_id: str
    image_path: Path
    country: str
    latitude: float
    longitude: float
    city: str
    region: str
    creator: str


def read_photo_records(csv_path: Path, image_dir: Path) -> list[PhotoRecord]:
    """Rows with a two-letter country code whose ``<id>.jpg`` exists under ``image_dir``."""
    records = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            country = (row.get("country") or "").strip().upper()
            image_path = image_dir / f"{row['id']}.jpg"
            if len(country) != 2 or not country.isalpha() or not image_path.is_file():
                continue
            records.append(
                PhotoRecord(
                    image_id=row["id"],
                    image_path=image_path,
                    country=country,
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    city=(row.get("city") or "").strip(),
                    region=(row.get("region") or "").strip(),
                    creator=(row.get("creator_username") or "").strip(),
                )
            )
    return records


def select_photos(
    records: list[PhotoRecord], rounds: int, min_count: int, seed: int
) -> list[PhotoRecord]:
    """Spread ``rounds`` photos evenly over countries with at least ``min_count`` photos.

    Countries take turns (round-robin over a seeded shuffle of each country's photos), so a
    pack is not three quarters US like the raw data. The result is shuffled again so the
    round order says nothing about the answer.
    """
    rng = random.Random(seed)
    by_country: dict[str, list[PhotoRecord]] = defaultdict(list)
    for record in sorted(records, key=lambda item: item.image_id):
        by_country[record.country].append(record)
    eligible = sorted(code for code, items in by_country.items() if len(items) >= min_count)
    for code in eligible:
        rng.shuffle(by_country[code])
    chosen: list[PhotoRecord] = []
    depth = 0
    while len(chosen) < rounds and any(len(by_country[code]) > depth for code in eligible):
        for code in eligible:
            if len(chosen) < rounds and len(by_country[code]) > depth:
                chosen.append(by_country[code][depth])
        depth += 1
    rng.shuffle(chosen)
    return chosen


def opaque_id(pack_id: str, seed: int, image_id: str) -> str:
    return hashlib.sha256(f"{pack_id}:{seed}:{image_id}".encode()).hexdigest()[:20]


def write_clean_jpeg(source: Path, destination: Path) -> None:
    """Re-encode without any metadata: no EXIF, XMP, ICC profile or comment is carried over."""
    with Image.open(source) as image:
        upright = ImageOps.exif_transpose(image).convert("RGB")
    upright.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    clean = Image.new("RGB", upright.size)
    clean.paste(upright)
    clean.save(destination, format="JPEG", quality=JPEG_QUALITY, optimize=True)


def _attribution(record: DatasetRecord, text: str, scope: str) -> Attribution:
    return Attribution(
        source_title=record.source_title,
        source_url=record.source_url,
        creator=record.creator,
        license_name=record.license_name,
        license_url=record.license_url,
        attribution_text=text,
        accessed_on=record.accessed_on,
        reviewed_on=record.reviewed_on,
        geographic_scope=scope,
        rights_status=record.rights_status,
    )


def _place(photo: PhotoRecord) -> str:
    parts = [part for part in (photo.city, photo.region) if part and part.lower() != "nan"]
    return ", ".join(parts)


def _round(
    record: DatasetRecord, photo: PhotoRecord, round_id: str, asset_id: str
) -> PracticeRound:
    place = _place(photo)
    where = f"{place} ({photo.country})" if place else photo.country
    photographer = photo.creator or "an unnamed Mapillary contributor"
    return PracticeRound(
        round_id=round_id,
        asset_id=asset_id,
        asset_kind=AssetKind.PHOTO,
        asset_attribution=_attribution(record, PRE_ANSWER_CREDIT, record.geographic_scope),
        asset_description=DESCRIPTION,
        clue=CLUE,
        answer=SourceTruthAnswer(
            country_code=photo.country,
            coordinate=Coordinate(latitude=photo.latitude, longitude=photo.longitude),
            explanation=(
                f"Source truth: the dataset records this photo at {where}, "
                f"{photo.latitude:.3f}, {photo.longitude:.3f}. The country comes from the "
                "photo's recorded location, not from anyone's reading of the scene, so "
                "compare what you noticed with what is typical there."
            ),
            citations=(
                Citation(
                    **_attribution(
                        record,
                        f"Photo by {photographer} on Mapillary (image {photo.image_id}), from "
                        f"OpenStreetView-5M (Astruc et al., CVPR 2024), {record.license_name}. "
                        "Resized and re-encoded without metadata.",
                        where,
                    ).model_dump()
                ),
            ),
            answer_origin=AnswerOrigin.SOURCE_TRUTH,
        ),
    )


def build_photo_pack(
    record: DatasetRecord,
    photos: list[PhotoRecord],
    out_dir: Path,
    *,
    pack_id: str,
    version: str,
    seed: int,
) -> LocalPhotoPack:
    """Write ``out_dir/pack.json`` and ``out_dir/assets/<opaque id>.jpg``."""
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    rounds = []
    assets = []
    for photo in photos:
        opaque = opaque_id(pack_id, seed, photo.image_id)
        asset_id = f"{opaque}.jpg"
        destination = assets_dir / asset_id
        write_clean_jpeg(photo.image_path, destination)
        assets.append(PackAsset(asset_id=asset_id, sha256=sha256_file(destination)))
        rounds.append(_round(record, photo, f"photo-{opaque}", asset_id))
    practice_rounds = tuple(rounds)
    local = LocalPhotoPack(
        pack=ContentPack(
            pack_id=pack_id,
            version=version,
            content_hash=content_hash(practice_rounds),
            created_at=datetime.now(UTC).replace(microsecond=0),
            lessons=(),
            practice_rounds=practice_rounds,
        ),
        source_dataset=record.dataset_id,
        assets=tuple(assets),
    )
    local.pack.require_publication_ready()
    (out_dir / "pack.json").write_text(local.model_dump_json(indent=2), encoding="utf-8")
    return local

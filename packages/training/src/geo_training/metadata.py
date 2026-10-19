"""Read dataset metadata (OSV-5M-style CSV) into labelled samples."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

REQUIRED_COLUMNS = ("id", "latitude", "longitude", "country")


@dataclass(frozen=True, slots=True)
class Sample:
    image_id: str
    image_path: Path
    latitude: float
    longitude: float
    country: str
    sequence: str | None


class MetadataError(ValueError):
    """Raised when a metadata file lacks a required column."""


def read_samples(csv_path: Path, image_dir: Path) -> Iterator[Sample]:
    """Yield samples whose image file exists; rows without a country code are skipped.

    OSV-5M stores images as ``<image_dir>/<id>.jpg``. Only images that are actually present
    are yielded, so a partial download (a few shards) gives a consistent subset.
    """
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or ())]
        if missing:
            msg = f"{csv_path.name} is missing columns: {', '.join(missing)}"
            raise MetadataError(msg)
        for row in reader:
            country = (row["country"] or "").strip().upper()
            if len(country) != 2 or not country.isalpha():
                continue
            image_path = image_dir / f"{row['id']}.jpg"
            if not image_path.is_file():
                continue
            yield Sample(
                image_id=row["id"],
                image_path=image_path,
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                country=country,
                sequence=(row.get("sequence") or None),
            )

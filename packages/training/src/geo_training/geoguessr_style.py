"""Import free GeoGuessr-style image sets from Hugging Face for private training.

OSV-5M photos are dashcam and phone shots; GeoGuessr shows Google Street View. These three
public sets look like the game:

- ``geoguessr``: marcelomoreno26/geoguessr, about 36k GeoGuessr screenshots (1536x662) labelled
  with English country names, in train / validation / test splits.
- ``pano``: stochastic/random_streetview_images_pano_v0.0.2, about 11k stitched Street View
  panoramas (about 3030x561) with ISO codes and coordinates. Each is cut into four views.
- ``sean``: 0xRafie/geosean11k, 11k Southeast Asian images (Street View, GeoGuessr and web),
  ISO codes in ``metadata.csv``.

Everything lands in one folder in the OSV-5M CSV format, so ``geo-train run`` and
``geo-train regrade`` read it unchanged::

    <root>/images/<id>.jpg
    <root>/metadata/train.csv       what models may train on
    <root>/metadata/benchmark.csv   the fixed GeoGuessr benchmark, never trained on

Only GeoGuessr countries are kept. The benchmark is the geoguessr set's own test split, every
panorama in 10% of 0.5-degree map cells (all four views of a spot stay together), and 10% of
the sean images. Byte-identical images are kept once, so a copy in two sets cannot sit on both
sides of the benchmark. None of these sets is cleared for showing in the app: they are for
private training only (see docs/sources/geoguessr-style.json).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import sys
import urllib.request
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geo_companion.geoguessr_countries import GEOGUESSR_COUNTRIES
from PIL import Image

from geo_training.fetch import RemoteFile, download, print_progress

HUB = "https://huggingface.co"
REPOS = {
    "geoguessr": "marcelomoreno26/geoguessr",
    "pano": "stochastic/random_streetview_images_pano_v0.0.2",
    "sean": "0xRafie/geosean11k",
}
COLUMNS = ("id", "latitude", "longitude", "country", "sequence", "source")
BENCHMARK_FRACTION = 0.1
PANO_CELL_DEGREES = 0.5
PANO_VIEWS = 4

# The English names the geoguessr set uses as labels.
COUNTRY_NAMES = {
    "Argentina": "AR", "Australia": "AU", "Austria": "AT", "Bangladesh": "BD", "Belgium": "BE",
    "Bolivia": "BO", "Botswana": "BW", "Brazil": "BR", "Bulgaria": "BG", "Cambodia": "KH",
    "Canada": "CA", "Chile": "CL", "Colombia": "CO", "Croatia": "HR", "Czechia": "CZ",
    "Czech Republic": "CZ", "Denmark": "DK", "Finland": "FI", "France": "FR", "Germany": "DE",
    "Ghana": "GH", "Greece": "GR", "Hungary": "HU", "India": "IN", "Indonesia": "ID",
    "Ireland": "IE", "Israel": "IL", "Italy": "IT", "Japan": "JP", "Kenya": "KE",
    "Latvia": "LV", "Lithuania": "LT", "Malaysia": "MY", "Mexico": "MX", "Netherlands": "NL",
    "New Zealand": "NZ", "Nigeria": "NG", "Norway": "NO", "Peru": "PE", "Philippines": "PH",
    "Poland": "PL", "Portugal": "PT", "Romania": "RO", "Russia": "RU", "Singapore": "SG",
    "Slovakia": "SK", "South Africa": "ZA", "South Korea": "KR", "Spain": "ES", "Sweden": "SE",
    "Switzerland": "CH", "Taiwan": "TW", "Thailand": "TH", "Turkey": "TR", "Ukraine": "UA",
    "United Kingdom": "GB", "United States": "US",
}  # fmt: skip


@dataclass(frozen=True)
class Row:
    """One image to write, before de-duplication."""

    image_id: str
    data: bytes
    country: str
    benchmark: bool
    latitude: float | None = None
    longitude: float | None = None
    sequence: str | None = None
    # What de-duplication compares: the image bytes, or for a cut view its panorama + position.
    dedupe_key: str | None = None


def in_benchmark(key: str, fraction: float = BENCHMARK_FRACTION) -> bool:
    digest = hashlib.sha256(f"geoguessr-benchmark:{key}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64 < fraction


def _short_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


# --- download -----------------------------------------------------------------------------


@dataclass(frozen=True)
class HubFile:
    path: str
    size: int
    sha256: str | None  # None for small files kept in Git rather than LFS


def list_hub_files(repo: str) -> list[HubFile]:
    url = f"{HUB}/api/datasets/{repo}/tree/main?recursive=true"
    with urllib.request.urlopen(url, timeout=60) as response:
        entries = json.load(response)
    return [
        HubFile(e["path"], int(e["size"]), (e.get("lfs") or {}).get("oid"))
        for e in entries
        if e.get("type") == "file"
    ]


def fetch_file(repo: str, file: HubFile, destination: Path, log_path: Path) -> Path:
    url = f"{HUB}/datasets/{repo}/resolve/main/{file.path}"
    if file.sha256:
        remote = RemoteFile(file.path, file.size, file.sha256)
        return download(remote, url, destination, log_path, print_progress)
    if destination.is_file() and destination.stat().st_size == file.size:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read()
    if len(data) != file.size:
        raise SystemExit(f"{repo}/{file.path}: got {len(data)} bytes, expected {file.size}.")
    destination.write_bytes(data)
    return destination


def wanted_files(name: str, files: Iterable[HubFile]) -> list[HubFile]:
    if name == "sean":
        return [f for f in files if f.path == "metadata.csv" or f.path.startswith("images/")]
    return [f for f in files if f.path.startswith("data/") and f.path.endswith(".parquet")]


# --- readers: raw files -> rows ------------------------------------------------------------


def _parquet_rows(path: Path, columns: list[str]) -> Iterator[dict[str, Any]]:
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    for batch in pq.ParquetFile(path).iter_batches(batch_size=64, columns=columns):
        yield from batch.to_pylist()


def read_geoguessr(raw: Path, skipped: Counter[str]) -> Iterator[Row]:
    for path in sorted((raw / "data").glob("*.parquet")):
        benchmark = path.name.startswith("test")
        for record in _parquet_rows(path, ["image", "label"]):
            country = COUNTRY_NAMES.get(str(record["label"]).strip())
            if country is None:
                skipped[f"unknown name {record['label']}"] += 1
                continue
            data = record["image"]["bytes"]
            image_id = f"gg-{_short_hash(data)}"
            yield Row(image_id, data, country, benchmark, sequence=image_id)


def cut_panorama(data: bytes, views: int = PANO_VIEWS) -> list[bytes]:
    """Split a stitched 360-degree strip into ``views`` side-by-side views."""
    with Image.open(io.BytesIO(data)) as image:
        rgb = image.convert("RGB")
    width = rgb.width // views
    out: list[bytes] = []
    for index in range(views):
        buffer = io.BytesIO()
        rgb.crop((index * width, 0, (index + 1) * width, rgb.height)).save(
            buffer, "JPEG", quality=92
        )
        out.append(buffer.getvalue())
    return out


def read_pano(raw: Path, skipped: Counter[str]) -> Iterator[Row]:
    columns = ["image", "country_iso_alpha2", "latitude", "longitude"]
    for path in sorted((raw / "data").glob("*.parquet")):
        for record in _parquet_rows(path, columns):
            country = str(record["country_iso_alpha2"] or "").strip().upper()
            try:
                latitude, longitude = float(record["latitude"]), float(record["longitude"])
            except (TypeError, ValueError):
                skipped["pano without coordinates"] += 1
                continue
            data = record["image"]["bytes"]
            spot = f"pano-{_short_hash(data)}"
            cell = (
                math.floor(latitude / PANO_CELL_DEGREES),
                math.floor(longitude / PANO_CELL_DEGREES),
            )
            benchmark = in_benchmark(f"cell:{cell[0]}:{cell[1]}")
            for index, view in enumerate(cut_panorama(data)):
                yield Row(
                    f"{spot}-{index}", view, country, benchmark, latitude, longitude, spot,
                    dedupe_key=f"{spot}-{index}",
                )


def read_sean(raw: Path, skipped: Counter[str]) -> Iterator[Row]:
    with (raw / "metadata.csv").open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            path = raw / record["file_name"]
            if not path.is_file():
                skipped["sean image missing"] += 1
                continue
            data = path.read_bytes()
            image_id = f"sean-{_short_hash(data)}"
            country = record["country_code"].strip().upper()
            yield Row(image_id, data, country, in_benchmark(image_id), sequence=image_id)


READERS = {"geoguessr": read_geoguessr, "pano": read_pano, "sean": read_sean}


# --- writer --------------------------------------------------------------------------------


def write_rows(
    rows: Iterable[tuple[str, Row]], root: Path, skipped: Counter[str]
) -> dict[str, Counter[str]]:
    """Write images and both CSVs; keep GeoGuessr countries and the first copy of each image."""
    images = root / "images"
    images.mkdir(parents=True, exist_ok=True)
    (root / "metadata").mkdir(exist_ok=True)
    seen: set[str] = set()
    counts: dict[str, Counter[str]] = {"train": Counter(), "benchmark": Counter()}
    with (
        (root / "metadata" / "train.csv").open("w", newline="", encoding="utf-8") as train,
        (root / "metadata" / "benchmark.csv").open("w", newline="", encoding="utf-8") as bench,
    ):
        writers = {"train": csv.writer(train), "benchmark": csv.writer(bench)}
        for writer in writers.values():
            writer.writerow(COLUMNS)
        for source, row in rows:
            if row.country not in GEOGUESSR_COUNTRIES:
                skipped[f"not in GeoGuessr: {row.country}"] += 1
                continue
            content = row.dedupe_key or hashlib.sha256(row.data).hexdigest()
            if content in seen:
                skipped["duplicate image"] += 1
                continue
            seen.add(content)
            target = images / f"{row.image_id}.jpg"
            if not target.is_file():
                target.write_bytes(row.data)
            split = "benchmark" if row.benchmark else "train"
            writers[split].writerow(
                (
                    row.image_id,
                    "" if row.latitude is None else f"{row.latitude:.6f}",
                    "" if row.longitude is None else f"{row.longitude:.6f}",
                    row.country,
                    row.sequence or row.image_id,
                    source,
                )
            )
            counts[split][row.country] += 1
    return counts


def import_sets(root: Path, names: list[str], *, offline: bool = False) -> dict[str, Any]:
    """Download (unless ``offline``) and convert the named sets into ``root``."""
    raw_root = root / "raw"
    if not offline:
        for name in names:
            repo = REPOS[name]
            files = wanted_files(name, list_hub_files(repo))
            total = sum(f.size for f in files)
            print(f"{repo}: {len(files)} files, {total / 1e9:.2f} GB", file=sys.stderr)
            for file in files:
                fetch_file(repo, file, raw_root / name / file.path, root / "fetch-log.jsonl")
    skipped: Counter[str] = Counter()

    def all_rows() -> Iterator[tuple[str, Row]]:
        for name in names:  # geoguessr first: its test split defines the benchmark copies
            for row in READERS[name](raw_root / name, skipped):
                yield name, row

    counts = write_rows(all_rows(), root, skipped)
    summary = {
        "data_dir": str(root),
        "train_images": sum(counts["train"].values()),
        "benchmark_images": sum(counts["benchmark"].values()),
        "countries": len(counts["train"] | counts["benchmark"]),
        "per_country": {
            code: {"train": counts["train"][code], "benchmark": counts["benchmark"][code]}
            for code in sorted(counts["train"] | counts["benchmark"])
        },
        "skipped": dict(skipped.most_common()),
    }
    (root / "import-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


__all__ = [
    "COUNTRY_NAMES",
    "REPOS",
    "Row",
    "cut_panorama",
    "import_sets",
    "in_benchmark",
    "read_geoguessr",
    "read_pano",
    "read_sean",
    "write_rows",
]

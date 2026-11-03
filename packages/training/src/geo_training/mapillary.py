"""Import Mapillary 360-degree panoramas near OSV-5M photo spots, cut like GeoGuessr views.

GeoGuessr shows a panorama at road level; OSV-5M has mostly forward-facing dashcam photos.
Mapillary (CC BY-SA 4.0, the same source as OSV-5M) also has panoramas, found through its
API with a free client token that kulo creates at mapillary.com/dashboard/developers.

For each GeoGuessr country the importer takes seed spots from the OSV-5M train metadata, reads
the Mapillary coverage tile around each seed, picks car-height panoramas within 1.5 km (one per
sequence, nearest first), downloads their 2048-pixel equirectangular thumbnails, keeps the
horizon band and cuts it into four views, as the ``pano`` GeoGuessr-style set does. Weak
countries get more seeds. Everything is resumable: each searched seed is logged and each
downloaded panorama kept, so a re-run picks up where it stopped. The output uses the OSV-5M
CSV format::

    <root>/raw/searched.jsonl        one line per searched seed, with the panoramas it chose
    <root>/raw/panos/<id>.jpg        downloaded thumbnails
    <root>/images/<id>.jpg           the cut views
    <root>/metadata/train.csv        what models may train on
    <root>/metadata/benchmark.csv    10% of 0.5-degree cells, never trained on
    <root>/metadata/attribution.csv  each panorama's Mapillary creator, for CC BY-SA credit

A panorama takes its seed's country, so a seed near a border can mislabel a few. The token
comes from ``MAPILLARY_TOKEN`` or ``~/geo-companion-secrets/mapillary-token.txt``, outside the
repository; it is never written to disk or logs.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from geo_companion.geoguessr_countries import GEOGUESSR_COUNTRIES
from PIL import Image

from geo_training.geoguessr_style import (
    PANO_CELL_DEGREES,
    PANO_VIEWS,
    Row,
    in_benchmark,
    write_rows,
)

GRAPH = "https://graph.mapillary.com"
FIELDS = "id,thumb_2048_url,computed_geometry,geometry,creator"
# Coverage tiles: the Graph API's image search almost never returns panoramas, but every point
# in these tiles says whether it is one. Zoom 14 tiles are about 2.4 km wide at the equator.
TILES = "https://tiles.mapillary.com/maps/vtp/mly1_public/2"
TILE_ZOOM = 14
MAX_KM = 1.5  # how far from its seed a panorama may be
HORIZON_BAND = (0.32, 0.68)  # rows kept of an equirectangular panorama, about +-33 degrees
PADDING_LIMIT = 0.15
# Countries the clip-c1 benchmark found weakest (2026-11-03): they get more seeds.
WEAK_COUNTRIES = ("HK", "VN", "LA", "SK", "PH")
TOKEN_PATH = Path("geo-companion-secrets") / "mapillary-token.txt"

GetJson = Callable[[str, str], dict[str, Any]]
GetTile = Callable[[str, str], bytes]
GetBytes = Callable[[str], bytes]


@dataclass(frozen=True)
class Seed:
    country: str
    latitude: float
    longitude: float

    @property
    def key(self) -> str:
        return f"{self.country}:{self.latitude:.5f}:{self.longitude:.5f}"


@dataclass(frozen=True)
class Pano:
    """One chosen panorama, as logged in ``searched.jsonl``."""

    image_id: str
    country: str
    latitude: float
    longitude: float
    sequence: str
    creator: str
    thumb_url: str


def read_token(home: Path) -> str:
    """The client token from ``MAPILLARY_TOKEN``, else from ``TOKEN_PATH`` under ``home``.

    The file sits in the home folder, not in application data: Windows can redirect a
    packaged app's AppData writes, so kulo would not find a file put there.
    """
    path = home / TOKEN_PATH
    found = os.environ.get("MAPILLARY_TOKEN", "").strip()
    if not found and path.is_file():
        found = path.read_text(encoding="utf-8-sig").strip()
    if not found:
        raise SystemExit(f"No Mapillary token: put the MLY| client token in {path}.")
    return found


# --- seeds ---------------------------------------------------------------------------------


def _rank(key: str) -> bytes:
    return hashlib.sha256(f"mapillary-seed:{key}".encode()).digest()


def choose_seeds(
    metadata: Path,
    per_country: int,
    weak: Iterable[str] = WEAK_COUNTRIES,
    weak_factor: int = 3,
    countries: Iterable[str] | None = None,
) -> list[Seed]:
    """Spread-out seed spots per GeoGuessr country: at most one per 0.1-degree cell.

    The choice depends only on the metadata, so a re-run picks the same seeds.
    """
    wanted = set(countries or GEOGUESSR_COUNTRIES) & GEOGUESSR_COUNTRIES
    cells: dict[str, dict[tuple[int, int], Seed]] = defaultdict(dict)
    with metadata.open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            country = record["country"].strip().upper()
            if country not in wanted:
                continue
            try:
                latitude, longitude = float(record["latitude"]), float(record["longitude"])
            except (TypeError, ValueError):
                continue
            cell = (math.floor(latitude * 10), math.floor(longitude * 10))
            seed = Seed(country, latitude, longitude)
            known = cells[country].get(cell)
            if known is None or _rank(seed.key) < _rank(known.key):
                cells[country][cell] = seed
    weak_set = set(weak)
    seeds: list[Seed] = []
    for country in sorted(cells):
        limit = per_country * (weak_factor if country in weak_set else 1)
        seeds += sorted(cells[country].values(), key=lambda s: _rank(s.key))[:limit]
    return seeds


# --- network -------------------------------------------------------------------------------


def _with_retries(action: Callable[[], Any], attempts: int = 5) -> Any:
    for attempt in range(attempts):
        try:
            return action()
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
        time.sleep(2**attempt)
    raise AssertionError("unreachable")


def http_get_json(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Authorization": f"OAuth {token}"})

    def go() -> dict[str, Any]:
        with urllib.request.urlopen(request, timeout=60) as response:
            result: dict[str, Any] = json.load(response)
            return result

    result: dict[str, Any] = _with_retries(go)
    return result


def http_get_bytes(url: str) -> bytes:
    def go() -> bytes:
        with urllib.request.urlopen(url, timeout=120) as response:
            data: bytes = response.read()
            return data

    data: bytes = _with_retries(go)
    return data


def http_get_tile(url: str, token: str) -> bytes:
    # The tile server takes the token only as a query parameter; this URL is never logged.
    return http_get_bytes(f"{url}?{urllib.parse.urlencode({'access_token': token})}")


# --- coverage tiles ------------------------------------------------------------------------


def tile_of(latitude: float, longitude: float, zoom: int = TILE_ZOOM) -> tuple[int, int]:
    n = 2**zoom
    x = int((longitude + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def tile_url(x: int, y: int, zoom: int = TILE_ZOOM) -> str:
    return f"{TILES}/{zoom}/{x}/{y}"


def _varint(data: bytes, pos: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, pos
        shift += 7


def _fields(data: bytes) -> Iterator[tuple[int, Any]]:
    """The (field number, value) pairs of one protobuf message."""
    pos = 0
    while pos < len(data):
        key, pos = _varint(data, pos)
        field, wire = key >> 3, key & 7
        value: Any
        if wire == 0:
            value, pos = _varint(data, pos)
        elif wire == 1:
            value, pos = data[pos : pos + 8], pos + 8
        elif wire == 2:
            size, pos = _varint(data, pos)
            value, pos = data[pos : pos + size], pos + size
        elif wire == 5:
            value, pos = data[pos : pos + 4], pos + 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")
        yield field, value


def _packed(data: bytes) -> list[int]:
    values: list[int] = []
    pos = 0
    while pos < len(data):
        value, pos = _varint(data, pos)
        values.append(value)
    return values


def _zigzag(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def _tile_value(data: bytes) -> Any:
    for field, value in _fields(data):
        if field == 1:
            return value.decode("utf-8")
        if field == 2:
            return struct.unpack("<f", value)[0]
        if field == 3:
            return struct.unpack("<d", value)[0]
        if field in (4, 5):
            return value
        if field == 6:
            return _zigzag(value)
        if field == 7:
            return bool(value)
    return None


def tile_points(data: bytes, x: int, y: int, zoom: int = TILE_ZOOM) -> list[dict[str, Any]]:
    """The point features of the ``image`` layer of a Mapbox vector tile, with coordinates.

    A minimal decoder, enough for Mapillary's coverage tiles, so no new dependency is needed.
    """
    n = 2**zoom
    points: list[dict[str, Any]] = []
    for field, layer in _fields(data):
        if field != 3:  # Tile.layers
            continue
        name, extent = "", 4096
        keys: list[str] = []
        values: list[Any] = []
        features: list[bytes] = []
        for layer_field, value in _fields(layer):
            if layer_field == 1:
                name = value.decode("utf-8")
            elif layer_field == 2:
                features.append(value)
            elif layer_field == 3:
                keys.append(value.decode("utf-8"))
            elif layer_field == 4:
                values.append(_tile_value(value))
            elif layer_field == 5:
                extent = value
        if name != "image":
            continue
        for feature in features:
            tags: list[int] = []
            geometry: list[int] = []
            for feature_field, value in _fields(feature):
                if feature_field == 2:
                    tags = _packed(value)
                elif feature_field == 4:
                    geometry = _packed(value)
            if len(geometry) < 3 or geometry[0] & 7 != 1:  # not a MoveTo, so not a point
                continue
            px, py = _zigzag(geometry[1]), _zigzag(geometry[2])
            longitude = (x + px / extent) / n * 360 - 180
            mercator = math.pi * (1 - 2 * (y + py / extent) / n)
            properties = {keys[k]: values[v] for k, v in zip(tags[::2], tags[1::2], strict=False)}
            properties["latitude"] = math.degrees(math.atan(math.sinh(mercator)))
            properties["longitude"] = longitude
            points.append(properties)
    return points


def _km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    dx = math.radians(b_lon - a_lon) * math.cos(math.radians((a_lat + b_lat) / 2))
    return 6371 * math.hypot(dx, math.radians(b_lat - a_lat))


def pano_points(seed: Seed, points: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Car-height panoramas (not on foot) within ``MAX_KM`` of the seed, nearest first."""
    near = [
        (_km(seed.latitude, seed.longitude, p["latitude"], p["longitude"]), p)
        for p in points
        if p.get("is_pano") and not p.get("foot")
    ]
    near.sort(key=lambda item: item[0])
    return [point for km, point in near if km <= MAX_KM]


def pick_panos(
    seed: Seed,
    points: list[dict[str, Any]],
    per_seed: int,
    get_entity: Callable[[str], dict[str, Any]],
) -> list[Pano]:
    """At most ``per_seed`` panoramas near the seed, each from a different sequence."""
    panos: list[Pano] = []
    sequences: set[str] = set()
    for point in pano_points(seed, points):
        sequence = str(point.get("sequence_id") or point["id"])
        if sequence in sequences:
            continue
        record = get_entity(str(point["id"]))
        url = record.get("thumb_2048_url")
        if not url:
            continue
        sequences.add(sequence)
        geometry = record.get("computed_geometry") or record.get("geometry") or {}
        longitude, latitude = geometry.get("coordinates") or (point["longitude"], point["latitude"])
        creator = (record.get("creator") or {}).get("username") or "unknown"
        panos.append(
            Pano(
                str(point["id"]), seed.country, float(latitude), float(longitude), sequence,
                str(creator), str(url),
            )
        )  # fmt: skip
        if len(panos) == per_seed:
            break
    return panos


# --- search and download -------------------------------------------------------------------


def read_searched(path: Path) -> dict[str, list[Pano]]:
    searched: dict[str, list[Pano]] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                searched[entry["seed"]] = [Pano(**pano) for pano in entry["panos"]]
    return searched


def fetch(
    root: Path,
    seeds: list[Seed],
    token: str,
    per_seed: int,
    get_json: GetJson = http_get_json,
    get_tile: GetTile = http_get_tile,
    get_bytes: GetBytes = http_get_bytes,
) -> list[Pano]:
    """Search every seed not yet searched and download every chosen panorama not yet here."""
    raw = root / "raw"
    (raw / "panos").mkdir(parents=True, exist_ok=True)
    log_path = raw / "searched.jsonl"
    searched = read_searched(log_path)
    todo = [seed for seed in seeds if seed.key not in searched]
    print(f"{len(seeds)} seeds, {len(todo)} still to search", file=sys.stderr)
    tiles: dict[tuple[int, int], list[dict[str, Any]]] = {}  # only each tile's panoramas
    taken = {pano.image_id for panos in searched.values() for pano in panos}

    def entity(image_id: str) -> dict[str, Any]:
        return get_json(f"{GRAPH}/{image_id}?fields={FIELDS}", token)

    with log_path.open("a", encoding="utf-8") as log:
        for index, seed in enumerate(todo, 1):
            tile = tile_of(seed.latitude, seed.longitude)
            if tile not in tiles:
                points = tile_points(get_tile(tile_url(*tile), token), *tile)
                tiles[tile] = [point for point in points if point.get("is_pano")]
            fresh = [point for point in tiles[tile] if str(point["id"]) not in taken]
            panos = pick_panos(seed, fresh, per_seed, entity)
            taken |= {pano.image_id for pano in panos}
            searched[seed.key] = panos
            log.write(json.dumps({"seed": seed.key, "panos": [asdict(p) for p in panos]}) + "\n")
            log.flush()
            for pano in panos:
                target = raw / "panos" / f"{pano.image_id}.jpg"
                if not target.is_file():
                    partial = target.with_suffix(".part")
                    partial.write_bytes(get_bytes(pano.thumb_url))
                    partial.replace(target)
            if index % 25 == 0:
                found = sum(len(searched[s.key]) for s in todo[:index])
                print(f"searched {index}/{len(todo)} seeds, {found} panoramas", file=sys.stderr)
    keys = {seed.key for seed in seeds}
    return [pano for key, panos in searched.items() if key in keys for pano in panos]


# --- convert -------------------------------------------------------------------------------


def horizon_views(data: bytes, views: int = PANO_VIEWS) -> list[bytes]:
    """Keep the horizon band of an equirectangular panorama and cut it into ``views``."""
    with Image.open(io.BytesIO(data)) as image:
        rgb = image.convert("RGB")
    top, bottom = (round(rgb.height * edge) for edge in HORIZON_BAND)
    # Partial panoramas are padded with pure white; reject one whose road half is mostly that.
    road = rgb.crop((0, rgb.height // 2, rgb.width, bottom)).convert("L").histogram()
    if sum(road[254:]) > PADDING_LIMIT * sum(road):
        raise ValueError("partial panorama")
    width = rgb.width // views
    out: list[bytes] = []
    for index in range(views):
        buffer = io.BytesIO()
        rgb.crop((index * width, top, (index + 1) * width, bottom)).save(buffer, "JPEG", quality=92)
        out.append(buffer.getvalue())
    return out


def pano_rows(root: Path, panos: Iterable[Pano], skipped: Counter[str]) -> Iterator[Row]:
    seen: set[str] = set()
    for pano in panos:
        path = root / "raw" / "panos" / f"{pano.image_id}.jpg"
        if pano.image_id in seen:
            continue
        seen.add(pano.image_id)
        if not path.is_file():
            skipped["panorama not downloaded"] += 1
            continue
        try:
            views = horizon_views(path.read_bytes())
        except OSError:
            skipped["unreadable panorama"] += 1
            continue
        except ValueError:
            skipped["partial panorama"] += 1
            continue
        cell = (
            math.floor(pano.latitude / PANO_CELL_DEGREES),
            math.floor(pano.longitude / PANO_CELL_DEGREES),
        )
        benchmark = in_benchmark(f"mapillary-cell:{cell[0]}:{cell[1]}")
        for index, view in enumerate(views):
            image_id = f"mly-{pano.image_id}-{index}"
            yield Row(
                image_id, view, pano.country, benchmark, pano.latitude, pano.longitude,
                f"mly-seq-{pano.sequence}", dedupe_key=image_id,
            )  # fmt: skip


def write_attribution(root: Path, panos: Iterable[Pano]) -> None:
    path = root / "metadata" / "attribution.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("mapillary_id", "creator_username", "url", "license"))
        for image_id, creator in sorted({(p.image_id, p.creator) for p in panos}):
            writer.writerow(
                (image_id, creator, f"https://www.mapillary.com/app/?pKey={image_id}",
                 "CC BY-SA 4.0")
            )  # fmt: skip


def import_mapillary(
    root: Path,
    seeds: list[Seed],
    token: str | None,
    per_seed: int = 2,
    *,
    get_json: GetJson = http_get_json,
    get_tile: GetTile = http_get_tile,
    get_bytes: GetBytes = http_get_bytes,
) -> dict[str, Any]:
    """Fetch (unless ``token`` is None) and convert into ``root``; returns a summary."""
    if token is None:
        keys = {seed.key for seed in seeds}
        searched = read_searched(root / "raw" / "searched.jsonl")
        panos = [p for key, found in searched.items() if key in keys for p in found]
    else:
        panos = fetch(root, seeds, token, per_seed, get_json, get_tile, get_bytes)
    skipped: Counter[str] = Counter()
    rows = (("mapillary", row) for row in pano_rows(root, panos, skipped))
    counts = write_rows(rows, root, skipped)
    write_attribution(root, panos)
    found = Counter(seed.country for seed in seeds)
    summary = {
        "data_dir": str(root),
        "seeds": len(seeds),
        "panoramas": len({p.image_id for p in panos}),
        "train_images": sum(counts["train"].values()),
        "benchmark_images": sum(counts["benchmark"].values()),
        "countries": len(counts["train"] | counts["benchmark"]),
        "per_country": {
            code: {
                "seeds": found[code],
                "train": counts["train"][code],
                "benchmark": counts["benchmark"][code],
            }
            for code in sorted(found)
        },
        "skipped": dict(skipped.most_common()),
    }
    (root / "import-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


__all__ = [
    "Pano",
    "Seed",
    "WEAK_COUNTRIES",
    "choose_seeds",
    "horizon_views",
    "import_mapillary",
    "pick_panos",
    "read_token",
    "tile_of",
    "tile_points",
]

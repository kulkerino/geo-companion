from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from typing import Any

import pytest
from geo_training.cli import main
from geo_training.mapillary import (
    TILE_ZOOM,
    Seed,
    choose_seeds,
    horizon_views,
    import_mapillary,
    pick_panos,
    read_token,
    tile_of,
    tile_points,
)
from geo_training.metadata import read_samples
from PIL import Image

# --- a tiny Mapbox vector tile writer, the inverse of the importer's decoder ----------------


def varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def message(field: int, payload: bytes) -> bytes:
    return varint(field << 3 | 2) + varint(len(payload)) + payload


def number(field: int, value: int) -> bytes:
    return varint(field << 3) + varint(value)


def zigzag(value: int) -> int:
    return (value << 1) ^ (value >> 63)


def encode_tile(points: list[dict[str, Any]], x: int, y: int, extent: int = 4096) -> bytes:
    """An ``image`` layer of point features at the given coordinates (and a decoy layer)."""
    keys: list[str] = []
    values: list[bytes] = []
    features = b""
    n = 2**TILE_ZOOM
    for point in points:
        tags: list[int] = []
        for key, value in point["properties"].items():
            if key not in keys:
                keys.append(key)
            if isinstance(value, bool):
                encoded = number(7, int(value))
            elif isinstance(value, int):
                encoded = number(4, value)
            else:
                encoded = message(1, str(value).encode())
            if encoded not in values:
                values.append(encoded)
            tags += [keys.index(key), values.index(encoded)]
        px = round(((point["lon"] + 180) / 360 * n - x) * extent)
        mercator = math.asinh(math.tan(math.radians(point["lat"])))
        py = round(((1 - mercator / math.pi) / 2 * n - y) * extent)
        geometry = b"".join(varint(v) for v in (9, zigzag(px), zigzag(py)))
        tag_bytes = b"".join(varint(t) for t in tags)
        features += message(2, number(3, 1) + message(2, tag_bytes) + message(4, geometry))
    layer = message(1, b"image") + features
    layer += b"".join(message(3, k.encode()) for k in keys)
    layer += b"".join(message(4, v) for v in values) + number(5, extent)
    return message(3, message(1, b"sequence")) + message(3, layer)


def equirect(noise: int, padded: bool = False) -> bytes:
    image = Image.new("RGB", (400, 200), (90, 90, 90))
    for x in range(8):
        image.putpixel((noise % 400, 100 + x), (255, noise % 256, 0))
    if padded:
        image.paste((255, 255, 255), (0, 100, 400, 200))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=95)
    return buffer.getvalue()


def write_seed_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [("JP", 35.0 + i * 0.2, 139.0) for i in range(5)]
    rows += [("JP", 35.001, 139.001)]  # same 0.1-degree cell as the first one
    rows += [("VN", 21.0 + i * 0.2, 105.8) for i in range(5)]
    rows += [("CN", 39.9, 116.4)]  # not a GeoGuessr country
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("id", "latitude", "longitude", "country"))
        for index, (country, lat, lon) in enumerate(rows):
            writer.writerow((index, lat, lon, country))
    return path


class FakeMapillary:
    """Serves coverage tiles with panoramas around each seed, entities and thumbnails."""

    def __init__(self, seeds: list[Seed]) -> None:
        self.seeds = seeds
        self.tiles = 0
        self.entities = 0
        self.downloads = 0
        self.tokens: set[str] = set()

    def get_tile(self, url: str, token: str) -> bytes:
        self.tiles += 1
        self.tokens.add(token)
        assert token not in url
        x, y = (int(part) for part in url.split("/")[-2:])
        here = [s for s in self.seeds if tile_of(s.latitude, s.longitude) == (x, y)]
        points = []
        for index, seed in enumerate(here):
            base = f"{index + 1}{abs(round(seed.latitude * 1000))}"
            # Two panoramas of one sequence, one of another, one on foot, one non-panorama,
            # and one panorama too far away.
            near = [
                (f"{base}1", 0.001, True, False, "a"),
                (f"{base}2", 0.002, True, False, "a"),
                (f"{base}3", 0.003, True, False, "b"),
                (f"{base}4", 0.001, True, True, "c"),
                (f"{base}5", 0.0005, False, False, "d"),
                (f"{base}6", 0.05, True, False, "e"),
            ]
            for image_id, offset, pano, foot, sequence in near:
                properties = {"id": int(image_id), "is_pano": pano, "foot": foot,
                              "sequence_id": f"{base}{sequence}"}  # fmt: skip
                points.append(
                    {"lat": seed.latitude + offset, "lon": seed.longitude, "properties": properties}
                )
        return encode_tile(points, x, y)

    def get_json(self, url: str, token: str) -> dict[str, Any]:
        self.entities += 1
        self.tokens.add(token)
        image_id = url.split("?")[0].rsplit("/", 1)[-1]
        return {
            "id": image_id,
            "thumb_2048_url": f"https://cdn.test/{image_id}.jpg",
            "creator": {"username": f"user{image_id[-1]}"},
        }

    def get_bytes(self, url: str) -> bytes:
        self.downloads += 1
        return equirect(len(url) * 7 + self.downloads)


def test_seeds_are_spread_out_boost_weak_countries_and_skip_others(tmp_path: Path) -> None:
    metadata = write_seed_csv(tmp_path / "train.csv")
    seeds = choose_seeds(metadata, per_country=2, weak=["VN"], weak_factor=2)
    counts = {c: sum(1 for s in seeds if s.country == c) for c in ("JP", "VN", "CN")}
    assert counts == {"JP": 2, "VN": 4, "CN": 0}
    assert choose_seeds(metadata, 2, ["VN"], 2) == seeds  # deterministic
    all_jp = choose_seeds(metadata, per_country=99, weak=[], countries=["JP"])
    assert len(all_jp) == 5  # the duplicate cell counts once


def test_tile_decoder_reads_points_back() -> None:
    x, y = tile_of(48.1486, 17.1077)
    properties = {"id": 42, "is_pano": True, "foot": False, "sequence_id": "s1"}
    data = encode_tile([{"lat": 48.15, "lon": 17.11, "properties": properties}], x, y)
    (point,) = tile_points(data, x, y)
    assert point["id"] == 42 and point["is_pano"] is True and point["sequence_id"] == "s1"
    assert point["latitude"] == pytest.approx(48.15, abs=1e-4)
    assert point["longitude"] == pytest.approx(17.11, abs=1e-4)


def test_pick_panos_takes_near_car_panoramas_one_per_sequence() -> None:
    seed = Seed("JP", 35.0, 139.0)
    fake = FakeMapillary([seed])
    x, y = tile_of(seed.latitude, seed.longitude)
    points = tile_points(fake.get_tile(f"https://tiles.test/14/{x}/{y}", "MLY|t"), x, y)
    panos = pick_panos(seed, points, 5, lambda image_id: fake.get_json(f"x/{image_id}", "MLY|t"))
    assert [p.image_id[-1] for p in panos] == ["1", "3"]  # nearest of sequence a, then b


def test_horizon_views_keep_the_middle_band_and_reject_padding() -> None:
    views = horizon_views(equirect(3))
    assert len(views) == 4
    with Image.open(io.BytesIO(views[0])) as view:
        assert view.size == (100, 72)
    with pytest.raises(ValueError, match="partial"):
        horizon_views(equirect(3, padded=True))


def test_import_is_resumable_and_writes_training_csvs(tmp_path: Path) -> None:
    seeds = choose_seeds(write_seed_csv(tmp_path / "train.csv"), 3, ["VN"], 1)
    root = tmp_path / "mapillary"
    fake = FakeMapillary(seeds)
    summary = import_mapillary(
        root, seeds, "MLY|test", 2,
        get_json=fake.get_json, get_tile=fake.get_tile, get_bytes=fake.get_bytes,
    )  # fmt: skip
    assert fake.tokens == {"MLY|test"}
    assert fake.downloads == 12 and summary["panoramas"] == 12
    assert summary["train_images"] + summary["benchmark_images"] == 48

    again = FakeMapillary(seeds)
    resumed = import_mapillary(
        root, seeds, "MLY|test", 2,
        get_json=again.get_json, get_tile=again.get_tile, get_bytes=again.get_bytes,
    )  # fmt: skip
    assert (again.tiles, again.entities, again.downloads) == (0, 0, 0)
    assert resumed["train_images"] == summary["train_images"]
    assert import_mapillary(root, seeds, None)["panoramas"] == 12  # offline rebuild

    samples = list(read_samples(root / "metadata" / "train.csv", root / "images"))
    assert samples and {s.country for s in samples} <= {"JP", "VN"}
    with (root / "metadata" / "attribution.csv").open(encoding="utf-8") as handle:
        credits = list(csv.DictReader(handle))
    assert len(credits) == 12 and all(c["license"] == "CC BY-SA 4.0" for c in credits)
    assert "MLY|test" not in (root / "raw" / "searched.jsonl").read_text(encoding="utf-8")


def test_token_comes_from_the_environment_or_the_home_secrets_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MAPILLARY_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="geo-companion-secrets"):
        read_token(tmp_path)
    (tmp_path / "geo-companion-secrets").mkdir()
    (tmp_path / "geo-companion-secrets" / "mapillary-token.txt").write_text(
        "﻿MLY|fromfile\n", encoding="utf-8"
    )
    assert read_token(tmp_path) == "MLY|fromfile"
    monkeypatch.setenv("MAPILLARY_TOKEN", "MLY|fromenv")
    assert read_token(tmp_path) == "MLY|fromenv"


def test_cli_offline_rebuild(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    seed_csv = write_seed_csv(tmp_path / "train.csv")
    root = tmp_path / "mapillary"
    seeds = choose_seeds(seed_csv, 3, ["VN"], 1)
    fake = FakeMapillary(seeds)
    import_mapillary(
        root, seeds, "MLY|x", 2,
        get_json=fake.get_json, get_tile=fake.get_tile, get_bytes=fake.get_bytes,
    )  # fmt: skip
    code = main(
        ["import-mapillary", "--data-dir", str(root), "--seed-metadata", str(seed_csv),
         "--seeds-per-country", "3", "--weak", "VN", "--weak-factor", "1", "--offline"]
    )  # fmt: skip
    assert code == 0
    assert json.loads(capsys.readouterr().out)["panoramas"] == 12


def test_extra_flags_must_come_in_matching_sets() -> None:
    args = ["run", "--ledger", "l", "--metadata", "m", "--images", "i"]
    extra = ["--extra-metadata", "a", "--extra-images", "b", "--extra-ledger", "c"]
    assert main([*args, *extra, "--extra-metadata", "d"]) == 2

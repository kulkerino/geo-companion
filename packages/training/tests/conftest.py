from __future__ import annotations

import csv
import importlib.util
import json
import random
from pathlib import Path

import pytest

# The training stack is the optional `training` group (CI installs it with --all-groups).
# Without it, skip these tests instead of failing the app's test run on import errors.
if importlib.util.find_spec("torch") is None:
    collect_ignore_glob = ["test_*.py"]

# Each synthetic "country" is a distinct colour with noise, so a tiny CNN can learn it fast.
SYNTHETIC_COUNTRIES = {"CZ": (200, 40, 40), "JP": (40, 200, 40), "BR": (40, 40, 200)}


def write_ledger(path: Path, status: str) -> Path:
    record = json.loads(
        (Path(__file__).resolve().parents[3] / "docs" / "sources" / "osv5m.json").read_text()
    )
    record["rights_status"] = status
    path.write_text(json.dumps(record))
    return path


def write_synthetic_split(root: Path, per_country: int, seed: int) -> tuple[Path, Path]:
    """Write ``<root>/images/<id>.jpg`` and ``<root>/metadata.csv`` (OSV-5M column names)."""
    from PIL import Image

    rng = random.Random(seed)
    images = root / "images"
    images.mkdir(parents=True)
    rows = []
    for country, colour in SYNTHETIC_COUNTRIES.items():
        for index in range(per_country):
            image_id = f"{seed}{country}{index:04d}"
            image = Image.new("RGB", (48, 40), colour)
            pixels = image.load()
            assert pixels is not None
            for _ in range(300):
                x, y = rng.randrange(48), rng.randrange(40)
                pixels[x, y] = tuple(rng.randrange(256) for _ in range(3))
            image.save(images / f"{image_id}.jpg")
            rows.append(
                {
                    "id": image_id,
                    "latitude": rng.uniform(-60, 60),
                    "longitude": rng.uniform(-180, 180),
                    "country": country,
                    "sequence": "",
                }
            )
    metadata = root / "metadata.csv"
    with metadata.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return metadata, images


@pytest.fixture
def cleared_ledger(tmp_path: Path) -> Path:
    return write_ledger(tmp_path / "ledger.json", "cleared")

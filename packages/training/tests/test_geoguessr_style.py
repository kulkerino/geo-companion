from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from conftest import write_ledger, write_synthetic_split
from geo_training.cli import main
from geo_training.geoguessr_style import COUNTRY_NAMES, cut_panorama, import_sets
from geo_training.metadata import read_samples
from geo_training.splits import split_train_val
from PIL import Image


def jpeg(colour: tuple[int, int, int], size: tuple[int, int] = (64, 32), noise: int = 0) -> bytes:
    image = Image.new("RGB", size, colour)
    # A noise-dependent bright block keeps each image's JPEG bytes unique.
    for x in range(8):
        for y in range(8):
            image.putpixel(((noise * 3 + x) % size[0], y), (255, (noise * 37) % 256, 255))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=95)
    return buffer.getvalue()


def write_parquet(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)


def build_raw(raw: Path) -> bytes:
    """A tiny copy of all three sets; returns one image that appears in two of them."""
    shared = jpeg((10, 200, 10), noise=999)
    write_parquet(
        raw / "geoguessr" / "data" / "train-00000-of-00001.parquet",
        [{"image": {"bytes": jpeg((200, 0, 0), noise=i), "path": f"j{i}.jpg"}, "label": "Japan"}
         for i in range(6)]
        + [{"image": {"bytes": jpeg((0, 0, 200), noise=i), "path": f"c{i}.jpg"}, "label": "China"}
           for i in range(2)]
        + [{"image": {"bytes": jpeg((0, 0, 200), noise=50), "path": "x.jpg"}, "label": "Narnia"}],
    )  # fmt: skip
    write_parquet(
        raw / "geoguessr" / "data" / "test-00000-of-00001.parquet",
        [{"image": {"bytes": shared, "path": "t.jpg"}, "label": "Thailand"}],
    )
    pano = jpeg((120, 120, 120), size=(400, 50), noise=3)
    write_parquet(
        raw / "pano" / "data" / "train-00000-of-00001-abc.parquet",
        [{"image": {"bytes": pano, "path": None}, "country_iso_alpha2": "PE",
          "latitude": "-11.72", "longitude": "-77.15", "address": "Panamericana Norte"},
         {"image": {"bytes": jpeg((1, 2, 3), size=(400, 50)), "path": None},
          "country_iso_alpha2": "AZ", "latitude": "40.4", "longitude": "49.8", "address": "Baku"}],
    )  # fmt: skip
    sean = raw / "sean"
    (sean / "images" / "TH").mkdir(parents=True)
    (sean / "images" / "MM").mkdir(parents=True)
    (sean / "images" / "TH" / "TH_text_001_aa.jpg").write_bytes(shared)  # same as geoguessr test
    (sean / "images" / "TH" / "TH_text_002_bb.jpg").write_bytes(jpeg((9, 9, 9), noise=4))
    (sean / "images" / "MM" / "MM_text_001_cc.jpg").write_bytes(jpeg((8, 8, 8), noise=5))
    with (sean / "metadata.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file_name", "image_id", "country_code", "text_presence",
                         "selection_rank", "content_sha256", "source"])  # fmt: skip
        for name, code, source in (
            ("TH/TH_text_001_aa.jpg", "TH", "geoguessr"),
            ("TH/TH_text_002_bb.jpg", "TH", "street_view"),
            ("MM/MM_text_001_cc.jpg", "MM", "street_view"),
        ):
            writer.writerow([f"images/{name}", name[3:8], code, "text", 1, "x", source])
    return shared


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_import_keeps_geoguessr_countries_once_and_holds_the_benchmark_out(tmp_path: Path) -> None:
    build_raw(tmp_path / "raw")

    summary = import_sets(tmp_path, ["geoguessr", "pano", "sean"], offline=True)

    train = rows(tmp_path / "metadata" / "train.csv")
    bench = rows(tmp_path / "metadata" / "benchmark.csv")
    countries = {row["country"] for row in train + bench}
    assert countries <= {"JP", "TH", "PE"}  # China, Narnia, Azerbaijan, Myanmar are dropped
    assert {r["country"] for r in train if r["source"] == "geoguessr"} == {"JP"}
    # The geoguessr test image is benchmark; its byte-identical copy in sean is dropped.
    assert [r["country"] for r in bench if r["source"] == "geoguessr"] == ["TH"]
    assert summary["skipped"]["duplicate image"] == 1
    assert summary["skipped"]["unknown name China"] == 2  # not a GeoGuessr country name
    assert summary["skipped"]["not in GeoGuessr: AZ"] == 4  # all four panorama views
    assert summary["skipped"]["not in GeoGuessr: MM"] == 1
    assert summary["skipped"]["unknown name Narnia"] == 1
    # A panorama becomes four views of one spot, all on the same side of the benchmark.
    pano = [r for r in train + bench if r["source"] == "pano"]
    assert len(pano) == 4 and len({r["sequence"] for r in pano}) == 1
    assert len({r in bench for r in pano}) == 1
    assert pano[0]["latitude"] == "-11.720000"
    for row in train + bench:
        assert (tmp_path / "images" / f"{row['id']}.jpg").is_file()
    assert json.loads((tmp_path / "import-summary.json").read_text())["train_images"] == len(train)

    # The training reader accepts rows without coordinates and splits them by sequence.
    samples = list(read_samples(tmp_path / "metadata" / "train.csv", tmp_path / "images"))
    assert len(samples) == len(train)
    split_train_val(samples, 0.5)


def test_cut_panorama_gives_four_equal_views() -> None:
    views = cut_panorama(jpeg((50, 60, 70), size=(400, 50)))
    sizes = [Image.open(io.BytesIO(view)).size for view in views]
    assert sizes == [(100, 50)] * 4


def test_every_country_name_maps_to_a_geoguessr_country() -> None:
    from geo_companion.geoguessr_countries import GEOGUESSR_COUNTRIES

    assert set(COUNTRY_NAMES.values()) <= GEOGUESSR_COUNTRIES
    assert COUNTRY_NAMES["Czechia"] == "CZ" and COUNTRY_NAMES["United Kingdom"] == "GB"


def test_cli_import_offline_and_refuses_unknown_sets(tmp_path: Path) -> None:
    build_raw(tmp_path / "data" / "raw")
    args = ["import-geoguessr-style", "--data-dir", str(tmp_path / "data"), "--offline"]
    assert main([*args, "--sets", "geoguessr"]) == 0
    assert rows(tmp_path / "data" / "metadata" / "benchmark.csv")
    with pytest.raises(SystemExit, match="Unknown sets"):
        main([*args, "--sets", "streetview-scraper"])


TINY = [
    "--image-size", "32", "--width", "8", "--epochs", "2", "--batch-size", "16",
    "--workers", "0", "--min-count", "5", "--val-fraction", "0.25", "--device", "cpu",
]  # fmt: skip


def test_fine_tune_with_an_extra_private_set_and_score_on_a_benchmark(
    tmp_path: Path, cleared_ledger: Path
) -> None:
    metadata, images = write_synthetic_split(tmp_path / "osv", per_country=30, seed=1)
    base = tmp_path / "base"
    common = ["run", "--ledger", str(cleared_ledger), "--metadata", str(metadata),
              "--images", str(images), *TINY]  # fmt: skip
    assert main([*common, "--out", str(base)]) == 0

    extra_metadata, extra_images = write_synthetic_split(tmp_path / "style", per_country=20, seed=3)
    private = write_ledger(tmp_path / "style.json", "reference-only")
    tuned = tmp_path / "tuned"
    extra = ["--extra-metadata", str(extra_metadata), "--extra-images", str(extra_images)]
    assert main([*common, *extra, "--extra-ledger", str(private),
                 "--init-from", str(base), "--out", str(tuned)]) == 0  # fmt: skip
    manifest = json.loads((tuned / "manifest.json").read_text())
    assert "privately" in manifest["dataset_attribution"]
    assert json.loads((tuned / "config.json").read_text())["init_from"] == str(base)

    bench_metadata, bench_images = write_synthetic_split(tmp_path / "bench", per_country=8, seed=5)
    score = ["regrade", "--run-dir", str(tuned), "--test-metadata", str(bench_metadata),
             "--test-images", str(bench_images), "--workers", "0", "--device", "cpu",
             "--out-name", "report-benchmark.json"]  # fmt: skip
    assert main(score) == 0
    report = json.loads((tuned / "report-benchmark.json").read_text())
    assert report["images"] == 24 and report["top1_all_images"] == report["top1"]

    quarantined = write_ledger(tmp_path / "bad.json", "quarantined")
    with pytest.raises(SystemExit, match="quarantined"):
        main([*common, *extra, "--extra-ledger", str(quarantined), "--out", str(tmp_path / "x")])
    assert main([*common, *extra, "--out", str(tmp_path / "y")]) == 2  # ledger missing

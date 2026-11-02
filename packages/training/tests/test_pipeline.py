from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnxruntime
import pytest
from conftest import SYNTHETIC_COUNTRIES, write_ledger, write_synthetic_split
from geo_training.cli import main
from geo_training.export import CountryModelManifest, sha256_file
from geo_training.preprocess import eval_array
from PIL import Image

TINY = [
    "--image-size", "32", "--width", "8", "--epochs", "4", "--batch-size", "16",
    "--workers", "0", "--min-count", "5", "--val-fraction", "0.25", "--device", "cpu",
]  # fmt: skip


def test_end_to_end_run_trains_calibrates_evaluates_and_exports(
    tmp_path: Path, cleared_ledger: Path
) -> None:
    metadata, images = write_synthetic_split(tmp_path / "train", per_country=40, seed=1)
    test_metadata, test_images = write_synthetic_split(tmp_path / "test", per_country=15, seed=2)
    out = tmp_path / "run"
    code = main(
        ["run", "--ledger", str(cleared_ledger), "--metadata", str(metadata),
         "--images", str(images), "--test-metadata", str(test_metadata),
         "--test-images", str(test_images), "--out", str(out), *TINY]  # fmt: skip
    )
    assert code == 0

    report = json.loads((out / "report.json").read_text())
    test = report["test"]
    assert test["images"] == 45 and test["classes"] == 3
    # The synthetic countries are trivially separable; the model must beat chance clearly.
    assert test["top1"] > 0.8 > test["baselines"]["uniform_top1"]
    assert set(test) >= {"top5", "ece_raw", "ece_calibrated", "temperature", "abstention"}
    assert len((out / "history.jsonl").read_text().splitlines()) == 4

    manifest = CountryModelManifest.model_validate_json((out / "manifest.json").read_text())
    assert manifest.artifact_hash == sha256_file(out / "model.onnx")
    assert manifest.runtime == "onnx" and manifest.required_for_learning is False
    assert manifest.classes == tuple(sorted(SYNTHETIC_COUNTRIES))
    assert manifest.trained_on == "osv5m" and manifest.dataset_license == "CC BY-SA 4.0"
    assert manifest.evaluation["top1"] == test["top1"]

    # The exported model, run with Pillow/NumPy preprocessing only, recognises a fresh image.
    session = onnxruntime.InferenceSession(str(out / "model.onnx"))
    image = Image.new("RGB", (48, 40), SYNTHETIC_COUNTRIES["JP"])
    (logits,) = session.run(["logits"], {"image": eval_array(image, 32)[None]})
    assert manifest.classes[int(np.argmax(logits))] == "JP"


def test_run_refuses_a_dataset_that_is_not_cleared(tmp_path: Path) -> None:
    metadata, images = write_synthetic_split(tmp_path / "train", per_country=5, seed=1)
    ledger = write_ledger(tmp_path / "ledger.json", "quarantined")
    with pytest.raises(PermissionError, match="only cleared"):
        main(["run", "--ledger", str(ledger), "--metadata", str(metadata), "--images",
              str(images), "--out", str(tmp_path / "run"), *TINY])  # fmt: skip
    assert not (tmp_path / "run").exists()


def test_run_refuses_to_write_inside_the_repository(tmp_path: Path, cleared_ledger: Path) -> None:
    metadata, images = write_synthetic_split(tmp_path / "train", per_country=5, seed=1)
    inside = Path(__file__).resolve().parents[3] / "runs" / "should-not-exist"
    with pytest.raises(SystemExit, match="inside the repository"):
        main(["run", "--ledger", str(cleared_ledger), "--metadata", str(metadata),
              "--images", str(images), "--out", str(inside), *TINY])  # fmt: skip
    assert not inside.exists()


def test_stats_summarises_the_local_dataset(
    tmp_path: Path, cleared_ledger: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    metadata, images = write_synthetic_split(tmp_path / "train", per_country=10, seed=1)
    assert main(["stats", "--ledger", str(cleared_ledger), "--metadata", str(metadata),
                 "--images", str(images), "--min-count", "5"]) == 0  # fmt: skip
    summary = json.loads(capsys.readouterr().out)
    assert summary["images"] == 30 and summary["countries"] == 3

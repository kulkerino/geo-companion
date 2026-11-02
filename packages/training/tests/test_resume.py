from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch
from conftest import write_synthetic_split
from geo_training.cli import main
from geo_training.metadata import read_samples
from geo_training.splits import select_classes, split_train_val
from geo_training.train import TrainConfig, train

CONFIG = TrainConfig(image_size=32, width=8, epochs=3, batch_size=16, num_workers=0, device="cpu")


def _samples(tmp_path: Path):  # type: ignore[no-untyped-def]
    metadata, images = write_synthetic_split(tmp_path / "data", per_country=20, seed=1)
    train_samples, val_samples = split_train_val(list(read_samples(metadata, images)), 0.25)
    return train_samples, val_samples, select_classes(train_samples, 5)


def test_a_run_paused_after_every_epoch_matches_an_uninterrupted_run(tmp_path: Path) -> None:
    train_samples, val_samples, classes = _samples(tmp_path)
    straight = train(train_samples, val_samples, classes, CONFIG, tmp_path / "straight")
    assert straight is not None
    assert not (tmp_path / "straight" / "last.pt").exists()

    out = tmp_path / "chunked"
    # A zero-hour budget stops after each epoch, so this takes three sessions.
    assert train(train_samples, val_samples, classes, CONFIG, out, max_hours=0) is None
    assert (out / "last.pt").exists()
    assert train(train_samples, val_samples, classes, CONFIG, out, resume=True, max_hours=0) is None
    chunked = train(train_samples, val_samples, classes, CONFIG, out, resume=True, max_hours=0)
    assert chunked is not None
    assert not (out / "last.pt").exists()

    def history(run: Path) -> list[dict[str, float]]:
        rows = [json.loads(line) for line in (run / "history.jsonl").read_text().splitlines()]
        return [{k: v for k, v in row.items() if k != "seconds"} for row in rows]

    assert history(out) == history(tmp_path / "straight")
    for name, tensor in straight.state_dict().items():
        assert torch.equal(tensor, chunked.state_dict()[name]), name


def test_resume_needs_an_unfinished_run(tmp_path: Path) -> None:
    train_samples, val_samples, classes = _samples(tmp_path)
    with pytest.raises(SystemExit, match="Nothing to resume"):
        train(train_samples, val_samples, classes, CONFIG, tmp_path / "run", resume=True)


def test_a_fresh_run_refuses_to_overwrite_an_unfinished_one(tmp_path: Path) -> None:
    train_samples, val_samples, classes = _samples(tmp_path)
    out = tmp_path / "run"
    train(train_samples, val_samples, classes, CONFIG, out, max_hours=0)
    with pytest.raises(SystemExit, match="--resume"):
        train(train_samples, val_samples, classes, CONFIG, out)


def test_resume_refuses_a_changed_configuration(tmp_path: Path) -> None:
    train_samples, val_samples, classes = _samples(tmp_path)
    out = tmp_path / "run"
    train(train_samples, val_samples, classes, CONFIG, out, max_hours=0)
    changed = TrainConfig(**{**CONFIG.__dict__, "learning_rate": 1e-3})
    with pytest.raises(SystemExit, match="learning_rate"):
        train(train_samples, val_samples, classes, changed, out, resume=True)
    # Workers and device may change between sessions.
    moved = TrainConfig(**{**CONFIG.__dict__, "num_workers": 1})
    assert train(train_samples, val_samples, classes, moved, out, resume=True, max_hours=0) is None


def test_cli_pauses_without_exporting_and_resumes_to_a_full_export(
    tmp_path: Path, cleared_ledger: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    metadata, images = write_synthetic_split(tmp_path / "train", per_country=20, seed=1)
    out = tmp_path / "run"
    args = [
        "run", "--ledger", str(cleared_ledger), "--metadata", str(metadata),
        "--images", str(images), "--out", str(out), "--image-size", "32", "--width", "8",
        "--epochs", "2", "--batch-size", "16", "--workers", "0", "--min-count", "5",
        "--val-fraction", "0.25", "--device", "cpu",
    ]  # fmt: skip
    assert main([*args, "--max-hours", "0"]) == 0
    assert "Paused after epoch 1 of 2" in capsys.readouterr().err
    assert not (out / "manifest.json").exists()
    assert main([*args, "--resume"]) == 0
    assert (out / "manifest.json").exists()
    assert len((out / "history.jsonl").read_text().splitlines()) == 2

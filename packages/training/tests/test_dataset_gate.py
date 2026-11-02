from __future__ import annotations

import csv
from pathlib import Path

import pytest
from conftest import write_ledger
from geo_companion.contracts import RightsStatus
from geo_training.ledger import DatasetNotClearedError, load_record, require_cleared
from geo_training.metadata import MetadataError, Sample, read_samples
from geo_training.splits import group_key, select_classes, split_train_val

REPO_LEDGER = Path(__file__).resolve().parents[3] / "docs" / "sources" / "osv5m.json"


def test_repository_ledger_is_complete_and_cleared() -> None:
    record = load_record(REPO_LEDGER)
    assert record.dataset_id == "osv5m"
    assert record.license_name == "CC BY-SA 4.0"
    assert "Mapillary" in record.attribution_text
    # kulo approved OSV-5M for training on 2026-10-19.
    assert record.rights_status is RightsStatus.CLEARED
    assert require_cleared(record) is record


@pytest.mark.parametrize("status", ["quarantined", "reference-only"])
def test_only_cleared_datasets_pass_the_gate(tmp_path: Path, status: str) -> None:
    with pytest.raises(DatasetNotClearedError):
        require_cleared(load_record(write_ledger(tmp_path / "l.json", status)))
    assert require_cleared(load_record(write_ledger(tmp_path / "c.json", "cleared")))


def _csv(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def test_metadata_requires_label_columns(tmp_path: Path) -> None:
    path = _csv(tmp_path / "m.csv", ["id", "latitude"], [["1", "0"]])
    with pytest.raises(MetadataError, match="longitude, country"):
        list(read_samples(path, tmp_path))


def test_metadata_keeps_only_present_images_with_valid_countries(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.jpg").write_bytes(b"x")
    path = _csv(
        tmp_path / "m.csv",
        ["id", "latitude", "longitude", "country", "sequence"],
        [
            ["a", "50.1", "14.4", "cz", "s1"],
            ["b", "0", "0", "", ""],  # no country
            ["c", "0", "0", "FR", ""],  # image not downloaded
        ],
    )
    samples = list(read_samples(path, tmp_path))
    assert [(s.image_id, s.country, s.sequence) for s in samples] == [("a", "CZ", "s1")]


def _sample(image_id: str, lat: float, lon: float, country: str, seq: str | None) -> Sample:
    return Sample(image_id, Path(f"{image_id}.jpg"), lat, lon, country, seq)


def test_split_is_deterministic_and_keeps_groups_together() -> None:
    samples = [
        _sample(f"{i}", (i % 40) * 0.5, (i % 37) * 0.5, "CZ", f"seq{i % 25}") for i in range(500)
    ]
    first = split_train_val(samples, 0.2)
    assert first == split_train_val(samples, 0.2)
    train_groups = {group_key(s) for s in first[0]}
    val_groups = {group_key(s) for s in first[1]}
    assert first[1] and train_groups.isdisjoint(val_groups)


def test_nearby_images_without_a_sequence_share_a_cell() -> None:
    a = _sample("a", 50.01, 14.41, "CZ", None)
    b = _sample("b", 50.04, 14.43, "CZ", None)
    c = _sample("c", 50.31, 14.43, "CZ", None)
    assert group_key(a) == group_key(b) != group_key(c)


def test_select_classes_applies_minimum_count() -> None:
    samples = [_sample(str(i), 0, 0, "CZ" if i < 5 else "JP", None) for i in range(7)]
    assert select_classes(samples, 3) == ("CZ",)
    assert select_classes(samples, 2) == ("CZ", "JP")


def test_deterministic_subset_is_stable_and_bounded() -> None:
    from geo_training.splits import deterministic_subset

    samples = [
        Sample(str(i), Path(f"{i}.jpg"), 0.0, 0.0, "CZ", None) for i in range(100)
    ]
    first = deterministic_subset(samples, 10)

    assert len(first) == 10
    assert first == deterministic_subset(list(reversed(samples)), 10)
    assert deterministic_subset(samples, None) == samples
    assert deterministic_subset(samples, 500) == samples

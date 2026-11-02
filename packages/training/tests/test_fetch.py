from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from geo_training.fetch import (
    FetchError,
    RemoteFile,
    download,
    extract_images,
    filter_metadata,
    parse_shards,
    shard_paths,
)


def published(path: Path, name: str) -> RemoteFile:
    data = path.read_bytes()
    return RemoteFile(name, len(data), hashlib.sha256(data).hexdigest())


def test_download_verifies_logs_and_skips_a_verified_file(tmp_path: Path) -> None:
    source = tmp_path / "source.zip"
    source.write_bytes(b"osv5m shard bytes" * 1000)
    remote = published(source, "images/train/00.zip")
    target = tmp_path / "data" / "raw" / remote.path
    log = tmp_path / "data" / "fetch-log.jsonl"

    download(remote, source.as_uri(), target, log)
    download(remote, source.as_uri(), target, log)

    assert target.read_bytes() == source.read_bytes()
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(entries) == 1
    assert entries[0]["sha256"] == remote.sha256
    assert entries[0]["size"] == remote.size
    assert not target.with_name("00.zip.part").exists()


def test_download_rejects_bytes_that_do_not_match_the_published_hash(tmp_path: Path) -> None:
    source = tmp_path / "source.zip"
    source.write_bytes(b"tampered")
    remote = RemoteFile("images/train/00.zip", 8, "0" * 64)
    target = tmp_path / "raw" / "00.zip"

    with pytest.raises(FetchError, match="expected"):
        download(remote, source.as_uri(), target, tmp_path / "log.jsonl")

    assert not target.exists()
    assert not target.with_name("00.zip.part").exists()
    assert not (tmp_path / "log.jsonl").exists()


def test_extract_flattens_images_and_filter_keeps_present_rows(tmp_path: Path) -> None:
    archive = tmp_path / "00.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("00/111.jpg", b"a")
        bundle.writestr("00/222.jpg", b"b")
        bundle.writestr("00/readme.txt", b"ignored")
    images = tmp_path / "images"

    assert extract_images(archive, images) == 2
    assert extract_images(archive, images) == 2  # idempotent
    assert sorted(p.name for p in images.iterdir()) == ["111.jpg", "222.jpg"]

    metadata = tmp_path / "train.csv"
    with metadata.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "latitude", "longitude", "country"])
        writer.writerows([["111", 1, 2, "CZ"], ["333", 3, 4, "JP"], ["222", 5, 6, "BR"]])
    filtered = tmp_path / "filtered.csv"

    assert filter_metadata(metadata, images, filtered) == 2
    assert [row["id"] for row in csv.DictReader(filtered.open())] == ["111", "222"]


def test_extract_refuses_unexpected_member_names(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../../evil.jpg", b"x")

    with pytest.raises(FetchError, match="unexpected member"):
        extract_images(archive, tmp_path / "images")


def test_shard_selection() -> None:
    assert parse_shards("0-2") == [0, 1, 2]
    assert parse_shards("5, 0-1") == [0, 1, 5]
    assert parse_shards("") == []
    assert shard_paths("test", [0, 4]) == ["images/test/00.zip", "images/test/04.zip"]


def test_fetch_command_unpacks_deletes_archives_and_does_not_refetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from conftest import write_ledger
    from geo_training import cli

    repository = tmp_path / "hub"
    files = repository / "resolve" / "main"
    (files / "images" / "train").mkdir(parents=True)
    with zipfile.ZipFile(files / "images" / "train" / "00.zip", "w") as bundle:
        bundle.writestr("00/111.jpg", b"a")
        bundle.writestr("00/222.jpg", b"b")
    (files / "train.csv").write_text("id,latitude,longitude,country\n111,1,2,CZ\n999,3,4,JP\n")
    remote = {
        name: published(files / name, name) for name in ("images/train/00.zip", "train.csv")
    }
    monkeypatch.setattr(cli, "list_remote_files", lambda base_url: remote)
    data = tmp_path / "data"
    argv = [
        "fetch", "--ledger", str(write_ledger(tmp_path / "ledger.json", "quarantined")),
        "--train-shards", "0", "--test-shards", "", "--data-dir", str(data),
        "--base-url", repository.as_uri(), "--delete-archives",
    ]  # fmt: skip

    assert cli.main(argv) == 0
    assert cli.main(argv) == 0

    assert sorted(p.name for p in (data / "images" / "train").iterdir()) == ["111.jpg", "222.jpg"]
    assert not (data / "raw" / "images" / "train" / "00.zip").exists()
    assert (data / "raw" / "images" / "train" / "00.zip.extracted.json").is_file()
    assert len((data / "fetch-log.jsonl").read_text().splitlines()) == 2
    assert (data / "metadata" / "train.csv").read_text().splitlines()[1:] == ["111,1,2,CZ"]

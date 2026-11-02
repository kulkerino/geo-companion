"""The one code path that downloads data: OSV-5M files from Hugging Face, run by hand.

Every file is checked against the SHA-256 that Hugging Face publishes for it (the Git LFS
object ID) and logged with its size and time in ``fetch-log.jsonl``. Downloads resume from a
``.part`` file. Nothing else in the project touches the network.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

OSV5M_BASE_URL = "https://huggingface.co/datasets/osv5m/osv5m"
CHUNK = 1 << 20


class FetchError(RuntimeError):
    """A download or extraction did not produce exactly the published file."""


@dataclass(frozen=True)
class RemoteFile:
    path: str
    size: int
    sha256: str


def list_remote_files(base_url: str = OSV5M_BASE_URL) -> dict[str, RemoteFile]:
    """Published files with their sizes and SHA-256 (LFS object IDs) from the Hub API."""
    api_url = base_url.replace("/datasets/", "/api/datasets/") + "/tree/main?recursive=true"
    with urllib.request.urlopen(api_url, timeout=60) as response:
        entries = json.load(response)
    return {
        entry["path"]: RemoteFile(entry["path"], int(entry["size"]), entry["lfs"]["oid"])
        for entry in entries
        if entry.get("type") == "file" and entry.get("lfs")
    }


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(
    remote: RemoteFile,
    url: str,
    destination: Path,
    log_path: Path,
    progress: Callable[[str, int, int], None] | None = None,
) -> Path:
    """Fetch ``url`` to ``destination`` unless it is already there and verified."""
    if destination.is_file() and destination.stat().st_size == remote.size:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    offset = partial.stat().st_size if partial.is_file() else 0
    request = urllib.request.Request(url)
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    with urllib.request.urlopen(request, timeout=120) as response:
        if offset and response.status != 206:
            offset = 0  # the server ignored the range; start again
        with partial.open("ab" if offset else "wb") as handle:
            written = offset
            for chunk in iter(lambda: response.read(CHUNK), b""):
                handle.write(chunk)
                written += len(chunk)
                if progress:
                    progress(remote.path, written, remote.size)
    actual_size = partial.stat().st_size
    actual_hash = sha256_of(partial)
    if actual_size != remote.size or actual_hash != remote.sha256:
        partial.unlink()
        msg = f"{remote.path}: got {actual_size} bytes, sha256 {actual_hash}; expected "
        raise FetchError(msg + f"{remote.size} bytes, sha256 {remote.sha256}.")
    partial.replace(destination)
    entry = {
        "path": remote.path,
        "url": url,
        "size": remote.size,
        "sha256": remote.sha256,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    with log_path.open("a", encoding="utf-8") as log:
        log.write(json.dumps(entry) + "\n")
    return destination


def extract_images(archive: Path, image_dir: Path) -> int:
    """Unpack every ``.jpg`` flat into ``image_dir`` as ``<id>.jpg``; returns the count."""
    image_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            name = Path(member.filename).name
            if member.is_dir() or not name.lower().endswith(".jpg"):
                continue
            stem = name[: -len(".jpg")]
            if not stem.isdigit():
                raise FetchError(f"{archive.name}: unexpected member {member.filename!r}")
            target = image_dir / f"{stem}.jpg"
            if not (target.is_file() and target.stat().st_size == member.file_size):
                with bundle.open(member) as source, target.open("wb") as sink:
                    shutil.copyfileobj(source, sink, CHUNK)
            count += 1
    return count


def filter_metadata(source: Path, image_dir: Path, destination: Path) -> int:
    """Keep only the rows whose image is present, so later reads skip the full 5M-row CSV."""
    present = {path.stem for path in image_dir.glob("*.jpg")}
    kept = 0
    with source.open(newline="", encoding="utf-8") as reader_handle:
        reader = csv.DictReader(reader_handle)
        temporary = destination.with_name(destination.name + ".part")
        with temporary.open("w", newline="", encoding="utf-8") as writer_handle:
            writer = csv.DictWriter(writer_handle, fieldnames=list(reader.fieldnames or ()))
            writer.writeheader()
            for row in reader:
                if row["id"] in present:
                    writer.writerow(row)
                    kept += 1
    temporary.replace(destination)
    return kept


def shard_paths(split: str, shards: Iterable[int]) -> list[str]:
    return [f"images/{split}/{shard:02d}.zip" for shard in shards]


def parse_shards(value: str) -> list[int]:
    """``"0-2"`` → [0, 1, 2]; ``"0,5"`` → [0, 5]; ``""`` → []."""
    shards: list[int] = []
    for part in filter(None, (piece.strip() for piece in value.split(","))):
        start, _, end = part.partition("-")
        shards.extend(range(int(start), int(end or start) + 1))
    return sorted(set(shards))


def print_progress(path: str, written: int, total: int) -> None:
    if written == total or written % (256 * CHUNK) < CHUNK:
        print(f"\r{path}: {written / 1e9:.2f} / {total / 1e9:.2f} GB", end="", file=sys.stderr)
        if written == total:
            print(file=sys.stderr)

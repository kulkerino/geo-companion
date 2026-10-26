"""Optional local photo pack: real photo rounds built by ``geo-train photo-pack``.

The pack lives in application data, never in this repository, and is loaded only when
``GEO_COMPANION_PHOTO_PACK=<pack.json>`` asks for it. Loading is the validation step: the
content hash, the rights of every attribution and citation, and the SHA-256 of every image
must all check out, or the app refuses to start rather than show unverified content.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from geo_companion.contracts import LocalPhotoPack, PracticeRound, PracticeRoundPublic
from geo_companion.paths import is_inside_repository
from geo_companion.starter_pack import content_hash

PHOTO_PACK_ENVIRONMENT_VARIABLE = "GEO_COMPANION_PHOTO_PACK"


class PhotoPackError(RuntimeError):
    """The photo pack cannot be trusted, so the app refuses to load it."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


class PhotoPack:
    """A verified local photo pack; it also shows the ONNX provider each round's photo."""

    def __init__(self, pack_path: Path) -> None:
        pack_path = pack_path.resolve()
        if is_inside_repository(pack_path):
            raise PhotoPackError("Photo packs must live outside the repository.")
        try:
            local = LocalPhotoPack.model_validate_json(pack_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise PhotoPackError(f"Cannot read photo pack {pack_path}.") from error
        pack = local.pack
        if content_hash(pack.practice_rounds) != pack.content_hash:
            raise PhotoPackError(f"Photo pack {pack_path} does not match its content hash.")
        if not pack.is_publication_ready():
            raise PhotoPackError(f"Photo pack {pack_path} contains content that is not cleared.")
        asset_dir = pack_path.parent / "assets"
        self._paths: dict[str, Path] = {}
        for asset in local.assets:
            path = asset_dir / asset.asset_id
            if not path.is_file() or sha256_file(path) != asset.sha256:
                raise PhotoPackError(f"Photo {path} is missing or does not match the pack.")
            self._paths[asset.asset_id] = path
        self.pack = pack
        self.rounds: tuple[PracticeRound, ...] = pack.practice_rounds

    def asset_path(self, asset_id: str) -> Path | None:
        return self._paths.get(asset_id)

    def image_path(self, round_: PracticeRoundPublic) -> Path | None:
        return self.asset_path(round_.asset_id)


def photo_pack_from_environment() -> PhotoPack | None:
    raw = os.environ.get(PHOTO_PACK_ENVIRONMENT_VARIABLE, "").strip()
    return PhotoPack(Path(raw).expanduser()) if raw else None

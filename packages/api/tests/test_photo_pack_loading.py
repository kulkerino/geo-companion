from __future__ import annotations

import json
from pathlib import Path

import pytest
from geo_companion.contracts import (
    AnswerOrigin,
    AssetKind,
    Citation,
    ContentPack,
    LocalPhotoPack,
    PackAsset,
    PracticeRound,
    SourceTruthAnswer,
)
from geo_companion.photo_pack import PhotoPack, PhotoPackError, sha256_file
from geo_companion.starter_pack import PRACTICE_ROUNDS, content_hash

# The photo loader never decodes images, so placeholder bytes stand in for a JPEG here; the
# builder and real photos are tested with the training group in test_photo_pack.py.
ATTRIBUTION = PRACTICE_ROUNDS[0].asset_attribution


def write_pack(root: Path, rights: str = "cleared") -> Path:
    (root / "assets").mkdir(parents=True)
    asset = root / "assets" / "0a1b2c.jpg"
    asset.write_bytes(b"not really a jpeg")
    attribution = json.loads(ATTRIBUTION.model_dump_json()) | {"rights_status": rights}
    round_ = PracticeRound(
        round_id="photo-0a1b2c",
        asset_id=asset.name,
        asset_kind=AssetKind.PHOTO,
        asset_attribution=attribution,
        answer=SourceTruthAnswer(
            country_code="JP",
            explanation="Source truth.",
            citations=(Citation(**attribution),),
            answer_origin=AnswerOrigin.SOURCE_TRUTH,
        ),
    )
    pack = LocalPhotoPack(
        pack=ContentPack(
            pack_id="photos",
            version="1.0.0",
            content_hash=content_hash((round_,)),
            created_at="2026-10-26T00:00:00Z",
            lessons=(),
            practice_rounds=(round_,),
        ),
        source_dataset="osv5m",
        assets=(PackAsset(asset_id=asset.name, sha256=sha256_file(asset)),),
    )
    path = root / "pack.json"
    path.write_text(pack.model_dump_json())
    return path


def test_a_verified_pack_loads(tmp_path: Path) -> None:
    pack = PhotoPack(write_pack(tmp_path))
    assert [round_.round_id for round_ in pack.rounds] == ["photo-0a1b2c"]
    assert pack.asset_path("0a1b2c.jpg") == tmp_path.resolve() / "assets" / "0a1b2c.jpg"
    assert pack.asset_path("../pack.json") is None


def test_a_pack_with_uncleared_content_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PhotoPackError, match="not cleared"):
        PhotoPack(write_pack(tmp_path, rights="quarantined"))


def test_a_pack_inside_the_repository_is_refused() -> None:
    inside = Path(__file__).resolve().parent / "fixtures" / "pack.json"
    with pytest.raises(PhotoPackError, match="outside the repository"):
        PhotoPack(inside)


def test_photo_rounds_must_each_list_one_asset(tmp_path: Path) -> None:
    data = json.loads(write_pack(tmp_path).read_text())
    data["assets"] = []
    with pytest.raises(ValueError):
        LocalPhotoPack.model_validate(data)
    data = json.loads((tmp_path / "pack.json").read_text())
    data["pack"]["practice_rounds"][0]["asset_kind"] = "diagram"
    with pytest.raises(ValueError, match="photo rounds only"):
        LocalPhotoPack.model_validate(data)

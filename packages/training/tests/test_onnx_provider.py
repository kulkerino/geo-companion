from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch
from conftest import write_ledger
from geo_companion.contracts import PracticeAnswerSubmission, PracticeRoundPublic
from geo_companion.learning import LearningService
from geo_companion.models import provider_from_environment
from geo_companion.onnx_provider import ModelIntegrityError, OnnxCountryProvider
from geo_training.export import export_onnx, write_manifest
from geo_training.ledger import load_record
from geo_training.model import CountryNet
from geo_training.preprocess import eval_array
from PIL import Image

CLASSES = ("BR", "CZ", "JP", "KE")
SIZE = 32
FIRST_ROUND = "starter-place-01"


def export_tiny_model(tmp_path: Path, abstain_below: float = 0.0) -> tuple[Path, CountryNet]:
    torch.manual_seed(0)
    model = CountryNet(len(CLASSES), width=8).eval()
    artifact = tmp_path / "model.onnx"
    assert export_onnx(model, SIZE, artifact) < 1e-3
    record = load_record(write_ledger(tmp_path / "ledger.json", "cleared"))
    manifest = tmp_path / "manifest.json"
    write_manifest(
        model_id="country-net-test",
        version="0.0.1",
        artifact=artifact,
        classes=CLASSES,
        input_size=SIZE,
        temperature=1.5,
        abstain_below=abstain_below,
        dataset=record,
        evaluation={"top1": 0.0},
        path=manifest,
    )
    return manifest, model


def write_photo(path: Path) -> Path:
    image = Image.new("RGB", (60, 40))
    for x in range(60):
        for y in range(40):
            image.putpixel((x, y), (x * 4, y * 6, (x + y) * 2))
    image.save(path)
    return path


class OnePhoto:
    def __init__(self, path: Path) -> None:
        self.path = path

    def image_path(self, round_: PracticeRoundPublic) -> Path | None:
        return self.path


def test_provider_matches_pytorch_with_temperature_and_labels_itself(tmp_path: Path) -> None:
    manifest, model = export_tiny_model(tmp_path)
    photo = write_photo(tmp_path / "photo.png")
    provider = OnnxCountryProvider(manifest)

    candidates = provider.predict_image(photo)

    with torch.no_grad():
        logits = model(torch.from_numpy(eval_array(Image.open(photo).convert("RGB"), SIZE))[None])
    expected = (logits[0] / 1.5).softmax(0)
    ranked = expected.argsort(descending=True)[:3]
    assert [c.country_code for c in candidates] == [CLASSES[int(i)] for i in ranked]
    for candidate, index in zip(candidates, ranked, strict=True):
        assert candidate.confidence == pytest.approx(float(expected[index]), abs=2e-3)
    assert provider.info.runtime == "onnx"
    assert provider.info.is_placeholder is False
    assert "OpenStreetView-5M" in provider.info.description


def test_provider_abstains_below_threshold_and_without_a_photo(tmp_path: Path) -> None:
    manifest, _ = export_tiny_model(tmp_path, abstain_below=1.0)
    photo = write_photo(tmp_path / "photo.png")

    assert OnnxCountryProvider(manifest).predict_image(photo) == ()

    # Starter rounds are SVG diagrams, so by default the model has nothing to look at.
    service = LearningService(tmp_path / "runtime.sqlite3", provider=OnnxCountryProvider(manifest))
    attempt = service.submit_practice(FIRST_ROUND, PracticeAnswerSubmission(skipped=True))
    result = service.model_prediction(attempt.attempt_id)
    assert result.abstained is True
    assert result.model.model_id == "country-net-test"


def test_provider_predicts_post_answer_through_an_image_source(tmp_path: Path) -> None:
    manifest, _ = export_tiny_model(tmp_path)
    photo = write_photo(tmp_path / "photo.png")
    provider = OnnxCountryProvider(manifest, images=OnePhoto(photo))
    service = LearningService(tmp_path / "runtime.sqlite3", provider=provider)

    attempt = service.submit_practice(FIRST_ROUND, PracticeAnswerSubmission(skipped=True))
    result = service.model_prediction(attempt.attempt_id)

    assert result.abstained is False
    assert len(result.candidates) == 3


def test_provider_guesses_an_uploaded_photo_like_the_same_file_on_disk(tmp_path: Path) -> None:
    from geo_companion.models import UnreadablePhotoError

    manifest, _ = export_tiny_model(tmp_path)
    photo = write_photo(tmp_path / "photo.png")
    provider = OnnxCountryProvider(manifest)
    service = LearningService(tmp_path / "runtime.sqlite3", provider=provider)

    result = service.photo_guess(photo.read_bytes())

    assert result.candidates == provider.predict_image(photo)
    assert len(result.candidates) == 3
    assert result.model.is_placeholder is False
    with pytest.raises(UnreadablePhotoError):
        provider.predict_photo(b"\x89PNG\r\n\x1a\n but truncated")


def test_provider_refuses_a_tampered_artifact(tmp_path: Path) -> None:
    manifest, _ = export_tiny_model(tmp_path)
    with (tmp_path / "model.onnx").open("ab") as handle:
        handle.write(b"\0")

    with pytest.raises(ModelIntegrityError, match="does not match"):
        OnnxCountryProvider(manifest)


@pytest.mark.parametrize("artifact_file", ["../model.onnx", "/etc/passwd", "sub/model.onnx"])
def test_manifest_cannot_point_outside_its_folder(tmp_path: Path, artifact_file: str) -> None:
    manifest, _ = export_tiny_model(tmp_path)
    data = json.loads(manifest.read_text())
    data["artifact_file"] = artifact_file
    manifest.write_text(json.dumps(data))

    with pytest.raises(ModelIntegrityError, match="Cannot read"):
        OnnxCountryProvider(manifest)


def test_provider_refuses_model_files_inside_the_repository() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    with pytest.raises(ModelIntegrityError, match="outside the repository"):
        OnnxCountryProvider(repository_root / "manifest.json")


def test_environment_selects_the_onnx_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, _ = export_tiny_model(tmp_path)
    monkeypatch.setenv("GEO_COMPANION_MODEL", f"onnx:{manifest}")
    assert isinstance(provider_from_environment(), OnnxCountryProvider)

    monkeypatch.setenv("GEO_COMPANION_MODEL", "onnx:")
    with pytest.raises(ValueError, match="onnx:<manifest path>"):
        provider_from_environment()

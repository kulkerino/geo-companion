from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


def export_tiny_model(
    tmp_path: Path, abstain_below: float = 0.0, evaluation: dict[str, Any] | None = None
) -> tuple[Path, CountryNet]:
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
        evaluation=evaluation if evaluation is not None else {"top1": 0.0},
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


# The shape ``geo_training.evaluate.report`` writes, minus ``per_country``.
SUMMARY: dict[str, Any] = {
    "images": 400, "out_of_label_set": 12, "classes": 4, "top1": 0.61, "top5": 0.97,
    "ece_raw": 0.08, "ece_calibrated": 0.02, "temperature": 1.5,
    "abstention": {"threshold": 0.55, "coverage": 0.4, "selective_top1": 0.83},
    "baselines": {"majority_class": "BR", "majority_top1": 0.3, "uniform_top1": 0.25},
}  # fmt: skip
PER_COUNTRY = {"BR": {"images": 120, "top1": 0.7}, "JP": {"images": 80, "top1": 0.55}}


def write_report(folder: Path, test: dict[str, Any]) -> None:
    (folder / "report.json").write_text(json.dumps({"val": {**SUMMARY, "top1": 0.6}, "test": test}))


def test_evaluation_joins_the_manifest_summary_with_matching_per_country_rows(
    tmp_path: Path,
) -> None:
    evaluation = {**SUMMARY, "split": "test", "calibration": "sqrt"}
    manifest, _ = export_tiny_model(tmp_path, evaluation=evaluation)
    write_report(tmp_path, {**SUMMARY, "per_country": PER_COUNTRY})

    result = OnnxCountryProvider(manifest).evaluation()

    assert result is not None
    assert result.split == "test" and result.top1 == 0.61 and result.images == 400
    assert result.abstention.coverage == 0.4
    assert [(c.country_code, c.images, c.top1) for c in result.per_country] == [
        ("BR", 120, 0.7),
        ("JP", 80, 0.55),
    ]
    assert result.model.model_id == "country-net-test"
    assert result.dataset_license == "CC BY-SA 4.0"


def test_a_report_that_disagrees_with_the_manifest_adds_no_rows(tmp_path: Path) -> None:
    manifest, _ = export_tiny_model(tmp_path, evaluation={**SUMMARY, "split": "test"})
    write_report(tmp_path, {**SUMMARY, "top1": 0.99, "per_country": PER_COUNTRY})

    result = OnnxCountryProvider(manifest).evaluation()

    assert result is not None and result.top1 == 0.61 and result.per_country == ()


def test_older_manifests_without_a_split_are_matched_against_the_report(tmp_path: Path) -> None:
    manifest, _ = export_tiny_model(tmp_path, evaluation=SUMMARY)
    write_report(tmp_path, {**SUMMARY, "per_country": PER_COUNTRY})

    result = OnnxCountryProvider(manifest).evaluation()

    assert result is not None and result.split == "test" and len(result.per_country) == 2


def test_evaluation_api_serves_results_and_404s_without_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    import geo_companion.main as main
    import httpx

    def get(path: str) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=main.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get(path)

        return asyncio.run(send())

    full = tmp_path / "full"
    full.mkdir()
    manifest, _ = export_tiny_model(full, evaluation={**SUMMARY, "split": "test"})
    service = LearningService(tmp_path / "a.sqlite3", provider=OnnxCountryProvider(manifest))
    monkeypatch.setattr(main, "learning_service", service)
    response = get("/api/v1/models/evaluation")
    assert response.status_code == 200
    assert response.json()["top1"] == 0.61 and response.json()["per_country"] == []

    # A smoke manifest with an incomplete summary: the model runs, but has no evaluation.
    smoke = tmp_path / "smoke"
    smoke.mkdir()
    manifest, _ = export_tiny_model(smoke)
    service = LearningService(tmp_path / "b.sqlite3", provider=OnnxCountryProvider(manifest))
    monkeypatch.setattr(main, "learning_service", service)
    response = get("/api/v1/models/evaluation")
    assert response.status_code == 404
    assert response.json()["detail"] == "The enabled model has no recorded evaluation."


def test_provider_never_answers_a_country_geoguessr_does_not_cover(tmp_path: Path) -> None:
    manifest, model = export_tiny_model(tmp_path)
    data = json.loads(manifest.read_text())
    data["classes"] = ["BR", "CN", "SJ", "KE"]  # China and Svalbard are not in GeoGuessr
    manifest.write_text(json.dumps(data))
    photo = write_photo(tmp_path / "photo.png")

    candidates = OnnxCountryProvider(manifest).predict_image(photo)

    with torch.no_grad():
        logits = model(torch.from_numpy(eval_array(Image.open(photo).convert("RGB"), SIZE))[None])
    masked = (logits[0] / 1.5)[[0, 3]].softmax(0)
    expected = ["BR", "KE"] if masked[0] >= masked[1] else ["KE", "BR"]
    assert [c.country_code for c in candidates] == expected
    assert sum(c.confidence for c in candidates) == pytest.approx(1.0, abs=2e-3)


def test_provider_refuses_a_model_without_any_geoguessr_country(tmp_path: Path) -> None:
    manifest, _ = export_tiny_model(tmp_path)
    data = json.loads(manifest.read_text())
    data["classes"] = ["CN", "SJ", "AZ", "PW"]
    manifest.write_text(json.dumps(data))
    with pytest.raises(ModelIntegrityError, match="GeoGuessr"):
        OnnxCountryProvider(manifest)

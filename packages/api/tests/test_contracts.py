"""Executable content and application contracts for future learning flows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "packs"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text())


def test_complete_cleared_pack_is_publication_ready_and_immutable() -> None:
    from geo_companion.contracts import ContentPack

    pack = ContentPack.model_validate(load_fixture("complete-cleared-pack.json"))

    assert pack.is_publication_ready() is True
    with pytest.raises(ValidationError):
        pack.version = "2.0.0"  # type: ignore[misc]
    with pytest.raises(TypeError, match="immutable"):
        pack.model_copy(update={"content_hash": "sha256:" + "b" * 64})


@pytest.mark.parametrize(
    "fixture_name",
    [
        "missing-source-pack.json",
        "missing-license-pack.json",
        "missing-creator-pack.json",
        "missing-answer-pack.json",
    ],
)
def test_incomplete_hand_checked_pack_fixtures_are_rejected(fixture_name: str) -> None:
    from geo_companion.contracts import ContentPack

    with pytest.raises(ValidationError):
        ContentPack.model_validate(load_fixture(fixture_name))


def test_non_cleared_content_cannot_be_published() -> None:
    from geo_companion.contracts import ContentPack, PublicationError

    pack = ContentPack.model_validate(load_fixture("non-cleared-pack.json"))

    assert pack.is_publication_ready() is False
    with pytest.raises(PublicationError, match="cleared"):
        pack.require_publication_ready()


def test_practice_round_public_contract_keeps_answer_and_coordinate_hidden() -> None:
    from geo_companion.contracts import ContentPack, PracticeRoundPublic

    pack = ContentPack.model_validate(load_fixture("complete-cleared-pack.json"))
    public_round = PracticeRoundPublic.from_round(pack.practice_rounds[0])

    assert public_round.model_dump(mode="json") == {
        "round_id": "bollards-practice-1",
        "asset_id": "original-bollards-diagram",
        "asset_attribution": pack.practice_rounds[0].asset_attribution.model_dump(mode="json"),
    }
    assert "answer" not in public_round.model_dump()
    assert "coordinate" not in public_round.model_dump()


def test_answer_origins_are_separate_from_source_truth() -> None:
    from geo_companion.contracts import AnswerOrigin, Feedback, ModelPrediction, UserCorrection

    correction = UserCorrection(
        round_id="r1", country_code="AT", note="The published answer is wrong."
    )
    prediction = ModelPrediction(
        round_id="r1", model_id="student-small.onnx", country_code="AT", confidence=0.4
    )
    feedback = Feedback(round_id="r1", rating=3, note="I confused the bollard shape.")

    assert correction.origin is AnswerOrigin.USER_CORRECTION
    assert prediction.origin is AnswerOrigin.MODEL_PREDICTION
    assert feedback.round_id == "r1"


def test_study_model_and_experiment_contracts_keep_optional_model_offline_safe() -> None:
    from geo_companion.contracts import Experiment, ModelManifest, StudyProgress

    progress = StudyProgress(lesson_id="bollards", repetitions=2, interval_days=6, ease_factor=2.5)
    manifest = ModelManifest(
        model_id="student-small.onnx",
        artifact_hash="sha256:" + "1" * 64,
        runtime="onnx",
        required_for_learning=False,
    )
    experiment = Experiment(
        experiment_id="shadow-1",
        model_id=manifest.model_id,
        status="shadow",
        answer_source="source_truth",
    )

    assert progress.next_review_on is not None
    assert manifest.required_for_learning is False
    assert experiment.status == "shadow"

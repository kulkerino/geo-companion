"""Real country model: an exported ONNX classifier behind the ``PredictionProvider`` boundary.

The manifest binds the provider to one artifact by SHA-256; a mismatch refuses to start. The
app never downloads a model: both files must already exist outside this repository. Needs
the optional ``model`` dependency group (onnxruntime, NumPy, Pillow), so this module is only
imported when ``GEO_COMPANION_MODEL=onnx:<manifest>`` asks for it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np
import onnxruntime  # type: ignore[import-untyped]
from PIL import Image

from geo_companion.contracts import (
    CountryAccuracy,
    CountryModelManifest,
    ModelCandidate,
    ModelEvaluation,
    ModelInfo,
    PracticeRoundPublic,
)
from geo_companion.geoguessr_countries import GEOGUESSR_COUNTRIES
from geo_companion.image_input import decode_upload, eval_array, load_rgb
from geo_companion.models import UnreadablePhotoError
from geo_companion.paths import is_inside_repository

TOP_K = 3
REPORT_FILE = "report.json"
# Manifest evaluation keys that describe the run rather than a result in the report.
RUN_KEYS = frozenset({"split", "calibration"})


class ModelIntegrityError(RuntimeError):
    """The manifest or artifact cannot be trusted, so the provider refuses to load."""


class RoundImageSource(Protocol):
    def image_path(self, round_: PracticeRoundPublic) -> Path | None:
        """Return a raster image for the round, or None when there is none to show the model."""
        ...


class NoRasterImages:
    """Starter rounds are SVG diagrams, not photos, so a photo model has nothing to see."""

    def image_path(self, round_: PracticeRoundPublic) -> Path | None:
        return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _trained(backbone: str) -> str:
    if backbone == "countrynet":
        return "trained from scratch"
    return f"fine-tuned from the pretrained {backbone} network"


class OnnxCountryProvider:
    """Calibrated top-3 countries from a photo, or an abstention below the manifest threshold."""

    def __init__(self, manifest_path: Path, images: RoundImageSource | None = None) -> None:
        manifest_path = manifest_path.resolve()
        if is_inside_repository(manifest_path):
            raise ModelIntegrityError("Model files must live outside the repository.")
        try:
            self.manifest = CountryModelManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as error:
            raise ModelIntegrityError(f"Cannot read model manifest {manifest_path}.") from error
        if self.manifest.runtime != "onnx":
            raise ModelIntegrityError("The manifest does not describe an ONNX model.")
        artifact = manifest_path.parent / self.manifest.artifact_file
        if not artifact.is_file():
            raise ModelIntegrityError(f"Model artifact {artifact} is missing.")
        if _sha256_file(artifact) != self.manifest.artifact_hash:
            raise ModelIntegrityError(f"Model artifact {artifact} does not match its manifest.")
        self._session = onnxruntime.InferenceSession(
            str(artifact), providers=["CPUExecutionProvider"]
        )
        self._images = images or NoRasterImages()
        # Only countries with GeoGuessr coverage may be answered: the others are masked out and
        # the remaining probabilities renormalised, so no retraining is needed.
        self._allowed = np.array([code in GEOGUESSR_COUNTRIES for code in self.manifest.classes])
        if not self._allowed.any():
            raise ModelIntegrityError("The model knows none of GeoGuessr's countries.")
        self.info = ModelInfo(
            model_id=self.manifest.model_id,
            version=self.manifest.version,
            runtime="onnx",
            is_placeholder=False,
            description=(
                f"Country classifier {_trained(self.manifest.backbone)} on "
                f"{self.manifest.trained_on}. "
                f"It sees photos only and abstains when unsure or when a round has no photo. "
                f"{self.manifest.dataset_attribution}"
            ),
        )

        self._evaluation = _evaluation(self.manifest, self.info, manifest_path.parent)

    def evaluation(self) -> ModelEvaluation | None:
        return self._evaluation

    def predict(self, round_: PracticeRoundPublic) -> tuple[ModelCandidate, ...]:
        path = self._images.image_path(round_)
        return () if path is None else self.predict_image(path)

    def predict_image(self, path: Path) -> tuple[ModelCandidate, ...]:
        """Rank countries for one image file; an empty tuple means the model abstains."""
        return self._rank(load_rgb(path))

    def predict_photo(self, photo: bytes) -> tuple[ModelCandidate, ...]:
        try:
            image = decode_upload(photo)
        except ValueError as error:
            raise UnreadablePhotoError(str(error)) from error
        return self._rank(image)

    def _rank(self, rgb: Image.Image) -> tuple[ModelCandidate, ...]:
        image = eval_array(rgb, self.manifest.input_size)
        (logits,) = self._session.run(["logits"], {"image": image[np.newaxis]})
        scaled = np.asarray(logits, dtype=np.float64)[0] / self.manifest.temperature
        scaled = np.where(self._allowed, scaled, -np.inf)
        probabilities = np.exp(scaled - scaled.max())
        probabilities /= probabilities.sum()
        order = np.argsort(-probabilities, kind="stable")[:TOP_K]
        if probabilities[order[0]] < self.manifest.abstain_below:
            return ()
        ranked = ((index, round(float(probabilities[index]), 3)) for index in order)
        return tuple(
            ModelCandidate(country_code=self.manifest.classes[index], confidence=confidence)
            for index, confidence in ranked
            if confidence > 0
        )


def _evaluation(
    manifest: CountryModelManifest, info: ModelInfo, folder: Path
) -> ModelEvaluation | None:
    """Build the accuracy summary from the manifest, adding per-country rows from the run's
    ``report.json`` only when one of its splits matches the manifest summary exactly.

    The manifest is bound to the artifact by hash; the report is not, so a report that
    disagrees with the manifest is ignored rather than trusted. A manifest whose summary is
    incomplete (an early smoke run, say) has no evaluation, and the model still works.
    """
    summary = {k: v for k, v in manifest.evaluation.items() if k not in RUN_KEYS}
    declared = manifest.evaluation.get("split")
    split: Literal["test", "val", "unknown"] = (
        "test" if declared == "test" else "val" if declared == "val" else "unknown"
    )
    names: tuple[Literal["test", "val"], ...] = ("test", "val") if split == "unknown" else (split,)
    per_country: dict[str, Any] = {}
    try:
        report = json.loads((folder / REPORT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = None
    for name in names:
        candidate = report.get(name) if isinstance(report, dict) else None
        if not isinstance(candidate, dict):
            continue
        rows = candidate.get("per_country")
        if {k: v for k, v in candidate.items() if k != "per_country"} == summary:
            split = name
            per_country = rows if isinstance(rows, dict) else {}
            break
    try:
        return ModelEvaluation(
            model=info,
            split=split,
            per_country=tuple(
                CountryAccuracy(country_code=code, **row) for code, row in per_country.items()
            ),
            trained_on=manifest.trained_on,
            dataset_license=manifest.dataset_license,
            dataset_attribution=manifest.dataset_attribution,
            **summary,
        )
    except (TypeError, ValueError):
        return None

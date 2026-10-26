"""Local prediction providers behind one boundary; the learning loop never depends on them.

A provider sees only the public round (asset ID and attribution), never the authored answer,
so it cannot leak or copy the answer key. The dummy provider stands in for a future local
model: it exercises the same API, storage, and UI paths without any inference or download.
"""

from __future__ import annotations

import hashlib
import os
import random
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from geo_companion.contracts import ModelCandidate, ModelInfo, PracticeRoundPublic

if TYPE_CHECKING:
    from geo_companion.onnx_provider import RoundImageSource

MODEL_ENVIRONMENT_VARIABLE = "GEO_COMPANION_MODEL"

# Fixed, answer-independent label space for the placeholder (European ISO 3166-1 alpha-2).
DUMMY_LABELS = (
    "AT", "BE", "BG", "CH", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GB", "GR", "HR",
    "HU", "IE", "IT", "LT", "LV", "NL", "NO", "PL", "PT", "RO", "SE", "SI", "SK",
)  # fmt: skip
ABSTAIN_BELOW = 0.2


class PredictionProvider(Protocol):
    info: ModelInfo

    def predict(self, round_: PracticeRoundPublic) -> tuple[ModelCandidate, ...]:
        """Return up to three ranked candidates, or an empty tuple to abstain."""
        ...


class DummyProvider:
    """Deterministic placeholder: seeded scores over a fixed label set, no inference."""

    info = ModelInfo(
        model_id="dummy-placeholder",
        version="0.1.0",
        runtime="dummy",
        is_placeholder=True,
        description=(
            "Placeholder model for wiring and testing. Its guesses are deterministic "
            "pseudo-random scores, not image analysis, and say nothing about the diagram."
        ),
    )

    def predict(self, round_: PracticeRoundPublic) -> tuple[ModelCandidate, ...]:
        seed_text = f"{self.info.model_id}:{self.info.version}:{round_.round_id}:{round_.asset_id}"
        seed = int.from_bytes(hashlib.sha256(seed_text.encode()).digest()[:8], "big")
        generator = random.Random(seed)
        weights = {label: generator.random() ** 10 for label in DUMMY_LABELS}
        total = sum(weights.values())
        ranked = sorted(weights.items(), key=lambda item: (-item[1], item[0]))[:3]
        candidates = tuple(
            ModelCandidate(country_code=label, confidence=round(weight / total, 3))
            for label, weight in ranked
        )
        return () if candidates[0].confidence < ABSTAIN_BELOW else candidates


def provider_from_environment(
    images: RoundImageSource | None = None,
) -> PredictionProvider | None:
    """``GEO_COMPANION_MODEL`` selects the provider: ``dummy`` (default), ``none``, or
    ``onnx:<manifest path>`` for a real exported model (needs the ``model`` dependency group).
    ``images`` shows a real model the photo of each photo round.
    """
    raw = os.environ.get(MODEL_ENVIRONMENT_VARIABLE, "dummy").strip()
    choice = raw.lower()
    if choice == "none":
        return None
    if choice == "dummy":
        return DummyProvider()
    if choice.startswith("onnx:") and raw[len("onnx:") :].strip():
        from geo_companion.onnx_provider import OnnxCountryProvider

        return OnnxCountryProvider(Path(raw[len("onnx:") :].strip()).expanduser(), images)
    msg = (
        f"{MODEL_ENVIRONMENT_VARIABLE} must be 'dummy', 'none' or 'onnx:<manifest path>', "
        f"not {raw!r}."
    )
    raise ValueError(msg)

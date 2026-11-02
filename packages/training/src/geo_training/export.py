"""Export to ONNX, check parity with PyTorch, and write a hash-bound manifest."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime  # type: ignore[import-untyped]
import torch
from geo_companion.contracts import CountryModelManifest

from geo_training.ledger import DatasetRecord


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def export_onnx(model: torch.nn.Module, input_size: int, path: Path) -> float:
    """Write ``path`` and return the largest absolute logit difference against PyTorch."""
    model = model.cpu().eval()
    example = torch.randn(2, 3, input_size, input_size, generator=torch.Generator().manual_seed(0))
    torch.onnx.export(
        model,
        (example,),
        str(path),
        input_names=["image"],
        output_names=["logits"],
        dynamic_shapes={"x": {0: torch.export.Dim("batch", min=1, max=1024)}},
        dynamo=True,
        external_data=False,
        verbose=False,
    )
    with torch.no_grad():
        expected = model(example).numpy()
    session = onnxruntime.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    (actual,) = session.run(["logits"], {"image": example.numpy()})
    return float(np.abs(np.asarray(actual) - expected).max())


def write_manifest(
    *,
    model_id: str,
    version: str,
    artifact: Path,
    classes: Sequence[str],
    input_size: int,
    temperature: float,
    abstain_below: float,
    dataset: DatasetRecord,
    evaluation: dict[str, Any],
    path: Path,
) -> CountryModelManifest:
    manifest = CountryModelManifest(
        model_id=model_id,
        version=version,
        artifact_hash=sha256_file(artifact),
        artifact_file=artifact.name,
        runtime="onnx",
        classes=tuple(classes),
        input_size=input_size,
        temperature=temperature,
        abstain_below=abstain_below,
        trained_on=dataset.dataset_id,
        dataset_license=dataset.license_name,
        dataset_attribution=dataset.attribution_text,
        evaluation=evaluation,
    )
    path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2), encoding="utf-8")
    return manifest


__all__ = ["CountryModelManifest", "export_onnx", "sha256_file", "write_manifest"]

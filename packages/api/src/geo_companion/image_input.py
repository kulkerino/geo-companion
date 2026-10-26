"""Evaluation-time image preprocessing, shared by training and the app's ONNX provider.

Only Pillow and NumPy (the optional ``model`` dependency group), so the app reproduces the
training pipeline's evaluation input exactly without PyTorch. Import it only when a real
model is enabled.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from geo_companion.contracts import IMAGE_MEAN, IMAGE_STD


def load_rgb(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def eval_array(image: Image.Image, size: int) -> NDArray[np.float32]:
    """Resize the shorter side to ``size``, centre-crop, normalise; returns CHW float32."""
    scale = size / min(image.size)
    resized = image.resize(
        (max(size, round(image.width * scale)), max(size, round(image.height * scale))),
        Image.Resampling.BILINEAR,
    )
    left = (resized.width - size) // 2
    top = (resized.height - size) // 2
    return normalise(resized.crop((left, top, left + size, top + size)))


def normalise(image: Image.Image) -> NDArray[np.float32]:
    pixels = np.asarray(image, dtype=np.float32) / np.float32(255.0)
    array = (pixels - np.array(IMAGE_MEAN, dtype=np.float32)) / np.array(
        IMAGE_STD, dtype=np.float32
    )
    return np.ascontiguousarray(array.transpose(2, 0, 1), dtype=np.float32)

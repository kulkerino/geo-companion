"""Image preprocessing shared by training, evaluation and the exported model.

Evaluation preprocessing uses only Pillow and NumPy, so the app can reproduce it exactly
without PyTorch.
"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image

MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)


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
    return _normalise(resized.crop((left, top, left + size, top + size)))


def train_array(image: Image.Image, size: int, rng: random.Random) -> NDArray[np.float32]:
    """Random resized crop plus mild colour jitter. No horizontal flip: flipping reverses
    the driving side and mirrors text, both of which are real country cues."""
    area = image.width * image.height
    for _ in range(10):
        target = area * rng.uniform(0.35, 1.0)
        ratio = rng.uniform(3 / 4, 4 / 3)
        width = round((target * ratio) ** 0.5)
        height = round((target / ratio) ** 0.5)
        if 0 < width <= image.width and 0 < height <= image.height:
            left = rng.randint(0, image.width - width)
            top = rng.randint(0, image.height - height)
            image = image.crop((left, top, left + width, top + height))
            break
    image = image.resize((size, size), Image.Resampling.BILINEAR)
    array = _normalise(image)
    brightness = rng.uniform(0.8, 1.2)
    contrast = rng.uniform(0.8, 1.2)
    mean = array.mean()
    return ((array - mean) * contrast + mean * brightness).astype(np.float32)


def _normalise(image: Image.Image) -> NDArray[np.float32]:
    pixels = np.asarray(image, dtype=np.float32) / np.float32(255.0)
    array = (pixels - np.array(MEAN, dtype=np.float32)) / np.array(STD, dtype=np.float32)
    return np.ascontiguousarray(array.transpose(2, 0, 1), dtype=np.float32)

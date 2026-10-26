"""Training-time augmentation. Evaluation preprocessing lives in ``geo_companion.image_input``
so the app reproduces it exactly without PyTorch; it is re-exported here.
"""

from __future__ import annotations

import random

import numpy as np
from geo_companion.contracts import IMAGE_MEAN as MEAN
from geo_companion.contracts import IMAGE_STD as STD
from geo_companion.image_input import eval_array, load_rgb, normalise
from numpy.typing import NDArray
from PIL import Image

__all__ = ["MEAN", "STD", "eval_array", "load_rgb", "train_array"]


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
    array = normalise(image)
    brightness = rng.uniform(0.8, 1.2)
    contrast = rng.uniform(0.8, 1.2)
    mean = array.mean()
    return ((array - mean) * contrast + mean * brightness).astype(np.float32)

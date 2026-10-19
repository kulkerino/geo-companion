"""Deterministic, geographically grouped splits and the class (country) list."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Iterable, Sequence

from geo_training.metadata import Sample

CELL_DEGREES = 0.1


def group_key(sample: Sample, cell_degrees: float = CELL_DEGREES) -> str:
    """Images from the same capture sequence or the same small cell share one group.

    Grouping keeps near-duplicate frames of one street on the same side of the split.
    """
    if sample.sequence:
        return f"seq:{sample.sequence}"
    lat_cell = math.floor(sample.latitude / cell_degrees)
    lon_cell = math.floor(sample.longitude / cell_degrees)
    return f"cell:{lat_cell}:{lon_cell}"


def is_validation(sample: Sample, fraction: float, salt: str = "geo-companion-val") -> bool:
    digest = hashlib.sha256(f"{salt}:{group_key(sample)}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64 < fraction


def split_train_val(
    samples: Iterable[Sample], fraction: float = 0.05
) -> tuple[list[Sample], list[Sample]]:
    train: list[Sample] = []
    val: list[Sample] = []
    for sample in samples:
        (val if is_validation(sample, fraction) else train).append(sample)
    return train, val


def select_classes(samples: Sequence[Sample], min_count: int) -> tuple[str, ...]:
    """Countries with at least ``min_count`` training images, in sorted order."""
    counts = Counter(sample.country for sample in samples)
    return tuple(sorted(country for country, count in counts.items() if count >= min_count))

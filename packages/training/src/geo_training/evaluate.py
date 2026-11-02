"""Evaluation report: accuracy, calibration, abstention, per-country results, baselines."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

import torch

from geo_training.calibration import expected_calibration_error

MIN_COUNTRY_SUPPORT = 50


def report(
    logits: torch.Tensor,
    labels: torch.Tensor,
    classes: Sequence[str],
    temperature: float,
    threshold: float,
    train_majority: str,
    out_of_label_set: int,
    min_support: int = MIN_COUNTRY_SUPPORT,
) -> dict[str, Any]:
    """Summarise predictions on one split. The temperature and threshold must come from val."""
    n = len(labels)
    if n == 0:
        return {"images": 0, "out_of_label_set": out_of_label_set}
    raw = logits.softmax(1)
    probs = (logits / temperature).softmax(1)
    confidence, predicted = probs.max(1)
    correct = predicted == labels
    top5 = (probs.topk(min(5, len(classes)), dim=1).indices == labels[:, None]).any(1)
    answered = confidence >= threshold
    majority_index = classes.index(train_majority) if train_majority in classes else -1

    per_country: dict[str, dict[str, float | int]] = {}
    support = Counter(int(label) for label in labels)
    for index, count in sorted(support.items()):
        if count >= min_support:
            mask = labels == index
            per_country[classes[index]] = {
                "images": count,
                "top1": round(float(correct[mask].float().mean()), 4),
            }

    return {
        "images": n,
        "out_of_label_set": out_of_label_set,
        "classes": len(classes),
        "top1": round(float(correct.float().mean()), 4),
        "top5": round(float(top5.float().mean()), 4),
        "ece_raw": round(expected_calibration_error(raw, labels), 4),
        "ece_calibrated": round(expected_calibration_error(probs, labels), 4),
        "temperature": round(temperature, 4),
        "abstention": {
            "threshold": round(threshold, 4),
            "coverage": round(float(answered.float().mean()), 4),
            "selective_top1": (
                round(float(correct[answered].float().mean()), 4) if answered.any() else None
            ),
        },
        "baselines": {
            "majority_class": train_majority,
            "majority_top1": round(float((labels == majority_index).float().mean()), 4),
            "uniform_top1": round(1 / len(classes), 4),
        },
        "per_country": per_country,
    }

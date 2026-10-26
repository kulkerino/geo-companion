"""Temperature scaling, calibration error, and an abstention threshold chosen on validation."""

from __future__ import annotations

from dataclasses import dataclass

import torch


def class_weights(labels: torch.Tensor, power: float) -> torch.Tensor:
    """Per-sample weights ``count(class) ** -power``, rescaled to mean 1.

    Validation keeps the training shards' country mix (a quarter of OSV-5M train is US), but
    the model was trained with square-root class-balanced sampling, and the test split and the
    app's players have a different mix. ``power=0.5`` reweights validation to the same prior
    the model was trained under; ``1`` gives every class equal weight; ``0`` changes nothing.
    """
    counts = torch.bincount(labels).float()
    weights = counts[labels] ** -power
    return weights * (len(labels) / weights.sum())


CALIBRATION_POWERS = {"sqrt": 0.5, "balanced": 1.0, "natural": 0.0}


def fit_temperature(
    logits: torch.Tensor, labels: torch.Tensor, weights: torch.Tensor | None = None
) -> float:
    """Return the temperature that minimises (weighted) validation negative log-likelihood."""
    sample_weights = torch.ones(len(labels)) if weights is None else weights
    log_temperature = torch.zeros(1, requires_grad=True)
    optimiser = torch.optim.LBFGS(
        [log_temperature], lr=1.0, max_iter=100, line_search_fn="strong_wolfe"
    )
    loss_fn = torch.nn.CrossEntropyLoss(reduction="none")

    def closure() -> torch.Tensor:
        optimiser.zero_grad()
        per_sample = loss_fn(logits / log_temperature.exp(), labels)
        loss: torch.Tensor = (per_sample * sample_weights).sum() / sample_weights.sum()
        loss.backward()  # type: ignore[no-untyped-call]
        return loss

    optimiser.step(closure)  # type: ignore[no-untyped-call]
    return float(log_temperature.exp().item())


def expected_calibration_error(probs: torch.Tensor, labels: torch.Tensor, bins: int = 15) -> float:
    confidence, predicted = probs.max(dim=1)
    correct = (predicted == labels).float()
    edges = torch.linspace(0, 1, bins + 1)
    error = torch.zeros(())
    for low, high in zip(edges[:-1], edges[1:], strict=True):
        in_bin = (confidence > low) & (confidence <= high)
        if in_bin.any():
            gap = (confidence[in_bin].mean() - correct[in_bin].mean()).abs()
            error += gap * in_bin.float().mean()
    return float(error.item())


@dataclass(frozen=True)
class Abstention:
    threshold: float
    coverage: float
    selective_accuracy: float


def choose_threshold(
    probs: torch.Tensor,
    labels: torch.Tensor,
    target: float,
    weights: torch.Tensor | None = None,
) -> Abstention:
    """Lowest top-1 threshold whose answered subset reaches ``target`` (weighted) accuracy.

    The model answers when top-1 probability >= threshold, otherwise it abstains. If no
    threshold reaches the target, the threshold is 1.0 (the manifest maximum), so the model
    abstains unless its top-1 probability is exactly 1.
    """
    sample_weights = torch.ones(len(labels)) if weights is None else weights
    confidence, predicted = probs.max(dim=1)
    order = confidence.argsort(descending=True)
    ordered_weights = sample_weights[order]
    correct = (predicted == labels)[order].float()
    answered_weight = ordered_weights.cumsum(0)
    running = (correct * ordered_weights).cumsum(0) / answered_weight
    reaching = (running >= target).nonzero().flatten()
    if len(reaching) == 0:
        return Abstention(threshold=1.0, coverage=0.0, selective_accuracy=0.0)
    last = int(reaching[-1].item())
    return Abstention(
        threshold=float(confidence[order][last].item()),
        coverage=float((answered_weight[last] / sample_weights.sum()).item()),
        selective_accuracy=float(running[last].item()),
    )

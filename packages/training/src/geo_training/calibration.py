"""Temperature scaling, calibration error, and an abstention threshold chosen on validation."""

from __future__ import annotations

from dataclasses import dataclass

import torch


def fit_temperature(logits: torch.Tensor, labels: torch.Tensor) -> float:
    """Return the temperature that minimises validation negative log-likelihood."""
    log_temperature = torch.zeros(1, requires_grad=True)
    optimiser = torch.optim.LBFGS(
        [log_temperature], lr=1.0, max_iter=100, line_search_fn="strong_wolfe"
    )
    loss_fn = torch.nn.CrossEntropyLoss()

    def closure() -> torch.Tensor:
        optimiser.zero_grad()
        loss: torch.Tensor = loss_fn(logits / log_temperature.exp(), labels)
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


def choose_threshold(probs: torch.Tensor, labels: torch.Tensor, target: float) -> Abstention:
    """Lowest top-1 threshold whose answered subset reaches ``target`` accuracy.

    The model answers when top-1 probability >= threshold, otherwise it abstains. If no
    threshold reaches the target, the threshold is above 1 and the model always abstains.
    """
    confidence, predicted = probs.max(dim=1)
    order = confidence.argsort(descending=True)
    correct = (predicted == labels)[order].float()
    running = correct.cumsum(0) / torch.arange(1, len(correct) + 1)
    reaching = (running >= target).nonzero().flatten()
    if len(reaching) == 0:
        return Abstention(threshold=1.01, coverage=0.0, selective_accuracy=0.0)
    last = int(reaching[-1].item())
    return Abstention(
        threshold=float(confidence[order][last].item()),
        coverage=(last + 1) / len(correct),
        selective_accuracy=float(running[last].item()),
    )

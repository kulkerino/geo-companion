"""Training loop for CountryNet: deterministic seeding, AdamW + cosine, balanced sampling."""

from __future__ import annotations

import json
import math
import random
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from geo_training.metadata import Sample
from geo_training.model import CountryNet
from geo_training.preprocess import eval_array, load_rgb, train_array


@dataclass(frozen=True)
class TrainConfig:
    image_size: int = 224
    width: int = 64
    epochs: int = 30
    batch_size: int = 128
    learning_rate: float = 2e-3
    weight_decay: float = 0.05
    label_smoothing: float = 0.1
    warmup_epochs: float = 1.0
    balance: str = "sqrt"  # "sqrt" class-balanced sampling, or "none"
    seed: int = 0
    num_workers: int = 4
    device: str = "auto"


class SampleDataset(Dataset[tuple[torch.Tensor, int]]):
    def __init__(
        self, samples: Sequence[Sample], classes: Sequence[str], size: int, train: bool, seed: int
    ):
        index = {country: position for position, country in enumerate(classes)}
        self.items = [(s.image_path, index[s.country]) for s in samples if s.country in index]
        self.size = size
        self.train = train
        self.seed = seed
        self.epoch = 0

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, position: int) -> tuple[torch.Tensor, int]:
        path, label = self.items[position]
        image = load_rgb(path)
        if self.train:
            rng = random.Random(f"{self.seed}:{self.epoch}:{position}")
            array = train_array(image, self.size, rng)
        else:
            array = eval_array(image, self.size)
        return torch.from_numpy(array), label


def resolve_device(choice: str) -> torch.device:
    if choice != "auto":
        return torch.device(choice)
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _sampler(dataset: SampleDataset, balance: str, seed: int) -> WeightedRandomSampler | None:
    if balance == "none":
        return None
    counts = Counter(label for _, label in dataset.items)
    weights = [1.0 / math.sqrt(counts[label]) for _, label in dataset.items]
    generator = torch.Generator().manual_seed(seed)
    return WeightedRandomSampler(weights, len(weights), replacement=True, generator=generator)


@torch.no_grad()
def predict_logits(
    model: nn.Module, dataset: SampleDataset, batch_size: int, device: torch.device, workers: int
) -> tuple[torch.Tensor, torch.Tensor]:
    model.eval()
    loader = DataLoader(dataset, batch_size=batch_size, num_workers=workers)
    all_logits: list[torch.Tensor] = []
    all_labels: list[torch.Tensor] = []
    for images, labels in loader:
        all_logits.append(model(images.to(device)).float().cpu())
        all_labels.append(labels)
    return torch.cat(all_logits), torch.cat(all_labels)


def train(
    train_samples: Sequence[Sample],
    val_samples: Sequence[Sample],
    classes: Sequence[str],
    config: TrainConfig,
    out_dir: Path,
) -> CountryNet:
    """Train from random initialisation, log per-epoch metrics, and keep the best checkpoint."""
    torch.manual_seed(config.seed)
    random.seed(config.seed)
    device = resolve_device(config.device)
    out_dir.mkdir(parents=True, exist_ok=True)

    train_set = SampleDataset(train_samples, classes, config.image_size, True, config.seed)
    val_set = SampleDataset(val_samples, classes, config.image_size, False, config.seed)
    sampler = _sampler(train_set, config.balance, config.seed)
    loader = DataLoader(
        train_set,
        batch_size=config.batch_size,
        sampler=sampler,
        shuffle=sampler is None,
        num_workers=config.num_workers,
        drop_last=len(train_set) > config.batch_size,
        generator=torch.Generator().manual_seed(config.seed),
        persistent_workers=False,
    )
    model = CountryNet(len(classes), width=config.width).to(device)
    optimiser = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    total_steps = max(1, config.epochs * len(loader))
    warmup_steps = round(config.warmup_epochs * len(loader))

    def learning_rate_factor(step: int) -> float:
        if step < warmup_steps:
            return (step + 1) / warmup_steps
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return 0.5 * (1 + math.cos(math.pi * progress))

    schedule = torch.optim.lr_scheduler.LambdaLR(optimiser, learning_rate_factor)
    loss_fn = nn.CrossEntropyLoss(label_smoothing=config.label_smoothing)
    use_amp = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    (out_dir / "config.json").write_text(
        json.dumps({**asdict(config), "classes": list(classes)}, indent=2), encoding="utf-8"
    )
    best_accuracy = -1.0
    with (out_dir / "history.jsonl").open("w", encoding="utf-8") as history:
        for epoch in range(config.epochs):
            model.train()
            train_set.epoch = epoch
            started = time.monotonic()
            running_loss = 0.0
            for images, labels in loader:
                images, labels = images.to(device), labels.to(device)
                optimiser.zero_grad(set_to_none=True)
                with torch.autocast(device.type, dtype=torch.float16, enabled=use_amp):
                    loss = loss_fn(model(images), labels)
                scaler.scale(loss).backward()
                scaler.step(optimiser)
                scaler.update()
                schedule.step()
                running_loss += float(loss.item())
            logits, labels = predict_logits(
                model, val_set, config.batch_size, device, config.num_workers
            )
            correct = (logits.argmax(1) == labels).float()
            accuracy = float(correct.mean().item()) if len(labels) else 0.0
            record = {
                "epoch": epoch + 1,
                "train_loss": running_loss / max(1, len(loader)),
                "val_top1": accuracy,
                "seconds": round(time.monotonic() - started, 2),
            }
            history.write(json.dumps(record) + "\n")
            history.flush()
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                torch.save(model.state_dict(), out_dir / "best.pt")
    model.load_state_dict(torch.load(out_dir / "best.pt", map_location=device, weights_only=True))
    return model

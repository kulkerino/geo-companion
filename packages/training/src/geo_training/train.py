"""Training loop for CountryNet: deterministic seeding, AdamW + cosine, balanced sampling.

After every epoch the full training state goes to ``last.pt``, so a run can stop (on a time
budget, or by being killed) and resume with identical results. ``last.pt`` is removed once
all epochs are done.
"""

from __future__ import annotations

import json
import math
import random
import sys
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from geo_training.metadata import Sample
from geo_training.model import build_model
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
    # A finished run folder (config.json + final.pt) to fine-tune from instead of random weights.
    init_from: str | None = None
    # "countrynet" (from scratch) or a pretrained network such as "clip-b16"; see model.py.
    backbone: str = "countrynet"
    # Pretrained networks learn their new country layer this many times faster than the rest.
    head_lr_scale: float = 10.0


# Settings that may change between the sessions of one run; everything else must match.
RESUMABLE_CHANGES = frozenset({"num_workers", "device"})
PROGRESS_EVERY = 500  # steps between progress lines on stderr


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


def initialise_from_run(
    model: nn.Module, classes: Sequence[str], run_dir: Path, backbone: str = "countrynet"
) -> int:
    """Copy a finished run's weights into ``model``; return how many countries it already knew.

    Everything but the final layer is copied as is. The final layer is matched row by row on
    the country code, so countries the earlier model knew keep what it learned and new ones
    start fresh. Fine-tuning this way needs far fewer images than training from scratch.
    """
    saved = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    state = torch.load(run_dir / "final.pt", map_location="cpu")
    saved_backbone = saved.get("backbone", "countrynet")
    if saved_backbone != backbone:
        msg = f"{run_dir} uses backbone {saved_backbone}; pass that --backbone."
        raise SystemExit(msg)
    head = model.get_submodule("head")
    assert isinstance(head, nn.Linear)
    if state["head.weight"].shape[1] != head.in_features:
        msg = f"{run_dir} was trained with width {saved['width']}; pass the same --width."
        raise SystemExit(msg)
    old_index = {code: index for index, code in enumerate(saved["classes"])}
    head_weight = head.weight.detach().clone()
    head_bias = head.bias.detach().clone()
    known = 0
    for index, code in enumerate(classes):
        if code in old_index:
            head_weight[index] = state["head.weight"][old_index[code]]
            head_bias[index] = state["head.bias"][old_index[code]]
            known += 1
    state["head.weight"] = head_weight
    state["head.bias"] = head_bias
    model.load_state_dict(state)
    return known


def train(
    train_samples: Sequence[Sample],
    val_samples: Sequence[Sample],
    classes: Sequence[str],
    config: TrainConfig,
    out_dir: Path,
    *,
    resume: bool = False,
    max_hours: float | None = None,
) -> nn.Module | None:
    """Train from random initialisation, log per-epoch metrics, and keep the best checkpoint.

    With ``max_hours``, stop after the first epoch past which the next one would not fit in
    the budget, and return ``None``: the run is paused, and ``resume=True`` continues it.
    """
    started_session = time.monotonic()
    torch.manual_seed(config.seed)
    random.seed(config.seed)
    device = resolve_device(config.device)
    last_path = out_dir / "last.pt"
    if resume:
        if not last_path.exists():
            raise SystemExit(f"Nothing to resume: no unfinished run in {out_dir}.")
        _check_resumable(out_dir / "config.json", config, classes)
    elif last_path.exists():
        msg = f"{out_dir} holds an unfinished run; pass --resume or choose another --run-name."
        raise SystemExit(msg)
    out_dir.mkdir(parents=True, exist_ok=True)

    train_set = SampleDataset(train_samples, classes, config.image_size, True, config.seed)
    val_set = SampleDataset(val_samples, classes, config.image_size, False, config.seed)
    sampler = _sampler(train_set, config.balance, config.seed)
    sampler_generator = None if sampler is None else sampler.generator
    loader_generator = torch.Generator().manual_seed(config.seed)
    loader = DataLoader(
        train_set,
        batch_size=config.batch_size,
        sampler=sampler,
        shuffle=sampler is None,
        num_workers=config.num_workers,
        drop_last=len(train_set) > config.batch_size,
        generator=loader_generator,
        persistent_workers=False,
    )
    # A resumed run loads its own weights, so it skips the pretrained download.
    model = build_model(len(classes), config.backbone, config.width, pretrained=not resume)
    if config.init_from and not resume:
        initialise_from_run(model, classes, Path(config.init_from), config.backbone)
    model = model.to(device)
    optimiser = torch.optim.AdamW(
        _parameter_groups(model, config), lr=config.learning_rate, weight_decay=config.weight_decay
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
    scaler = torch.amp.grad_scaler.GradScaler("cuda", enabled=use_amp)

    best_accuracy = -1.0
    first_epoch = 0
    if resume:
        # Load on the CPU: the RNG states must stay CPU tensors, and load_state_dict moves the rest.
        state = torch.load(last_path, map_location="cpu", weights_only=False)
        model.load_state_dict(state["model"])
        optimiser.load_state_dict(state["optimiser"])
        scaler.load_state_dict(state["scaler"])
        schedule.load_state_dict(state["schedule"])
        if sampler_generator is not None:
            sampler_generator.set_state(state["sampler_generator"])
        loader_generator.set_state(state["loader_generator"])
        best_accuracy = state["best_accuracy"]
        first_epoch = state["epoch"]
    else:
        (out_dir / "config.json").write_text(
            json.dumps({**asdict(config), "classes": list(classes)}, indent=2), encoding="utf-8"
        )
    with (out_dir / "history.jsonl").open("a" if resume else "w", encoding="utf-8") as history:
        for epoch in range(first_epoch, config.epochs):
            model.train()
            train_set.epoch = epoch
            started = time.monotonic()
            running_loss = 0.0
            for step, (images, labels) in enumerate(loader, start=1):
                images, labels = images.to(device), labels.to(device)
                optimiser.zero_grad(set_to_none=True)
                with torch.autocast(device.type, dtype=torch.float16, enabled=use_amp):
                    loss = loss_fn(model(images), labels)
                scaler.scale(loss).backward()
                scaler.step(optimiser)
                scaler.update()
                schedule.step()
                running_loss += float(loss.item())
                if step % PROGRESS_EVERY == 0:
                    _log_progress(epoch, config.epochs, step, len(loader), started)
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
            if epoch + 1 == config.epochs:
                break
            state = {
                "epoch": epoch + 1,
                "best_accuracy": best_accuracy,
                "model": model.state_dict(),
                "optimiser": optimiser.state_dict(),
                "scaler": scaler.state_dict(),
                "schedule": schedule.state_dict(),
                "sampler_generator": (
                    None if sampler_generator is None else sampler_generator.get_state()
                ),
                "loader_generator": loader_generator.get_state(),
            }
            partial = last_path.with_suffix(".pt.partial")
            torch.save(state, partial)
            partial.replace(last_path)  # a kill mid-save leaves the previous last.pt intact
            if max_hours is not None:
                elapsed = time.monotonic() - started_session
                if elapsed + record["seconds"] > max_hours * 3600:
                    return None
    last_path.unlink(missing_ok=True)
    model.load_state_dict(torch.load(out_dir / "best.pt", map_location=device, weights_only=True))
    return model


def _parameter_groups(model: nn.Module, config: TrainConfig) -> list[dict[str, object]]:
    if config.backbone == "countrynet":
        return [{"params": list(model.parameters())}]
    head = list(model.get_submodule("head").parameters())
    head_ids = {id(p) for p in head}
    body = [p for p in model.parameters() if id(p) not in head_ids]
    return [
        {"params": body},
        {"params": head, "lr": config.learning_rate * config.head_lr_scale},
    ]


def _check_resumable(config_path: Path, config: TrainConfig, classes: Sequence[str]) -> None:
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    current = {**asdict(config), "classes": list(classes)}
    defaults = asdict(TrainConfig())  # runs paused before a setting existed used its default
    changed = sorted(
        key
        for key in current.keys() - RESUMABLE_CHANGES
        if saved.get(key, defaults.get(key)) != current[key]
    )
    if changed:
        msg = f"Cannot resume: settings differ from the paused run: {', '.join(changed)}."
        raise SystemExit(msg)


def _log_progress(epoch: int, epochs: int, step: int, steps: int, started: float) -> None:
    elapsed = time.monotonic() - started
    remaining = elapsed / step * (steps - step)
    print(
        f"epoch {epoch + 1}/{epochs} step {step}/{steps}: {elapsed / step:.3f} s/step, "
        f"about {remaining / 60:.0f} min left in this epoch",
        file=sys.stderr,
        flush=True,
    )

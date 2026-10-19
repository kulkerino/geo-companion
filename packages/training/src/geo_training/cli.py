"""``geo-train``: dataset statistics and a full train → calibrate → evaluate → export run.

Nothing here downloads data. Every input path is local, the dataset ledger must be
``cleared``, and every output goes to the application-data directory, never this repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from geo_companion.paths import application_data_dir, is_inside_repository

from geo_training.ledger import load_record, require_cleared
from geo_training.metadata import read_samples
from geo_training.splits import select_classes, split_train_val


def _output_dir(value: str | None, run_name: str) -> Path:
    path = Path(value) if value else application_data_dir() / "training" / "runs" / run_name
    if is_inside_repository(path):
        msg = f"Refusing to write training output inside the repository: {path}"
        raise SystemExit(msg)
    return path


def _stats(args: argparse.Namespace) -> int:
    require_cleared(load_record(Path(args.ledger)))
    samples = list(read_samples(Path(args.metadata), Path(args.images)))
    train, val = split_train_val(samples, args.val_fraction)
    counts = Counter(sample.country for sample in train)
    summary = {
        "images": len(samples),
        "train": len(train),
        "val": len(val),
        "countries": len(counts),
        "countries_with_min_count": len(select_classes(train, args.min_count)),
        "top_countries": counts.most_common(20),
    }
    print(json.dumps(summary, indent=2))
    return 0


def _run(args: argparse.Namespace) -> int:
    import torch

    from geo_training.calibration import choose_threshold, fit_temperature
    from geo_training.evaluate import report
    from geo_training.export import export_onnx, write_manifest
    from geo_training.train import SampleDataset, TrainConfig, predict_logits, resolve_device
    from geo_training.train import train as train_model

    record = require_cleared(load_record(Path(args.ledger)))
    out_dir = _output_dir(args.out, args.run_name)
    samples = list(read_samples(Path(args.metadata), Path(args.images)))
    train_samples, val_samples = split_train_val(samples, args.val_fraction)
    classes = select_classes(train_samples, args.min_count)
    if len(classes) < 2:
        raise SystemExit("Fewer than two countries reach --min-count; nothing to train.")
    config = TrainConfig(
        image_size=args.image_size,
        width=args.width,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        seed=args.seed,
        num_workers=args.workers,
        device=args.device,
    )
    model = train_model(train_samples, val_samples, classes, config, out_dir)
    device = resolve_device(config.device)

    val_set = SampleDataset(val_samples, classes, config.image_size, False, config.seed)
    val_logits, val_labels = predict_logits(model, val_set, config.batch_size, device, args.workers)
    temperature = fit_temperature(val_logits, val_labels)
    abstention = choose_threshold(
        (val_logits / temperature).softmax(1), val_labels, args.target_precision
    )
    majority = Counter(s.country for s in train_samples if s.country in classes).most_common(1)
    majority_country = majority[0][0]
    reports = {
        "val": report(
            val_logits, val_labels, classes, temperature, abstention.threshold, majority_country,
            sum(1 for s in val_samples if s.country not in classes),
        )
    }
    if args.test_metadata:
        test_samples = list(read_samples(Path(args.test_metadata), Path(args.test_images)))
        test_set = SampleDataset(test_samples, classes, config.image_size, False, config.seed)
        test_logits, test_labels = predict_logits(
            model, test_set, config.batch_size, device, args.workers
        )
        reports["test"] = report(
            test_logits, test_labels, classes, temperature, abstention.threshold,
            majority_country, sum(1 for s in test_samples if s.country not in classes),
        )
    (out_dir / "report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")

    artifact = out_dir / "model.onnx"
    parity = export_onnx(model, config.image_size, artifact)
    if parity > 1e-3:
        raise SystemExit(f"ONNX output differs from PyTorch by {parity:.2e}; not exporting.")
    summary = reports.get("test", reports["val"])
    write_manifest(
        model_id=args.model_id,
        version=args.version,
        artifact=artifact,
        classes=classes,
        input_size=config.image_size,
        temperature=temperature,
        abstain_below=abstention.threshold,
        dataset=record,
        evaluation={k: v for k, v in summary.items() if k != "per_country"},
        path=out_dir / "manifest.json",
    )
    torch.save(model.state_dict(), out_dir / "final.pt")
    print(json.dumps({"out_dir": str(out_dir), "onnx_parity": parity, **summary}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="geo-train", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--ledger", required=True, help="dataset rights record (JSON)")
        sub.add_argument("--metadata", required=True, help="train metadata CSV")
        sub.add_argument("--images", required=True, help="directory of <id>.jpg train images")
        sub.add_argument("--val-fraction", type=float, default=0.05)
        sub.add_argument("--min-count", type=int, default=50)

    stats = commands.add_parser("stats", help="summarise the locally available dataset")
    common(stats)
    stats.set_defaults(handler=_stats)

    run = commands.add_parser("run", help="train, calibrate, evaluate and export")
    common(run)
    run.add_argument("--test-metadata")
    run.add_argument("--test-images")
    run.add_argument("--out", help="output directory (default: application data)")
    run.add_argument("--run-name", default="m1")
    run.add_argument("--model-id", default="country-net")
    run.add_argument("--version", default="0.1.0")
    run.add_argument("--image-size", type=int, default=224)
    run.add_argument("--width", type=int, default=64)
    run.add_argument("--epochs", type=int, default=30)
    run.add_argument("--batch-size", type=int, default=128)
    run.add_argument("--learning-rate", type=float, default=2e-3)
    run.add_argument("--target-precision", type=float, default=0.8)
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--workers", type=int, default=4)
    run.add_argument("--device", default="auto")
    run.set_defaults(handler=_run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run" and bool(args.test_metadata) != bool(args.test_images):
        print("--test-metadata and --test-images go together.", file=sys.stderr)
        return 2
    result: int = args.handler(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())

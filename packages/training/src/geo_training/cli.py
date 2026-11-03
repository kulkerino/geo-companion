"""``geo-train``: fetch OSV-5M, dataset statistics, a full train → calibrate → evaluate →
export run, and a local photo pack of practice rounds from the held-out test photos.

Only ``fetch`` touches the network, and only when run by hand. Training reads local paths,
the dataset ledger must be ``cleared``, and every output goes to the application-data
directory, never this repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from geo_companion.contracts import RightsStatus
from geo_companion.geoguessr_countries import GEOGUESSR_COUNTRIES
from geo_companion.paths import application_data_dir, is_inside_repository

from geo_training.fetch import (
    OSV5M_BASE_URL,
    download,
    extract_images,
    filter_metadata,
    list_remote_files,
    parse_shards,
    print_progress,
    shard_paths,
)
from geo_training.ledger import load_record, require_cleared
from geo_training.mapillary import WEAK_COUNTRIES
from geo_training.metadata import read_samples
from geo_training.splits import deterministic_subset, select_classes, split_train_val


def _output_dir(value: str | None, run_name: str) -> Path:
    path = Path(value) if value else application_data_dir() / "training" / "runs" / run_name
    if is_inside_repository(path):
        msg = f"Refusing to write training output inside the repository: {path}"
        raise SystemExit(msg)
    return path


def _dataset_dir(value: str | None) -> Path:
    path = Path(value) if value else application_data_dir() / "datasets" / "osv5m"
    if is_inside_repository(path):
        msg = f"Refusing to store datasets inside the repository: {path}"
        raise SystemExit(msg)
    return path


def _extracted_marker(root: Path, path: str, sha256: str) -> int | None:
    """Image count of an archive that was unpacked and deleted, if its hash still matches."""
    marker = root / "raw" / f"{path}.extracted.json"
    if not marker.is_file():
        return None
    record = json.loads(marker.read_text(encoding="utf-8"))
    return int(record["images"]) if record.get("sha256") == sha256 else None


def _fetch(args: argparse.Namespace) -> int:
    load_record(Path(args.ledger))  # the rights record must exist before anything is fetched
    root = _dataset_dir(args.data_dir)
    root.mkdir(parents=True, exist_ok=True)
    published = list_remote_files(args.base_url)
    plan = {
        "train": shard_paths("train", parse_shards(args.train_shards)),
        "test": shard_paths("test", parse_shards(args.test_shards)),
    }
    wanted = [path for paths in plan.values() for path in paths]
    wanted += [f"{split}.csv" for split, paths in plan.items() if paths]
    unknown = [path for path in wanted if path not in published]
    if unknown:
        raise SystemExit(f"Not published in the dataset: {', '.join(unknown)}")
    total = sum(published[path].size for path in wanted)
    print(f"Fetching {len(wanted)} files, {total / 1e9:.1f} GB, into {root}", file=sys.stderr)
    for path in wanted:
        if _extracted_marker(root, path, published[path].sha256) is not None:
            continue  # unpacked earlier and its archive deleted
        download(
            published[path],
            f"{args.base_url}/resolve/main/{path}",
            root / "raw" / path,
            root / "fetch-log.jsonl",
            print_progress,
        )
    summary: dict[str, dict[str, int]] = {}
    for split, paths in plan.items():
        if not paths:
            continue
        image_dir = root / "images" / split
        extracted = 0
        for path in paths:
            marker = _extracted_marker(root, path, published[path].sha256)
            if marker is not None:
                extracted += marker
                continue
            count = extract_images(root / "raw" / path, image_dir)
            extracted += count
            if args.delete_archives:
                marker_path = root / "raw" / f"{path}.extracted.json"
                marker_path.write_text(
                    json.dumps({"sha256": published[path].sha256, "images": count}),
                    encoding="utf-8",
                )
                (root / "raw" / path).unlink()
        (root / "metadata").mkdir(exist_ok=True)
        rows = filter_metadata(
            root / "raw" / f"{split}.csv", image_dir, root / "metadata" / f"{split}.csv"
        )
        summary[split] = {"images": extracted, "metadata_rows": rows}
    print(json.dumps({"data_dir": str(root), **summary}, indent=2))
    return 0


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


def _photo_pack(args: argparse.Namespace) -> int:
    from geo_training.photo_pack import build_photo_pack, read_photo_records, select_photos

    record = require_cleared(load_record(Path(args.ledger)))
    out = (
        Path(args.out)
        if args.out
        else application_data_dir() / "packs" / args.pack_id / args.version
    )
    if is_inside_repository(out):
        raise SystemExit(f"Refusing to write a pack inside the repository: {out}")
    if (out / "pack.json").exists():
        raise SystemExit(f"{out} already holds a pack; packs are immutable, bump --version.")
    records = read_photo_records(Path(args.metadata), Path(args.images))
    photos = select_photos(records, args.rounds, args.min_count, args.seed)
    if not photos:
        raise SystemExit("No photos match; check --metadata, --images and --min-count.")
    local = build_photo_pack(
        record, photos, out, pack_id=args.pack_id, version=args.version, seed=args.seed
    )
    countries = len({round_.answer.country_code for round_ in local.pack.practice_rounds})
    print(f"Wrote {len(photos)} photo rounds from {countries} countries to {out / 'pack.json'}")
    return 0


def _run(args: argparse.Namespace) -> int:
    import torch

    from geo_training.calibration import (
        CALIBRATION_POWERS,
        choose_threshold,
        class_weights,
        fit_temperature,
    )
    from geo_training.evaluate import report
    from geo_training.export import export_onnx, write_manifest
    from geo_training.train import SampleDataset, TrainConfig, predict_logits, resolve_device
    from geo_training.train import train as train_model

    record = require_cleared(load_record(Path(args.ledger)))
    out_dir = _output_dir(args.out, args.run_name)
    samples = deterministic_subset(
        list(read_samples(Path(args.metadata), Path(args.images))), args.max_images
    )
    for metadata, images, ledger in zip(
        args.extra_metadata or [], args.extra_images or [], args.extra_ledger or [], strict=True
    ):
        extra = load_record(Path(ledger))
        if extra.rights_status is RightsStatus.QUARANTINED:
            raise SystemExit(f"Dataset {extra.dataset_id!r} is quarantined; it cannot be used.")
        samples += read_samples(Path(metadata), Path(images))
        # Each extra set is named in the model's attribution, which the app shows.
        record = type(record).model_validate(
            {
                **record.model_dump(),
                "attribution_text": f"{record.attribution_text} Also trained on "
                f"{extra.source_title} ({extra.license_name}), privately.",
            }
        )
    if args.geoguessr_only:
        samples = [s for s in samples if s.country in GEOGUESSR_COUNTRIES]
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
        init_from=args.init_from,
        backbone=args.backbone,
    )
    model = train_model(
        train_samples, val_samples, classes, config, out_dir,
        resume=args.resume, max_hours=args.max_hours,
    )  # fmt: skip
    if model is None:
        done = len((out_dir / "history.jsonl").read_text(encoding="utf-8").splitlines())
        print(
            f"Paused after epoch {done} of {config.epochs}. Run the same command with --resume "
            "to continue.",
            file=sys.stderr,
        )
        return 0
    device = resolve_device(config.device)

    val_set = SampleDataset(val_samples, classes, config.image_size, False, config.seed)
    val_logits, val_labels = predict_logits(model, val_set, config.batch_size, device, args.workers)
    weights = class_weights(val_labels, CALIBRATION_POWERS[args.calibration])
    temperature = fit_temperature(val_logits, val_labels, weights)
    abstention = choose_threshold(
        (val_logits / temperature).softmax(1), val_labels, args.target_precision, weights
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
    split = "test" if "test" in reports else "val"
    summary = {**reports[split], "split": split, "calibration": args.calibration}
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


def _import_style(args: argparse.Namespace) -> int:
    from geo_training.geoguessr_style import REPOS, import_sets

    root = (
        Path(args.data_dir)
        if args.data_dir
        else application_data_dir() / "datasets" / "geoguessr-style"
    )
    if is_inside_repository(root):
        raise SystemExit(f"Refusing to store datasets inside the repository: {root}")
    names = [name.strip() for name in args.sets.split(",") if name.strip()]
    unknown = [name for name in names if name not in REPOS]
    if unknown:
        raise SystemExit(f"Unknown sets: {', '.join(unknown)}; choose from {', '.join(REPOS)}.")
    summary = import_sets(root, names, offline=args.offline)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_country"}, indent=2))
    return 0


def _import_mapillary(args: argparse.Namespace) -> int:
    from geo_training.mapillary import choose_seeds, import_mapillary, read_token

    app_dir = application_data_dir()
    root = Path(args.data_dir) if args.data_dir else app_dir / "datasets" / "mapillary"
    if is_inside_repository(root):
        raise SystemExit(f"Refusing to store datasets inside the repository: {root}")
    seed_metadata = (
        Path(args.seed_metadata)
        if args.seed_metadata
        else _dataset_dir(None) / "metadata" / "train.csv"
    )
    countries = [c.strip().upper() for c in args.countries.split(",") if c.strip()] or None
    weak = [c.strip().upper() for c in args.weak.split(",") if c.strip()]
    seeds = choose_seeds(seed_metadata, args.seeds_per_country, weak, args.weak_factor, countries)
    client_token = None if args.offline else read_token(Path.home())
    summary = import_mapillary(root, seeds, client_token, args.per_seed)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_country"}, indent=2))
    return 0


def _regrade(args: argparse.Namespace) -> int:
    """Re-measure a finished run as the app now uses it: GeoGuessr countries only."""
    import torch

    from geo_training.evaluate import report, restrict_classes
    from geo_training.model import build_model
    from geo_training.train import SampleDataset, predict_logits, resolve_device

    run_dir = Path(args.run_dir)
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    classes: list[str] = config["classes"]
    device = resolve_device(args.device)
    backbone = config.get("backbone", "countrynet")
    model = build_model(len(classes), backbone, config["width"], pretrained=False)
    model.load_state_dict(torch.load(run_dir / "final.pt", map_location="cpu"))
    model.to(device)
    samples = list(read_samples(Path(args.test_metadata), Path(args.test_images)))
    dataset = SampleDataset(samples, classes, config["image_size"], False, config["seed"])
    logits, labels = predict_logits(model, dataset, args.batch_size, device, args.workers)
    logits, labels, kept, dropped = restrict_classes(logits, labels, classes, GEOGUESSR_COUNTRIES)
    majority_index = int(torch.bincount(labels, minlength=len(kept)).argmax())
    result = report(
        logits, labels, kept, manifest["temperature"], manifest["abstain_below"],
        kept[majority_index],
        sum(1 for s in samples if s.country in GEOGUESSR_COUNTRIES and s.country not in classes),
    )  # fmt: skip
    result["dropped_non_geoguessr_images"] = dropped
    # Images of countries the model never learned are misses, not exclusions, on a benchmark.
    graded = int(result.get("images", 0))
    unknown = int(result.get("out_of_label_set", 0))
    if graded + unknown:
        result["top1_all_images"] = round(
            float(result.get("top1", 0.0)) * graded / (graded + unknown), 4
        )
    out = run_dir / args.out_name
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    summary = {k: v for k, v in result.items() if k != "per_country"}
    print(json.dumps({"written": str(out), **summary}, indent=2))
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

    fetch = commands.add_parser("fetch", help="download and unpack OSV-5M shards (network)")
    fetch.add_argument("--ledger", required=True, help="dataset rights record (JSON)")
    fetch.add_argument("--train-shards", default="0-2", help='e.g. "0-2" or "0,5"; "" for none')
    fetch.add_argument("--test-shards", default="0-4", help='e.g. "0-4"; "" for none')
    fetch.add_argument("--data-dir", help="dataset directory (default: application data)")
    fetch.add_argument(
        "--delete-archives",
        action="store_true",
        help="delete each image zip once unpacked (saves ~2.5 GB per shard)",
    )
    fetch.add_argument("--base-url", default=OSV5M_BASE_URL, help=argparse.SUPPRESS)
    fetch.set_defaults(handler=_fetch)

    stats = commands.add_parser("stats", help="summarise the locally available dataset")
    common(stats)
    stats.set_defaults(handler=_stats)

    pack = commands.add_parser(
        "photo-pack", help="build a local photo pack of practice rounds from test photos"
    )
    pack.add_argument("--ledger", required=True, help="dataset rights record (JSON)")
    pack.add_argument("--metadata", required=True, help="test metadata CSV (never train)")
    pack.add_argument("--images", required=True, help="directory of <id>.jpg test images")
    pack.add_argument("--rounds", type=int, default=200)
    pack.add_argument("--min-count", type=int, default=50, help="photos a country needs")
    pack.add_argument("--pack-id", default="osv5m-test-photos")
    pack.add_argument("--version", default="1.0.0")
    pack.add_argument("--seed", type=int, default=0)
    pack.add_argument("--out", help="pack directory (default: application data)")
    pack.set_defaults(handler=_photo_pack)

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
    run.add_argument(
        "--backbone",
        default="countrynet",
        help="countrynet (from scratch), clip-b16 or convnext-t (pretrained), or timm:<name>",
    )
    run.add_argument("--epochs", type=int, default=30)
    run.add_argument("--batch-size", type=int, default=128)
    run.add_argument("--learning-rate", type=float, default=2e-3)
    run.add_argument("--target-precision", type=float, default=0.8)
    run.add_argument(
        "--max-images", type=int, help="use a fixed hashed subset of the train images (smoke runs)"
    )
    run.add_argument(
        "--calibration",
        choices=("sqrt", "balanced", "natural"),
        default="sqrt",
        help="class weighting of val for temperature and threshold; sqrt matches the sampler",
    )
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--workers", type=int, default=4)
    run.add_argument("--device", default="auto")
    run.add_argument(
        "--resume", action="store_true", help="continue the paused or killed run of this name"
    )
    run.add_argument(
        "--max-hours",
        type=float,
        help="pause after the last epoch that fits in this many hours; continue with --resume",
    )
    run.add_argument(
        "--extra-metadata",
        action="append",
        help="another train CSV added after --max-images; repeat for several sets",
    )
    run.add_argument(
        "--extra-images", action="append", help="directory of <id>.jpg for each --extra-metadata"
    )
    run.add_argument(
        "--extra-ledger", action="append", help="rights record of each extra set (not quarantined)"
    )
    run.add_argument(
        "--init-from",
        help="fine-tune from a finished run folder (e.g. M1c) instead of random weights",
    )
    run.add_argument(
        "--geoguessr-only",
        action="store_true",
        help="train only on countries with official GeoGuessr coverage",
    )
    run.set_defaults(handler=_run)

    regrade = commands.add_parser(
        "regrade", help="re-measure a finished run on GeoGuessr countries only (as the app plays)"
    )
    regrade.add_argument("--run-dir", required=True)
    regrade.add_argument("--test-metadata", required=True)
    regrade.add_argument("--test-images", required=True)
    regrade.add_argument("--batch-size", type=int, default=128)
    regrade.add_argument("--workers", type=int, default=4)
    regrade.add_argument("--device", default="auto")
    regrade.add_argument(
        "--out-name",
        default="report-geoguessr.json",
        help="report file in the run folder, e.g. report-benchmark.json",
    )
    regrade.set_defaults(handler=_regrade)

    style = commands.add_parser(
        "import-geoguessr-style",
        help="download free GeoGuessr-style image sets and build the fixed benchmark (network)",
    )
    style.add_argument("--data-dir", help="default: application data/datasets/geoguessr-style")
    style.add_argument(
        "--sets", default="geoguessr,pano,sean", help="comma-separated: geoguessr, pano, sean"
    )
    style.add_argument(
        "--offline", action="store_true", help="convert files already downloaded, fetch nothing"
    )
    style.set_defaults(handler=_import_style)

    mapillary = commands.add_parser(
        "import-mapillary",
        help="download Mapillary panoramas near OSV-5M spots, cut into views (network, token)",
    )
    mapillary.add_argument("--data-dir", help="default: application data/datasets/mapillary")
    mapillary.add_argument(
        "--seed-metadata", help="OSV-5M train CSV to take seed spots from (default: fetched)"
    )
    mapillary.add_argument("--seeds-per-country", type=int, default=60)
    mapillary.add_argument("--per-seed", type=int, default=3, help="panoramas kept per seed")
    mapillary.add_argument(
        "--weak", default=",".join(WEAK_COUNTRIES), help="countries that get more seeds"
    )
    mapillary.add_argument("--weak-factor", type=int, default=3)
    mapillary.add_argument("--countries", default="", help="only these (default: all GeoGuessr)")
    mapillary.add_argument(
        "--offline", action="store_true", help="convert what is downloaded, fetch nothing"
    )
    mapillary.set_defaults(handler=_import_mapillary)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run" and bool(args.test_metadata) != bool(args.test_images):
        print("--test-metadata and --test-images go together.", file=sys.stderr)
        return 2
    extra = ("extra_metadata", "extra_images", "extra_ledger")
    if args.command == "run" and len({len(getattr(args, name) or []) for name in extra}) > 1:
        print(
            "Give --extra-metadata, --extra-images and --extra-ledger once each per extra set.",
            file=sys.stderr,
        )
        return 2
    result: int = args.handler(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())

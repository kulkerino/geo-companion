# Runbook: GeoGuessr benchmark and fine-tuning (desktop PC)

First measure how the
current model does on images that look like GeoGuessr, then fine-tune it on them and measure
again on the same benchmark. Everything runs in PowerShell from the repository folder. Data
and runs stay in `%LOCALAPPDATA%\geo-companion`, never in the repository.

```powershell
uv sync --group training          # adds pyarrow for the parquet files
$D = "$env:LOCALAPPDATA\geo-companion\datasets\osv5m"
$G = "$env:LOCALAPPDATA\geo-companion\datasets\geoguessr-style"
$R = "$env:LOCALAPPDATA\geo-companion\training\runs\m1c"
```

## 1. Download the GeoGuessr-style sets and build the benchmark (about 10 GB)

```powershell
uv run geo-train import-geoguessr-style
```

Downloads three free Hugging Face sets (GeoGuessr screenshots, Street View panoramas, Southeast
Asia), keeps the 109 GeoGuessr countries, cuts each panorama into four views, drops duplicate
images, and writes `$G\metadata\train.csv` and `$G\metadata\benchmark.csv`. Re-running is
safe; downloaded files are verified and skipped. `--offline` re-converts without network.
`$G\import-summary.json` lists images per country.

The benchmark is never trained on. Every model is scored on exactly this file.

## 2. Score the current model (minutes)

```powershell
uv run geo-train regrade --run-dir $R --test-metadata $G\metadata\benchmark.csv --test-images $G\images --out-name report-benchmark.json --workers 8
```

Read `top1_all_images` first: images from countries the model never learned count as misses.

## 3. Route A: fine-tune (about 1 hour)

150k OSV photos (GeoGuessr countries only) plus all GeoGuessr-style training images, starting
from the current model's weights with a low learning rate:

```powershell
uv run geo-train run --ledger docs/sources/osv5m.json --metadata $D\metadata\train.csv --images $D\images\train --max-images 150000 --geoguessr-only --extra-metadata $G\metadata\train.csv --extra-images $G\images --extra-ledger docs/sources/geoguessr-style.json --init-from $R --test-metadata $G\metadata\benchmark.csv --test-images $G\images --run-name ft-a1 --epochs 6 --learning-rate 3e-4 --min-count 20 --batch-size 128 --workers 8 --device cuda --max-hours 2
uv run geo-train regrade --run-dir "$env:LOCALAPPDATA\geo-companion\training\runs\ft-a1" --test-metadata $G\metadata\benchmark.csv --test-images $G\images --out-name report-benchmark.json --workers 8
```

Compare the two `report-benchmark.json` files. Routes B (retrain) and C (pretrained backbone)
are decided from these numbers.

# 2026-10-19 — Model M1b: first real data (OSV-5M) and a laptop smoke run

## Intent

kulo approved the download ("download whatever is needed", 2026-10-19, on the Linux laptop).
Fetch the first OSV-5M slice reproducibly, clear its rights ledger, compute statistics, and
prove the whole pipeline (train → calibrate → evaluate → ONNX export → app provider) on real
images with a short CPU run.

## Evidence

- Commit: this entry with `geo_training/fetch.py`, the `geo-train fetch` command, its tests,
  the cleared ledger, and the plan/PROGRESS updates on `feature/model-m1`.
- Dataset layout checked through the Hub API (`/api/datasets/osv5m/osv5m/tree/main`): 98
  train zips (~2.5 GB, 50,000 images each), 5 test zips (9.4 GB), `train.csv` (2.9 GB),
  `test.csv` (0.12 GB). Zips are stored (no compression), members `00/<id>.jpg`.
- Commands and results:
  - `uv run --all-groups geo-train fetch --ledger docs/sources/osv5m.json --train-shards 0-2
    --test-shards 0-4` → 10 files, 20.0 GB, every one matching its published SHA-256 and
    logged in `fetch-log.jsonl` (11:54–12:17 UTC). Unpacked 150,000 train and 210,122 test
    images; filtered metadata 150,000 and 210,122 rows. On disk: 19 GB zips, 17 GB images,
    197 MB metadata, all under `~/.local/share/geo-companion/datasets/osv5m`.
  - `docs/sources/osv5m.json` → `rights_status: cleared`, `reviewed_on: 2026-10-19`.
  - `geo-train stats ... --min-count 50` (4.5 s) → 142,575 train / 7,425 val, 204 countries,
    124 with at least 50 images. Top: US 35,532 (25%), DE 7,941, FR 7,063, RU 6,456,
    JP 6,098. The test split has 219 countries; US is 23,875 of 210,122 (11%).
  - Smoke subsets (seed 0) in `metadata/`: `train-smoke-30k.csv`, `test-smoke-20k.csv`.
  - `geo-train run ... --image-size 128 --width 32 --epochs 2 --batch-size 64 --workers 6
    --min-count 20 --device cpu --run-name m1b-smoke` → about 4.5 min per epoch; val top-1
    0.240 then 0.235. Test (17,000 in-label images, 3,000 out of label set, 101 classes):
    top-1 0.113, top-5 0.273, majority (US) baseline 0.131; ECE 0.020 raw, 0.090 after
    temperature 0.65; abstention threshold 0.63 → coverage 1.7%, selective top-1 0.70.
    ONNX parity 1.9e-6.
  - The exported smoke model loads through `OnnxCountryProvider` (hash verified): 12.8 ms per
    image on the laptop CPU, abstains on 198 of 200 test images.
  - `uv run --all-groups pytest -q` → 107 passed; `ruff check .` and `mypy` clean;
    `audit_repository.py --root .` → exit 0.
- Decisions:
  - Downloaded the whole official test split (5 zips), not one shard, so M1c reports on the
    real geographically separated test set. Total 20 GB instead of the estimated 15 GB.
  - Kept the zips next to the images so the hashes can be re-checked; deleting `raw/images`
    frees 19 GB if needed.
  - Cleared the ledger on kulo's download approval.
- Findings (smoke run, not real results):
  - Two CPU epochs on 30k images learn little: below the majority baseline, as expected.
  - Temperature scaling made calibration **worse** on test (0.020 → 0.090). The val split is
    5% of the same train shards, where the US share is 25%, while test is 11% US and drawn
    from separate regions. M1c should calibrate on a split that matches test better (for
    example class-balanced, or a held-out region) and recheck.
- Limitations and external gaps:
  - The Windows RTX machine's GPU is still unknown, so M1c cannot be sized yet.
  - Only 3 of 98 train shards are local; a serious run needs more, on the RTX machine.

## Follow-up

M1c: full training on the RTX machine once kulo names its GPU, with the calibration-split fix.

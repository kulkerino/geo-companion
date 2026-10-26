# Runbook — Model M1c on the Windows RTX 3060 PC

The real training run for Model M1 ([plan](model-m1-plan.md)). The laptop has no CUDA GPU, so
this runs by hand on kulo's desktop with an **NVIDIA RTX 3060 12 GB** (confirmed with
`nvidia-smi` on 2026-10-26). Task 7 later automates it.

Numbers marked *measured* come from this PC on 2026-10-26
([journal](../journal/2026-10-26-model-m1c-rtx-3060.md)). Sections 1–3 are already done
there: uv is installed, the data is fetched and verified, and the smoke run passes. In Git
Bash, uv lives in `~/.local/bin`, which is not on the PATH by default.

## 1. One-time setup (PowerShell)

1. Update the NVIDIA driver (the CUDA 12.8 PyTorch wheels need a recent driver), then check:
   ```powershell
   nvidia-smi
   ```
2. Install Git and uv, then clone the private repository:
   ```powershell
   winget install --id Git.Git -e
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   git clone https://github.com/kulkerino/geo-companion.git
   cd geo-companion
   git switch feature/model-m1
   ```
3. Install the training stack. `pyproject.toml` routes `torch` to the CUDA 12.8 wheels on
   Windows automatically:
   ```powershell
   uv sync --group training
   uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
   ```
   Expect `True` and `NVIDIA GeForce RTX 3060`. If it prints `False`, stop: the driver or the
   wheel is wrong, and training would silently run on the CPU.
4. Run the tests once (about a minute):
   ```powershell
   uv run pytest -q packages/training
   ```

## 2. Fetch data

Data goes to `%LOCALAPPDATA%\geo-companion\datasets\osv5m`, never the repository. Each train
shard is 2.5 GB and 50,000 photos; the full test split is 9.4 GB.

```powershell
uv run geo-train fetch --ledger docs/sources/osv5m.json --train-shards 0-19 --test-shards 0-4 --delete-archives
```

20 train shards give 1,000,000 photos. With `--delete-archives` this needs about **55 GB**
free (unpacked photos plus metadata; the 2.9 GB `train.csv` is kept). Each file is checked
against the SHA-256 Hugging Face publishes and logged in `fetch-log.jsonl`. Re-running the
command is safe: verified files and unpacked shards are skipped.

## 3. GPU smoke run (about 10 minutes, *estimate*)

Proves CUDA, mixed precision and Windows data loading before the long run:

```powershell
$D = "$env:LOCALAPPDATA\geo-companion\datasets\osv5m"
uv run geo-train run --ledger docs/sources/osv5m.json --metadata $D\metadata\train.csv --images $D\images\train --max-images 50000 --run-name m1c-gpu-smoke --model-id country-net --version 0.0.2 --epochs 1 --batch-size 128 --workers 8 --device cuda
```

Watch `nvidia-smi` in a second window. If GPU utilisation stays low (under about 70%), the
CPU cannot decode photos fast enough: raise `--workers` up to the number of CPU cores. If it
runs out of memory, halve `--batch-size`.

*Measured:* one smoke epoch took 160–165 s for about 47,500 train photos (about 300 photos
per second, including the val pass). `nvidia-smi dmon` showed 35–60% GPU use while the photos
were not yet in the page cache, then 85–98%, so with `--workers 11` the GPU is the limit.
Reading the 2.9 GB `train.csv` takes about 3 minutes before each run or resume starts.

## 4. The real run (in sessions while someone is home)

kulo does not leave the PC on unattended, so the run is split into sessions. After every
epoch the full training state is saved to `last.pt`. `--max-hours` pauses the run cleanly
before an epoch that would not fit, and `--resume` continues it with results identical to an
uninterrupted run. The first session:

```powershell
$D = "$env:LOCALAPPDATA\geo-companion\datasets\osv5m"
uv run geo-train run --ledger docs/sources/osv5m.json --metadata $D\metadata\train.csv --images $D\images\train --test-metadata $D\metadata\test.csv --test-images $D\images\test --run-name m1c --model-id country-net --version 0.1.0 --image-size 224 --width 64 --epochs 16 --batch-size 128 --workers 11 --device cuda --max-hours 4
```

Every later session runs the same command with `--resume` added (and any `--max-hours`). The
settings must match the first session, except `--workers` and `--device`. Stopping the
command with Ctrl+C, closing the window or a power cut loses only the epoch in progress. The
session that finishes epoch 16 goes on to calibrate, evaluate on the test split and export.
A progress line with the time left in the epoch is printed every 500 steps.

Before the first session, delete the folder left by the run stopped on 2026-10-26, which
holds only an empty history:
`Remove-Item -Recurse "$env:LOCALAPPDATA\geo-companion\training\runs\m1c"`.

- ResNet-18 layout (width 64, about 11M parameters), 224 px, random initialisation.
- Calibration defaults to `--calibration sqrt`: validation is reweighted to the same class
  prior as the square-root balanced training sampler (see the M1c-prep journal).
- *Estimate from the measured smoke run*: about 300 photos per second, so roughly 50 minutes
  per epoch on 950,000 train photos and **12–14 hours** for 16 epochs, plus the test split
  and export. Epoch 1 reads every photo from disk for the first time and will be the
  slowest. Check `seconds` in `history.jsonl` after epoch 1.
- Output: `%LOCALAPPDATA%\geo-companion\training\runs\m1c\` with `history.jsonl`,
  `report.json` (test results), `model.onnx`, `manifest.json`, and checkpoints.

## 5. Bring the result back

Copy `report.json`, `history.jsonl`, `config.json`, `manifest.json` and `model.onnx` from the
run folder to the laptop's application-data directory
(`~/.local/share/geo-companion/training/runs/m1c/`), never into the repository. The audit
forbids `.onnx` and `.pt` files there. Then on the laptop:

```bash
GEO_COMPANION_MODEL=onnx:$HOME/.local/share/geo-companion/training/runs/m1c/manifest.json uv run --group model uvicorn geo_companion.main:app --host 127.0.0.1 --port 8000
```

The app checks the model's SHA-256 against the manifest before it loads it.

## Known risks

- Windows uses `spawn` for data-loader workers. A synthetic run with `spawn` forced passed on
  Linux, but nothing has run on Windows yet.
- The val split comes from the same shards as training; the test split is geographically
  separate, so expect test accuracy below val accuracy.

# Runbook — Model M1c on the Windows RTX 3060 PC

The real training run for Model M1 ([plan](model-m1-plan.md)). The laptop has no CUDA GPU, so
this runs by hand on kulo's desktop with an **NVIDIA RTX 3060 (12 GB VRAM, assumed: the
desktop card; an 8 GB variant exists, check with `nvidia-smi`)**. Task 7 later automates it.

Every number marked *estimate* comes from the laptop smoke run and published RTX 3060
figures, not from this PC. Replace them with measured values in the M1c journal entry.

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

## 4. The real run (overnight)

```powershell
uv run geo-train run --ledger docs/sources/osv5m.json --metadata $D\metadata\train.csv --images $D\images\train --test-metadata $D\metadata\test.csv --test-images $D\images\test --run-name m1c --model-id country-net --version 0.1.0 --image-size 224 --width 64 --epochs 16 --batch-size 128 --workers 8 --device cuda
```

- ResNet-18 layout (width 64, about 11M parameters), 224 px, random initialisation.
- Calibration defaults to `--calibration sqrt`: validation is reweighted to the same class
  prior as the square-root balanced training sampler (see the M1c-prep journal).
- *Estimate*: 500–900 photos per second, so about 20–35 minutes per epoch on 950,000 train
  photos and **6–9 hours** for 16 epochs. Use the smoke run's `seconds` in
  `history.jsonl` to recompute this before starting.
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

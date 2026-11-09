# 2026-11-09 — Race step 4: laptop timing

## Intent

The laptop half of race step 4 in [`docs/race-mode-plan.md`](../docs/race-mode-plan.md):
measure time per race answer and reliability on the laptop, and check a race end to end in the
app. The desktop half is in the [2026-11-02 entry](2026-11-02-race-with-m1c-desktop.md).

## Evidence

- Code: `main` at `ff4c12a` plus the 2026-11-04 docs branch merged in (no code changes).
- Machine: laptop (Intel Core Ultra 7 155H, 22 threads), CachyOS. ONNX on the CPU.
- Model: **not M1c.** The M1c files live only on the PC, and the PC was not reachable from the
  laptop's network. Instead a short script built an untrained `CountryNet(width=64)` (the
  same ResNet-18 layout as M1c, 11.2M parameters, 101 classes from the m1b-smoke manifest),
  exported it with `geo_training.export.export_onnx` at 224 px, and wrote a manifest based on
  the m1b-smoke one (`model_id` `timing-proxy`, `input_size` 224, `abstain_below` 0, new
  SHA-256). Same graph and input size as M1c, so the timing carries over; the guesses are
  meaningless. Files stayed in a scratch folder, never in the repository.
- Commands and results:
  - `uv run --group training --group model python make_proxy.py <scratch>/proxy
    ~/.local/share/geo-companion/training/runs/m1b-smoke` → `101 11228325`
    (classes, parameters); `model.onnx` 45 MB.
  - `GEO_COMPANION_DATA_DIR=<scratch>/data GEO_COMPANION_PHOTO_PACK=~/.local/share/geo-companion/packs/osv5m-test-photos/1.0.0/pack.json
    GEO_COMPANION_MODEL=onnx:<scratch>/proxy/manifest.json uv run --group model uvicorn
    geo_companion.main:app --host 127.0.0.1 --port 8765` → `GET /api/v1/races/availability`
    `available: true`; `GET /api/v1/models` reports `timing-proxy` 0.0.0,
    `is_placeholder: false`. The scratch data directory kept these races out of kulo's history.
  - The same scripted races as on the desktop (20 races of 5 rounds; start, open each round,
    answer `skipped: true`, time the answer request), run twice:
    - run 1: 100 rounds, 0 errors, 0 model unavailable; median 24.9 ms, p95 31.8 ms, max 33.6 ms
    - run 2: 100 rounds, 0 errors, 0 model unavailable; median 22.1 ms, p95 30.7 ms, max 34.7 ms
  - App on port 8000 plus `pnpm --dir apps/web dev`: in the browser, Race the model → Start
    race showed "Round 1 of 5 · racing timing-proxy 0.0.0" and "The model is ready. Its guess
    stays hidden until you answer."; Skip revealed the answer, "You skipped. +0" and the
    model's guess with its top 3.
- Decisions:
  - The laptop is fast enough to run the race model itself (median about 23 ms, slightly
    faster than the desktop's 33 ms). So the laptop/desktop question in the plan is settled:
    races and the projector mode run on the laptop, no desktop needed.
- Limitations and external gaps:
  - Not M1c: accuracy and abstention were not tested on the laptop, only speed and
    reliability. Timing is for the CPU at whatever power profile the laptop was on.
  - No races played by a person yet.
  - The scripts (`make_proxy.py`, `race_timing.py`) were scratch files and are not committed.

## Follow-up

Copy M1c's `model.onnx`, `manifest.json`, `report.json`, `history.jsonl` and `config.json`
from the PC to `~/.local/share/geo-companion/training/runs/m1c/` (runbook section 5), start the
app with `GEO_COMPANION_MODEL=onnx:.../m1c/manifest.json`, and kulo plays a few real races.

# 2026-11-02 — Race step 4: race with M1c (desktop half)

## Intent

Race step 4 of [`docs/race-mode-plan.md`](../docs/race-mode-plan.md): load the M1c model in
the app, measure time per photo and reliability, and record the numbers. This entry covers the
RTX 3060 desktop only. The laptop half and races played by a person are still to do.

## Evidence

- Code: `main` at `03fef73`, a clean clone on the desktop (no code changes in this step).
- Machine: AMD Ryzen 5 5600 (6 cores), Windows 11. The app runs ONNX on the CPU
  (`CPUExecutionProvider`, onnxruntime 1.31.0), so the GPU plays no part in a race.
- Model: M1c, `country-net` 0.1.0 (test top-1 0.645, see the
  [M1c journal](2026-10-26-model-m1c-rtx-3060.md)); photo pack `osv5m-test-photos` 1.0.0.
- Commands and results:
  - `GEO_COMPANION_DATA_DIR=<scratch dir> GEO_COMPANION_PHOTO_PACK=<pack.json>
    GEO_COMPANION_MODEL=onnx:<m1c manifest.json> uv run --group model uvicorn
    geo_companion.main:app --host 127.0.0.1 --port 8765` → starts; `GET /api/v1/models`
    reports `country-net` 0.1.0, `is_placeholder: false`; `GET /api/v1/races/availability`
    → `available: true`. A scratch data directory kept these test races out of kulo's own
    history.
  - A script played 20 races of 5 rounds through the API (start, open each round, answer
    with `skipped: true`, so only the model scores):
    100 rounds, 0 errors, 0 rounds with the model unavailable, model right on 51 of 100.
    Time for the answer request (practice submit + model prediction + scoring):
    median 32.9 ms, p95 54.0 ms, max 71.1 ms.
  - 200 held-out test photos that are not in the pack, sent to `POST /api/v1/photo-guesses`:
    median 17.1 ms, p95 38.7 ms, max 106.1 ms end to end; the model abstained on 26.
- Decisions:
  - On the desktop the model is far below anything a player would notice (under 0.1 s per
    round). The laptop/desktop choice now depends only on the laptop numbers.
- Limitations and external gaps:
  - The races were scripted (the "player" always skips), so they test reliability and
    timing, not a human against the model. 51/100 on pack rounds is lower than test top-1
    because the pack spreads rounds over countries, including weak ones.
  - Not measured on the laptop: the M1c files live only on the desktop
    (`%LOCALAPPDATA%\geo-companion\training\runs\m1c\`) until copied over (runbook section 5).

## Follow-up

Copy `model.onnx`, `manifest.json`, `report.json`, `history.jsonl` and `config.json` to the
laptop, repeat the timing there, then kulo plays a few real races and the result goes into
this entry.

# 2026-11-02 — Model accuracy page

## Intent

The app could run a real model but gave no way to see how good it is. While M1c finishes on
the RTX 3060 PC, add a read-only "Model accuracy" page that shows the enabled model's
held-out results. It works with the M1b smoke model now and with M1c as soon as that model
is exported.

## Evidence

- Commit: on `feature/model-accuracy-page`, one PR into `main`.
- Decisions:
  - New contract `ModelEvaluation` (with `AbstentionSummary`, `EvaluationBaselines` and
    `CountryAccuracy`) and route `GET /api/v1/models/evaluation`. It returns 404 "No local
    model is enabled." without a model, and 404 "The enabled model has no recorded
    evaluation." for the dummy or a manifest whose summary is incomplete. The model itself
    keeps working in that case.
  - The summary comes only from the manifest, which is bound to the ONNX file by SHA-256.
    The per-country rows come from `report.json` next to it, which is not hashed, so they are
    used only when that report's split matches the manifest summary exactly. Otherwise they
    are left out.
  - `geo-train run` now writes `split` ("test" or "val") into the manifest's evaluation.
    Older manifests without it are matched against the report's `test` split first, then
    `val`.
  - `PredictionProvider` gained `evaluation()`. The dummy returns None, because a
    placeholder has nothing to report.
  - The page names the comparison points in plain words: "Always guessing United States
    (US)" is the majority baseline, plus random guessing. It states that these are past
    results on photos the model never trained on, and that they never change an answer.
  - Regenerated `openapi.json` and `generated.ts` with `generate_api_contract.py`.
- Commands and results (all exit 0 unless noted):
  - `uv lock --check`
  - `uv run pytest -q` → 145 passed. A first run outside the pnpm PATH failed only
    `test_web_bundle_safety`, which needs `pnpm`; it passed with the Codex runtime on PATH.
  - `uv run ruff check .`
  - `uv run mypy` → 24 files, clean (after typing `split` as a Literal).
  - `generate_api_contract.py --check` and `generate_starter_diagrams.py --check`.
  - `pnpm --dir apps/web test` → 13 passed (2 new); `lint`; `typecheck`; `build`.
  - `tools/audit_repository.py --root .`
  - Tests added:
    - `packages/training/tests/test_onnx_provider.py`: summary plus matching rows; a report
      that disagrees adds no rows; an older manifest with no split; the API returns 200, and
      404 for a smoke manifest.
    - `packages/api/tests/test_model_provider.py`: the route is listed, and returns 404 for
      the dummy and with no model.
  - Real app: uvicorn with `GEO_COMPANION_MODEL=onnx:` the M1b smoke manifest and a scratch
    data directory, plus Vite, checked in the browser.
    - The page showed `country-net-smoke 0.0.1` with 17,000 test photos from 101 countries
      (3,000 out of label set), top-1 11.3%, top-5 27.3%, majority (US) 13.1%, answers 1.7%,
      right when it answers 70.1%, and ECE 2.0% → 8.9%.
    - It listed 59 per-country rows, led by United States at 75.1%.
- Limitations and external gaps:
  - The smoke model's ECE gets worse after calibration (2.0% → 8.9%) because its manifest
    predates the sqrt-weighted calibration fix. The page shows what the manifest says. M1c
    will show the fixed calibration.
  - Per-country rows include only countries with at least 50 test photos (the threshold in
    `evaluate.report`).

## Follow-up

When M1c is exported, start the app with its manifest and check this page against its
`report.json`. Then do the independent M1 review.

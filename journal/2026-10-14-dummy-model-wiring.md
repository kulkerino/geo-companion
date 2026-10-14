# 2026-10-14 — Wire the app to a dummy model

## Intent

kulo asked for the app to be connected to a dummy model. The point is plumbing. A placeholder
provider exercises the full model path (provider boundary, API, SQLite storage, UI, abstention,
and a no-model fallback) so a real local model can later replace it without changing the app.
It also lets us prove now, with tests, that model output can never leak an answer or be mistaken
for source truth.

## Decisions

- **Provider boundary:** `geo_companion/models.py` defines `PredictionProvider`, whose
  `predict` receives only a `PracticeRoundPublic` (no answer field). The provider therefore
  cannot read or copy the authored answer.
- **Dummy provider:** `DummyProvider` (`dummy-placeholder` 0.1.0, runtime `dummy`,
  `is_placeholder = true`) seeds a PRNG from the model ID, version, round ID, and asset ID. It
  scores a fixed list of 27 European country codes and returns the top three, or abstains when
  the top share is below 0.2. On the starter pack, 9 of 10 rounds produce candidates and 1
  abstains. Any hit is coincidental: round 02 (CZ) happens to rank CZ first, and its
  description says the guesses are not image analysis.
- **Post-answer only:** the only prediction route is
  `GET /api/v1/practice/attempts/{attempt_id}/model-prediction`. It requires an existing
  attempt, so a learner must answer or skip first. There is no route that takes a round ID.
- **Separate from truth:** `ModelPredictionResult.origin` is `model_prediction`. Results are
  stored in their own table, `learner_model_predictions`, once per attempt and model version.
  They never touch the authored answer, attempts, feedback, or scheduling.
- **Optional:** `GET /api/v1/models` reports `{"active": null}` when
  `GEO_COMPANION_MODEL=none`. The prediction route then returns 404 "No local model is
  enabled.", and the UI hides the button. The default is `dummy`; any other value is rejected
  at startup.
- **New contracts:** `ModelInfo` (`required_for_learning` is always false), `ModelStatus`,
  `ModelCandidate`, and `ModelPredictionResult`. The last validates that it abstains exactly
  when there are no candidates, and that candidates are ordered, distinct, and sum to at most 1.
  The Task 2 `ModelManifest` and `ModelPrediction` are unchanged.
- **UI:** after the reveal, a "Compare with model" button shows the model name, a "placeholder,
  not real inference" label, the description, the ranked candidates or an abstention message,
  and a note that model output never changes the authored answer. A failing `/models` call
  hides the feature instead of blocking practice.

## Evidence

- New `packages/api/tests/test_model_provider.py` (12 tests) covers:
  - determinism, labelling, and abstention;
  - that changing the authored answer leaves predictions unchanged;
  - environment selection;
  - rejection of inconsistent candidates (5 cases);
  - the attempt requirement, store-once behaviour, and persistence;
  - the no-model fallback;
  - that OpenAPI exposes exactly two model paths;
  - the API's 404 responses.
- `apps/web/src/App.integration.test.tsx` (real FastAPI + SQLite through the stdio bridge):
  - no compare button before the answer;
  - after the reveal it shows `CH · 27%`, `PT · 19%`, `BG · 13%` with the placeholder label,
    while the authored answer `SK` stays shown;
  - writes a `learner_model_predictions` row;
  - a separate run with `GEO_COMPANION_MODEL=none` practises normally with no button and no
    error.
- Real uvicorn on a fresh data directory, checked with curl:
  - `/api/v1/models` returned the dummy;
  - a CZ answer to round 02 was correct, and its prediction was `model_prediction`, not
    abstained, `[CZ 0.228, BE 0.208, IT 0.089]`;
  - an unknown attempt returned 404;
  - the directory then held only `runtime.sqlite3`.
- Full suite (all exit 0): `uv lock --check`; `uv run pytest -q` → 74 passed; ruff; mypy (8
  files); OpenAPI and diagram `--check`; `pnpm --dir apps/web test` → 7 passed; lint;
  typecheck; build; repository audit.

## Limitations

- The dummy says nothing about the image. It exists to test wiring and the UI only.
- Task 6 still owns real models: ONNX runtime, manifests with artifact hashes, calibration,
  abstention thresholds from evaluation, and benchmarks. No model is downloaded.

## Follow-up

Decide whether to merge PR kulkerino/geo-companion#1. Task 4 (pack lifecycle) is next in the
plan.

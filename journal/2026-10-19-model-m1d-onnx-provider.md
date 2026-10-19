# 2026-10-19 — Model M1d: ONNX country provider in the app

## Intent

While PR #1's merge and the OSV-5M download wait for kulo, build the part of Model M1 that needs
no real data: M1d from [`docs/model-m1-plan.md`](../docs/model-m1-plan.md), the app-side
provider that runs an exported ONNX model behind the existing `PredictionProvider` boundary.

## Evidence

- Commit: this entry with the provider, contract, training and dependency changes on
  `feature/model-m1`.
- What changed:
  - `CountryModelManifest` moved from `geo_training.export` into `geo_companion.contracts`, so
    the app reads manifests without importing PyTorch. It gained `artifact_file` (a bare file
    name next to the manifest, so a manifest cannot point elsewhere on disk), and `classes`
    must be ISO alpha-2 codes. `IMAGE_MEAN`/`IMAGE_STD` live there too.
  - Evaluation preprocessing moved to `geo_companion/image_input.py`; `geo_training.preprocess`
    re-exports it, so training and the app share one implementation.
  - New `geo_companion/onnx_provider.py`: `OnnxCountryProvider` refuses manifests inside the
    repository, a missing artifact, or a SHA-256 mismatch (`ModelIntegrityError`); runs
    onnxruntime on CPU; applies the manifest temperature; returns the top 3 or abstains below
    `abstain_below`. Round images come from a `RoundImageSource`; the default, `NoRasterImages`,
    has none because starter rounds are SVG diagrams, so the model abstains on them.
  - `GEO_COMPANION_MODEL=onnx:<manifest path>` selects it (imported lazily).
  - New optional `model` dependency group (numpy, onnxruntime, pillow) for running a model in
    the app without the training stack.
- Commands and results (Codex-runtime `pnpm`/Node on `PATH`):
  - `uv lock` → resolved 50 packages; `uv lock --check` → up to date.
  - `uv run --all-groups pytest -q packages/training` → 28 passed (9 new provider tests:
    parity with PyTorch incl. temperature, abstention by threshold and for starter rounds,
    post-answer prediction through an image source, tampered artifact refused, three
    `artifact_file` escapes refused, repository paths refused, environment selection).
  - `uv run --all-groups pytest -q` → 102 passed.
  - `uv run --all-groups ruff check .` → one import-order error in the new test, fixed with
    `--fix`, then all checks passed.
  - `uv run --all-groups mypy` → no issues in 21 source files.
  - `generate_api_contract.py --check`, `generate_starter_diagrams.py --check`,
    `audit_repository.py --root .` → exit 0. `pnpm --dir apps/web test|lint|typecheck|build`
    → exit 0.
- Decisions:
  - Abstain when a round has no raster image instead of rasterising the SVG diagrams: the
    model is out of distribution on drawings anyway, and it avoids a new SVG dependency.
- Limitations and external gaps:
  - No real model exists yet; tests use a tiny randomly initialised `CountryNet`.
  - Until photo rounds or photo upload exist, the real model always abstains in the app.
  - Stored predictions are keyed by model id and version, not by artifact hash, so a retrained
    model must get a new version number.

## Follow-up

M1b (OSV-5M download and ledger clearing) waits for kulo's approval; PR #1 waits for kulo's
merge confirmation. Photo rounds or upload are the natural next app milestone.

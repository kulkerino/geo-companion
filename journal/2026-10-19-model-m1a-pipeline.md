# 2026-10-19 — Model M1a: training pipeline on synthetic images

## Intent

Pick up the cut-off session of 2026-10-16. kulo said "do whatever you see fit" and asked for
the branches to be merged and tidied. Plan: merge PR #1 if green, tidy stale branches, then
finish M1a from [`docs/model-m1-plan.md`](../docs/model-m1-plan.md): PyTorch as an optional
`training` dependency group and the full pipeline tested on synthetic images, with no real
data downloaded.

## Evidence

- Commit: this entry, `PROGRESS.md`, `pyproject.toml`, `uv.lock`, `paths.py`,
  `docs/sources/osv5m.json` and `packages/training/` together on `feature/model-m1`.
- What was already on disk (uncommitted from the previous session): the `geo_training`
  package (ledger gate, metadata loader, grouped split, `CountryNet`, training loop,
  temperature calibration, abstention threshold, evaluation, ONNX export with a hash-bound
  manifest, `geo-train` CLI with `stats` and `run`), its tests, the OSV-5M ledger entry
  (`rights_status: quarantined`, so training refuses it), and the `training` dependency group
  (torch CPU wheels on Linux, CUDA 12.8 wheels on Windows, onnx, onnxruntime, pillow, numpy).
- Commands and results:
  - `gh pr checks 1` → `verify` pass. `gh pr merge 1 --merge` → **refused** by the session's
    permission guard (merging into `main` needs kulo's own confirmation in the thread). PR #1
    is still open; asked kulo.
  - `uv lock --check` → resolved 50 packages, lock up to date.
  - `uv run --group training python -c "import torch, onnx, onnxruntime"` → torch 2.14.1+cpu,
    onnx 1.23.2, onnxruntime 1.31.0.
  - First `uv run --all-groups ruff check .` → 5 errors (import order, two long lines);
    first `uv run --all-groups mypy` → 3 errors (complex dtype inferred in
    `preprocess._normalise`, untyped `onnxruntime` import, an unused `type: ignore`). Fixed.
  - Training tests now skip when torch is not installed (`collect_ignore_glob` in
    `packages/training/tests/conftest.py`, Pillow imported lazily), so a dev-only environment
    still runs the app tests. Checked with a throwaway dev-only venv: 74 tests collected, the
    training tests skipped.
  - With the Codex-runtime `pnpm`/Node on `PATH`:
    - `uv run --all-groups pytest -q` → 93 passed (19 of them training).
    - `uv run --all-groups ruff check .` → all checks passed.
    - `uv run --all-groups mypy` → no issues in 19 source files.
    - `generate_api_contract.py --check`, `generate_starter_diagrams.py --check`,
      `audit_repository.py --root .` → exit 0.
    - `pnpm --dir apps/web test`, `lint`, `typecheck`, `build` → exit 0.
- Decisions:
  - PyTorch, onnx and onnxruntime live in the optional `training` group; the app never imports
    them. CI already installs every group (`uv sync --frozen --all-groups`).
  - The `codex-workspace` remote stays: it is the documented backup of the old folder.
- Limitations and external gaps:
  - PR #1 is not merged yet, so `main` still lacks Tasks 1–3.
  - Nothing has been downloaded; the OSV-5M ledger stays `quarantined` until kulo approves it.
  - Only a synthetic end-to-end run (32 px, width 8, 4 epochs, CPU) has been exercised; no
    real-image training or timing yet.
  - The Windows RTX machine's GPU is still unknown.

## Follow-up

Merge PR #1 once kulo confirms, then delete `feature/initial-platform`. M1b needs kulo's go
for the OSV-5M download (about 15 GB) and for clearing the ledger.

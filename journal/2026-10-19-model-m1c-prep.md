# 2026-10-19 — Model M1c prep: calibration fix and the RTX 3060 runbook

## Intent

kulo named the training PC's GPU: an RTX 3060. Prepare M1c so it can run there by hand: fix
the calibration problem the M1b smoke run exposed, add what a Windows run needs, and write a
runbook with sized settings.

## Evidence

- Commit: this entry with the calibration, CLI, test, plan and runbook changes on
  `feature/model-m1`.
- What changed:
  - `calibration.class_weights(labels, power)` and weighted `fit_temperature` /
    `choose_threshold`. `geo-train run --calibration {sqrt,balanced,natural}`, default
    `sqrt`, which reweights val to the same square-root class prior the training sampler uses.
    The choice is recorded in the manifest's evaluation summary.
  - `geo-train run --max-images N`: a fixed, hash-chosen subset for smoke runs.
  - `geo-train fetch --delete-archives`: deletes each image zip once unpacked and leaves a
    `<zip>.extracted.json` marker (hash and image count), so re-running skips it.
  - New [`docs/runbook-m1c-rtx-3060.md`](../docs/runbook-m1c-rtx-3060.md): setup, CUDA check,
    fetch of 20 train shards (1M photos, about 55 GB), GPU smoke run, overnight run
    (ResNet-18 layout, 224 px, 16 epochs, batch 128), and how to bring the model back.
- Commands and results:
  - Calibration diagnostic on the M1b smoke model (scratch script, not committed): val logits
    (1,491 images) and test logits (17,000) recomputed from `final.pt`, temperature and
    threshold fitted on val only, ECE measured on test:

    | weighting | temperature | test ECE (raw 0.020) | threshold | test coverage |
    | --- | --- | --- | --- | --- |
    | natural | 0.645 | 0.0895 | 0.628 | 1.65% |
    | sqrt | 1.017 | 0.0226 | 0.519 | 0.06% |
    | balanced | 1.652 | 0.0702 | ≥1 (always abstains) | 0% |

    `sqrt` was picked because it matches the training sampler, not because it scored best;
    the smoke model is too weak and its val too small (1,491 images) for this to be a real
    result. M1c rechecks it with a val of about 50,000 images.
  - A synthetic `geo-train run` with DataLoader workers forced to `spawn` (as on Windows)
    finished on Linux.
  - `uv run --all-groups pytest -q` → 112 passed (5 new: class weights, weighted temperature,
    weighted threshold coverage, hashed subset, fetch with `--delete-archives` run twice).
  - `ruff check .`, `mypy` (22 files), `uv lock --check`, the contract and diagram checks,
    `pnpm --dir apps/web test|lint|typecheck|build`, `audit_repository.py --root .` → all
    passed.
- Decisions:
  - RTX 3060 assumed to be the 12 GB desktop card; the runbook says to confirm with
    `nvidia-smi`.
  - 20 train shards (1M photos) for the first real run, a balance between disk, download time
    and an overnight training run.
- Limitations and external gaps:
  - Nothing has run on Windows or a GPU yet. The throughput and time figures in the runbook
    are estimates.
  - The PC's free disk space and CPU core count are unknown; the runbook explains how to adapt.

## Follow-up

kulo runs the runbook on the PC (or lets a session there run it), then M1c's results come back
for the independent review the plan calls for.

# 2026-10-16 — Plan Model M1 (dataset and from-scratch training)

## Intent

Continue after the dummy-model wiring. kulo's stated next step was a real dataset and a model
trained from scratch, which is the core of the project. This session checked the state of
PR #1, chose a candidate dataset, and wrote a concrete plan. Nothing was downloaded or
installed.

## Evidence

- Commit: this entry together with `docs/model-m1-plan.md` and `PROGRESS.md`, on the new
  branch `feature/model-m1`, which branches from `feature/initial-platform`.
- Commands and results:
  - `gh pr view 1` → OPEN, MERGEABLE, CI `verify` SUCCESS (2026-10-14).
  - Hardware: `lspci` shows Intel Arc (Meteor Lake) and no NVIDIA GPU; `nproc` 22; 14 GB RAM;
    680 GB free on `/home`.
  - The Hugging Face page for `osv5m/osv5m` gives the licence cc-by-sa-4.0 and a size of
    259 GB. The image count, label fields and shard sizes come from the paper and are not yet
    checked against the files.
  - `uv run python tools/audit_repository.py --root .` → exit 0. This is a docs-only change, so the other checks were not rerun.
- Decisions (proposed, waiting for kulo):
  - OSV-5M as the training set, behind a rights-ledger entry that starts `pending` and gates
    training until it is `cleared`.
  - A ResNet-18-style CNN with random initialisation (no pretrained weights) that classifies
    the country.
  - Temperature calibration and an abstention threshold chosen on a val split grouped by
    geographic cell.
  - ONNX export, used through a hash-checked provider.
  - PyTorch as an optional `training` dependency group.
- Limitations and external gaps:
  - The laptop has no CUDA, so real training needs the Windows RTX machine (GPU not known yet).
  - The app's rounds are diagrams, not photos, so the model will be out of distribution in the
    app until photo rounds or photo upload exist.

## Follow-up

kulo answers the five decisions in `docs/model-m1-plan.md`. Then M1a: the pipeline and tests on
synthetic fixtures.

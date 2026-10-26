# Geo Companion — progress

The current state of the project at a glance. Update this file in the same commit as any
work that changes it; detailed evidence for each session goes in [`journal/`](journal/).

**Last updated:** 2026-10-26
**Branch:** `feature/model-m1`, draft [PR #3](https://github.com/kulkerino/geo-companion/pull/3) into `main` (Tasks 1–3 are merged into `main`)
**GitHub:** [kulkerino/geo-companion](https://github.com/kulkerino/geo-companion) (private), remote `origin`; branches `main`, `feature/model-m1`, and the school branch `rocnikovy-projekt`
**Next step:** M1c on kulo's RTX 3060 PC, following [`docs/runbook-m1c-rtx-3060.md`](docs/runbook-m1c-rtx-3060.md); then load the M1c model with the photo pack, and the independent M1 review.

## Task status

| Task | Status | Commit(s) | Journal |
| --- | --- | --- | --- |
| 1. Repository and audit foundation | done, reviewed | `411dbfe`, `ade9730`, `6b1b241` | [2026-10-05](journal/2026-10-05-task-1-repository-audit-foundation.md) |
| 2. Content and application contracts | done, reviewed | `93abbf1`, `70167f1` | [2026-10-05](journal/2026-10-05-task-2-content-application-contracts.md) |
| 3. Standalone offline Open Practice slice | done, self-reviewed | `0ac1ed0`, `7e61cef`, `a6970c1` | [2026-10-14](journal/2026-10-14-task-3-standalone-offline-vertical-slice.md) |
| Dummy-model wiring (interim) | done, self-reviewed | see journal | [2026-10-14](journal/2026-10-14-dummy-model-wiring.md) |
| Model M1: plan | done | see journal | [2026-10-16](journal/2026-10-16-model-m1-plan.md) |
| Model M1a: training pipeline on synthetic images | done, self-reviewed | see journal | [2026-10-19](journal/2026-10-19-model-m1a-pipeline.md) |
| Model M1d: ONNX provider in the app | done, self-reviewed | see journal | [2026-10-19](journal/2026-10-19-model-m1d-onnx-provider.md) |
| Model M1b: first real data and laptop smoke run | done, self-reviewed | see journal | [2026-10-19](journal/2026-10-19-model-m1b-first-real-data.md) |
| Model M1c prep: calibration fix and RTX 3060 runbook | done, self-reviewed | see journal | [2026-10-19](journal/2026-10-19-model-m1c-prep.md) |
| Repository cleanup (no behaviour change) | done, PR #2 merged into `feature/model-m1` | see journal | [2026-10-26](journal/2026-10-26-repo-cleanup.md) |
| Photo rounds from held-out OSV-5M test photos | done, self-reviewed | see journal | [2026-10-26](journal/2026-10-26-photo-rounds.md) |
| Model M1c: real training on the RTX 3060 PC | ready to run by hand | — | — |
| 4. Pack lifecycle and source tooling | planned | — | — |
| 5. Curriculum pipeline | planned | — | — |
| 6. Optional local model | planned | — | — |
| 7. Windows RTX worker | planned | — | — |
| 8. GeoGuessr review adapter | planned | — | — |
| 9. School delivery | planned | — | — |

The full plan is in
[`docs/superpowers/plans/2026-10-05-geoguessr-meta-learning.md`](docs/superpowers/plans/2026-10-05-geoguessr-meta-learning.md).

## What works today

- Open Practice on ten original CC0 diagrams. You get an optional clue, then guess, guess
  marked uncertain, or skip; the answer and explanation are revealed afterwards. You can
  report a problem with an attempt, retry the same round, or move to the next round.
- SM-2 study review ordered by due date, with "practice this round" from the review screen.
- After answering, "Compare with model" shows a model's opinion. The default is a clearly
  labelled placeholder (`dummy-placeholder`, no real inference); `GEO_COMPANION_MODEL=none`
  runs without a model, and `GEO_COMPANION_MODEL=onnx:<manifest>` loads a real exported
  model (see the README).
- Optional photo rounds: `geo-train photo-pack` builds a local pack from held-out OSV-5M
  test photos (opaque ids, metadata stripped, credit and place revealed after the answer),
  and `GEO_COMPANION_PHOTO_PACK=<pack.json>` loads it after hash and rights checks. With an
  ONNX model, "Compare with model" runs on the round's photo.
- Everything runs locally: FastAPI on `127.0.0.1:8000`, Vite on `127.0.0.1:5173`, and SQLite
  in the per-user application-data directory (never inside this folder).

## Decisions log

| Date | Decision | Where recorded |
| --- | --- | --- |
| 2026-10-05 | Original diagrams, not third-party imagery, for the starter pack | plan preflight rulings |
| 2026-10-14 | Knowledge lessons dropped; Task 3 is Open Practice only | plan Task 3 note, Task 3 journal |
| 2026-10-14 | Independent review only at big milestones; a self-review pass otherwise | Task 3 journal |
| 2026-10-14 | Project moved to `~/Documents/geolearn` (the history moved with it) | this file |
| 2026-10-14 | Private GitHub repo `kulkerino/geo-companion` created as `origin` | journal 2026-10-14 move entry |
| 2026-10-14 | Model output is post-answer only, labelled, stored apart from truth; dummy provider first | journal 2026-10-14 dummy model |
| 2026-10-16 | Model work moved ahead of Task 4 (kulo: the model is the core); OSV-5M proposed, pending approval | `docs/model-m1-plan.md` |
| 2026-10-19 | PR #1 merged into `main` (kulo: "merge"); `feature/initial-platform` deleted | journal 2026-10-19 M1d |
| 2026-10-19 | OSV-5M approved and ledger `cleared`; 3 train shards + full test (20 GB) fetched | journal 2026-10-19 M1b |
| 2026-10-19 | Training PC GPU is an RTX 3060; calibration reweights val to the sampler's sqrt prior | journal 2026-10-19 M1c prep |
| 2026-10-19 | PyTorch, onnx, onnxruntime added as the optional `training` group; training tests skip without it | journal 2026-10-19 M1a |
| 2026-10-26 | `.obsidian/` is local editor state and no longer tracked | journal 2026-10-26 cleanup |
| 2026-10-26 | Photo rounds use the OSV-5M test split only; photographer credit shown after the answer; display use pending kulo's OK | journal 2026-10-26 photo rounds |

## Known gaps

- The dummy model is still the default. `GEO_COMPANION_MODEL=onnx:<manifest>` runs a real
  exported model, but only the weak smoke model exists until M1c, and it abstains on starter rounds (SVG
  diagrams, no photo). Stored predictions are keyed by model id and version, so bump the version on
  every retrain.
- The laptop has no CUDA GPU, so real training runs on the RTX 3060 PC. Nothing has run on
  Windows or a GPU yet.
- Calibration now uses a sqrt class-weighted val (smoke model: test ECE 0.090 → 0.023), but
  that was checked only on a weak smoke model; M1c must confirm it.
- Photo rounds exist but are opt-in (`GEO_COMPANION_PHOTO_PACK`) and come after the diagrams;
  answers show a country code, not a full name. Showing OSV-5M photos in the app needs kulo's
  confirmation (it was cleared for training). The smoke model abstains on 199 of 200 photos.
- The starter pack teaches one deliberately easy cue (a named city) and contains no real
  imagery.
- Storage cleanup for Task 4: the database tables from the original migration are still
  unused, and old development databases keep an unused progress table.

## Location history

Until 2026-10-14 the project lived in the Codex workspace at
`~/Documents/Codex/2026-09-30/could/geoguessr-meta-coach`, with this branch checked out in its
`.worktrees/initial-platform` folder. It was cloned here with full history, both branches,
and the ignored `.superpowers/sdd` task ledger. The old folder is untouched and kept as a
backup. It is registered here as the git remote `codex-workspace`.

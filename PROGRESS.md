# Geo Companion — progress

The current state of the project at a glance. Update this file in the same commit as any
work that changes it; detailed evidence for each session goes in [`journal/`](journal/).

**Last updated:** 2026-11-03
**Branch:** `main`. PRs #1–#4 are merged, and new work goes on short branches with one PR each into `main`, which kulo merges.
**GitHub:** [kulkerino/geo-companion](https://github.com/kulkerino/geo-companion) (public, because the professor needs access), remote `origin`; branches `main` and the separate school branch `rocnikovy-projekt` (no shared history, never merged)
**Next step:** finish the Mapillary import on the desktop (2,060 of 5,665 seeds done; resume with `uv run --group training --group model geo-train import-mapillary`) and clip-c2 (epoch 2 of 3 done; resume with its original command plus `--resume`, see the journal; score it on the benchmark and switch `play-clip.ps1` to it if it beats clip-c1), then train a CLIP model on OSV-5M + GeoGuessr-style + Mapillary (repeat the `--extra-*` triple) and score it on the GeoGuessr-style benchmark; then the GeoGuessr-style play mode.

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
| Repository cleanup (no behaviour change) | done, merged into `main` via PR #2 and PR #3 | see journal | [2026-10-26](journal/2026-10-26-repo-cleanup.md) |
| Photo rounds from held-out OSV-5M test photos | done, self-reviewed | see journal | [2026-10-26](journal/2026-10-26-photo-rounds.md) |
| Model M1c: real training on the RTX 3060 PC | done: test top-1 0.645, top-5 0.830 (171 countries); exported to ONNX on the PC | `b6968a7`, see journal | [2026-10-26](journal/2026-10-26-model-m1c-rtx-3060.md) |
| Photo upload: the model's top-3 guess or abstention on your own photo | done, self-reviewed; merged into `main` via PR #4 and PR #3 | see journal | [2026-10-26](journal/2026-10-26-photo-upload.md) |
| OSV-5M photo display OK; full country names after the answer | done, self-reviewed | see journal | [2026-11-01](journal/2026-11-01-photo-display-ok-country-names.md) |
| Model accuracy page: held-out results of the enabled model | done, self-reviewed | see journal | [2026-11-02](journal/2026-11-02-model-accuracy-page.md) |
| Race mode plan; searchable country list for guesses (race step 1) | done, self-reviewed | see journal | [2026-11-02](journal/2026-11-02-race-mode-plan-country-picker.md) |
| Race mode backend: race API, storage and scoring (race step 2) | done, self-reviewed | see journal | [2026-11-02](journal/2026-11-02-race-backend.md) |
| Race mode screen: start, countdown, side-by-side reveal, summary (race step 3) | done, self-reviewed | see journal | [2026-11-02](journal/2026-11-02-race-screen.md) |
| Race with M1c (race step 4): desktop timing and scripted races | desktop half done (33 ms per race answer, 0 failures in 100 rounds); laptop timing and real races to do | see journal | [2026-11-02](journal/2026-11-02-race-with-m1c-desktop.md) |
| Race history and model progress on a fixed photo set (race step 5) | done, self-reviewed | see journal | [2026-11-02](journal/2026-11-02-race-history.md) |
| Race mode projector mode: "Class vs Model" (race step 6) | done, self-reviewed | see journal | [2026-11-02](journal/2026-11-02-race-projector.md) |
| GeoGuessr-style benchmark; pretrained CLIP model (route C) in the app | done: clip-c1 63.8% top-1 vs M1c 18.2% on the benchmark; PRs #15 and #16 merged | see journal | [2026-11-03](journal/2026-11-03-geoguessr-benchmark-and-clip.md) |
| Own model id and description for CLIP models (race history no longer merges them with M1c) | done, self-reviewed | see journal | [2026-11-03](journal/2026-11-03-clip-model-id.md) |
| Mapillary panorama importer; several `--extra-*` sets in training | done, self-reviewed; live smoke run 6 panoramas from 16 seeds | see journal | [2026-11-03](journal/2026-11-03-mapillary-importer.md) |
| 4. Pack lifecycle and source tooling | planned | — | — |
| 5. Curriculum pipeline | planned | — | — |
| 6. Optional local model | planned | — | — |
| 7. Windows RTX worker | planned | — | — |
| 8. GeoGuessr review adapter | planned | — | — |
| 9. School delivery | planned | — | — |

The full plan is in
[`docs/superpowers/plans/2026-10-05-geoguessr-meta-learning.md`](docs/superpowers/plans/2026-10-05-geoguessr-meta-learning.md).

## What works today

- **Race the model**: five photo rounds against the enabled model, with an optional time
  limit per round, a side-by-side reveal after each answer and a summary. It needs a real
  model and a photo pack; with the placeholder it explains why it is off.
- **Class vs Model** (projector mode): pick "The class (projector)" before starting. The race
  gets big text, a full-width photo and a Full screen button; you type in the class's answer.
  Class answers are scored but do not change your study review.
- **Race history**: your record against the model over all finished races, overall and per
  model version, and "Model progress": each model version scored once on the same fixed photos
  (every photo of the loaded pack), totals only.
- Guesses are picked from a searchable list of every country (type a name or a code, e.g.
  France or FR); the answer is still sent as the two-letter code.
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
- **Your photo**: upload a JPEG, PNG or WebP photo of your own and get the enabled model's
  top-3 country guess or an abstention. The photo is held in memory for that request only
  and nothing is stored; photos from the loaded photo pack are refused.
- **Model accuracy**: a tab that shows the enabled model's held-out results, recorded when it
  was trained: top-1 and top-5 accuracy against "always guess the commonest country" and
  random guessing, how often it answers and how often it is right then, calibration error,
  and top-1 accuracy by country. The summary comes from the hash-checked manifest; the
  per-country rows come from the run's `report.json` and are shown only when it agrees with
  the manifest.
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
| 2026-10-26 | The GitHub repo stays public (kulo: the professor needs it) | journal 2026-10-26 photo upload |
| 2026-10-26 | Uploaded photos are kept in memory for one request, never stored, never graded; pack photos are refused byte for byte | journal 2026-10-26 photo upload |
| 2026-10-26 | M1c runs only while kulo is home: training is resumable (`--resume`, `--max-hours`) and split into sessions | journal 2026-10-26 M1c |
| 2026-11-01 | OSV-5M photos cleared for display in the app too (kulo: "i mean yea sure"); photos stay in app data, never in the repo | journal 2026-11-01 photo display OK |
| 2026-11-01 | Countries are shown as `Name (CODE)` after the answer, via the browser's offline `Intl.DisplayNames` | journal 2026-11-01 photo display OK |
| 2026-11-02 | PRs #2–#4 merged into `main`; stale local branches deleted; kulo merges PRs, Claude only opens them | journal 2026-11-02 branch cleanup |
| 2026-11-02 | Race mode: 1 point per right country, 5 rounds with a chosen time limit, no racing the dummy, race answers feed spaced repetition, projector-only class race; laptop vs desktop model decided by measurement | `docs/race-mode-plan.md` |
| 2026-11-02 | Guesses are picked from a fixed offline list of every country (never built from pack answers) | journal 2026-11-02 race mode plan |
| 2026-11-02 | Class (projector) races are stored with `player = class`; their answers are scored and kept as attempts but skip the spaced-repetition schedule | journal 2026-11-02 race projector |
| 2026-11-02 | Races reuse practice attempts and the stored post-answer model prediction; late answers (limit + 5 s) count as skips; a model that fails or changes loses that round | journal 2026-11-02 race backend |
| 2026-11-02 | Model progress compares versions on a fixed photo set named by a hash of its round ids, run once per version and set, totals only; race history counts finished races only | journal 2026-11-02 race history |
| 2026-11-03 | Pretrained CLIP (route C) replaces M1c as the app's model; route A dropped | journal 2026-11-03 benchmark and CLIP |
| 2026-11-03 | No Street View or GeoGuessr capture for training; Mapillary (CC BY-SA) is the next source | journal 2026-11-03 benchmark and CLIP |
| 2026-11-03 | Commits and PRs carry no Claude trailers or footers; long work goes in fresh threads to save tokens, with this file as the handoff | `CLAUDE.md` |

## Known gaps

- Pretrained models still get the manifest id `country-net` 0.1.0 and a "trained from scratch"
  description, the same id as M1c, so race history would merge them. Fix before racing CLIP.
- clip-c1 is 344 MB and takes about 150 ms per photo on the PC CPU; laptop speed not measured.
- The dummy model is still the default. `GEO_COMPANION_MODEL=onnx:<manifest>` runs a real
  exported model, but only the weak smoke model exists until M1c, and it abstains on starter rounds (SVG
  diagrams, no photo). Stored predictions are keyed by model id and version, so bump the version on
  every retrain.
- The laptop has no CUDA GPU, so real training runs on the RTX 3060 PC. M1c took 16 epochs
  of about 36 minutes there; its model files live only on the PC until copied over.
- On the Windows PC the Python checks pass, except the web-bundle test, which runs `pnpm` from
  PATH; Node 24 is installed there now and `npx --yes pnpm@11.19.0 ...` runs the web checks.
  The symlink storage test skips without the symlink privilege.
- Calibration uses a sqrt class-weighted val. On M1c it cuts val ECE 0.090 → 0.014 but barely
  moves test ECE (0.043 → 0.040), and the 0.8 val target precision gives 0.75 on test.
- Photo rounds are opt-in (`GEO_COMPANION_PHOTO_PACK`) and come after the diagrams; guesses
  are still typed as two-letter codes. The smoke model abstains on 199 of 200 photos.
- Photo upload works end to end, but the only real model on the PC (the M1c smoke model,
  `abstain_below` 1.0) always abstains, so a real top-3 on an upload waits for M1c. Refusing
  pack photos only catches byte-identical files; a re-saved copy gets through.
- Race history counts every finished race. Once projector mode (step 6) adds class races, the
  history must count only your own races.
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

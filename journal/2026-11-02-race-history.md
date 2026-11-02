# 2026-11-02 — Race history and model progress

## Intent

Race mode step 5 of [`docs/race-mode-plan.md`](../docs/race-mode-plan.md): show "you vs the
model" over all finished races, and a way to compare model versions on the same fixed photos,
so improvement from M1c to later models is visible. kulo asked to keep building what does not
need M1c while training waits for the RTX 3060 PC.

## Evidence

- Commit: on `feature/race-history`, one PR into `main`. Built on kulo's laptop.
- What changed:
  - `geo_companion/race_history.py` (`RaceHistoryService`), a new module so it stays apart
    from the race module that step 6 (projector mode, PR #10) changes.
  - `GET /api/v1/races/history`: finished races newest first, a total (races, rounds, points,
    wins, losses, draws) and the same total per model version. Unfinished races are left out.
    It returns scores and totals only, never a round id, answer or guess. The route is declared
    before `/api/v1/races/{race_id}` so "history" is not read as a race id.
  - `GET` and `POST /api/v1/models/benchmarks`: the enabled model guesses every photo of the
    loaded pack once, seeing only the public round (as in a race), and only the totals are
    stored in a new `model_benchmarks` table (right, abstained, failed, accuracy). A photo set
    id (`photos-<count>-<sha256 of the sorted round ids>`) names the exact photos, so runs are
    compared only on the same set. The models are deterministic, so a model version is run
    once per photo set; asking again returns the stored run. Like races, the placeholder and
    "no model" get a 409 with the reason. A benchmark is not practice: it adds no attempts and
    no reviews.
  - The model-route allowlist in `test_model_provider.py` (the guard that model routes are
    post-answer only) now lists `/api/v1/models/benchmarks`, with a comment on why it is safe.
  - New contracts at the end of `contracts.py` (`RaceTally`, `RaceModelRecord`,
    `RaceHistoryEntry`, `RaceHistory`, `ModelBenchmarkRun`, `ModelBenchmarks`); OpenAPI snapshot
    and TypeScript client regenerated with the script.
  - New "Race history" tab (`apps/web/src/RaceHistory.tsx`, its own file): your record line,
    a table per model version, the finished races, and "Model progress", a table with bars of
    each version's right-country rate on the fixed photos (the same bar style as Model
    accuracy), a note when older runs used another photo set, and a "Score the current model
    on these photos" button (disabled with the reason for the placeholder).
- Commands and results (laptop, Node 24.22.1 from the Codex runtime):
  - `uv lock --check` ok.
  - `uv run pytest -q`: 164 passed (7 new in `test_race_history.py`: finished-only totals with
    no answers in the payload, a record per model version, benchmarks per version on the same
    photos and run once, a failing model scores nothing, placeholder and no-model refused,
    photo set ids, and the API including the route order). A first run failed 1 test, the
    model-route allowlist, which was then updated as described above; a second run without
    `pnpm` on PATH failed the web-bundle test, which passes with the bundled Node on PATH.
  - `uv run ruff check .` ok; `uv run mypy` ok (26 files); contract and diagram `--check` ok;
    repository audit ok.
  - `pnpm --dir apps/web test`: 26 passed (3 new in `RaceHistory.test.tsx`, 1 new real
    FastAPI + SQLite integration test: empty history and the placeholder kept out of model
    progress). `lint`, `typecheck` and `build` ok.
  - `uv run ruff format --check packages/api` reports 3 files, the same 3 as on `main`; it is
    not one of the project's checks and those files were left alone.
  - Real app in the browser pane: the API with the M1b smoke ONNX model and the local OSV-5M
    photo pack (200 photos), data directory in a scratch folder, Vite on 5173. The empty
    history showed; "Score the current model" scored `country-net-smoke 0.0.1` on all 200
    photos in a few seconds: 0 right, 199 abstained, 0 failed (as expected for the smoke
    model). One 30 s race finished through the API (2 wrong guesses, 3 skips), and the tab
    then showed "1 drawn, over 1 race", the per-model row and the race row. The history JSON
    contained no `round_id`. No console errors.
- Decisions:
  - The fixed photo set is every photo round of the loaded pack, named by a hash of its round
    ids; changing the pack starts a new comparison instead of mixing sets.
  - Only finished races count in the history.
- Limitations:
  - Only the smoke model has been scored; the progress graph means something once M1c (and
    later models) are scored on the same pack.
  - The benchmark runs inside the request (a few seconds for 200 photos with the smoke model).
  - Step 6 (PR #10) adds a `player` column (`you` or `class`). Whichever of the two PRs merges
    second must make the history count only `player = 'you'` races, so a class race is not
    counted as yours.

## Follow-up

Rebase on step 6 when it merges and filter class races out of the history; score M1c on the
pack once it is exported (race mode step 4).

# 2026-11-02 — Race mode backend

## Intent

Race mode step 2 of [`docs/race-mode-plan.md`](../docs/race-mode-plan.md): the API and storage
for a race, where the learner and the enabled model guess the same five photo rounds. No screen
yet; that is step 3.

## Evidence

- Commit: on `feature/race-backend`, one PR into `main`.
- What changed:
  - Contracts: `RaceStartRequest` (optional per-round `time_limit_seconds`, 10 to 600, null for
    no limit), `RaceStarted`, `RaceRoundPublic`, `RaceRoundResult`, `RaceRoundSummary`,
    `RaceSummary`, `RaceScore`, `RaceAvailability`; `RACE_ROUNDS = 5`.
  - `geo_companion/race.py` (`RaceService`) with two new tables in the learner database:
    `races` (model id, version and full model info, time limit, start and finish time) and
    `race_rounds` (position, round, clock start, attempt, points, the model's top guess, late
    and model-unavailable flags).
  - Routes: `GET /api/v1/races/availability`, `POST /api/v1/races` (201, or 409 with the reason),
    `GET /api/v1/races/{race_id}` (summary), `GET /api/v1/races/{race_id}/rounds/{position}`
    (public round, starts its clock), `POST /api/v1/races/{race_id}/rounds/{position}/answers`.
    OpenAPI snapshot and the TypeScript client regenerated.
- How it works and why:
  - A race picks 5 photo rounds at random, avoiding the rounds of the last 3 races when enough
    others exist. Diagrams never race: the photo model cannot read them.
  - The learner's answer goes through the normal practice submit, so it is an ordinary attempt
    with a spaced-repetition schedule. The model's guess is the existing stored post-answer
    prediction for that attempt. No route shows a round's answer or the model's guess before
    the learner answers; the summary leaves answers of unanswered rounds null.
  - Scoring: 1 point for the right country, for the learner and for the model's top guess; a
    skip or an abstention scores 0.
  - Rounds are played in order, each answered once (409 otherwise). With a time limit, the
    clock starts when the round is first opened (reopening keeps it); an answer more than 5 s
    past the limit is recorded as a skip and scores 0.
  - If the model throws, or the app was restarted with a different model or version, the model
    gets 0 for that round and it is counted in `model_missed_rounds`.
  - The app never races the placeholder (kulo): availability says why, and starting returns
    409. `RaceService(allow_placeholder_model=True)` exists for tests only.
- Commands and results (cloud container, Node 24.22.2 for the web tests):
  - New `packages/api/tests/test_race.py`, 12 tests: availability reasons, a full race with
    both scores checked against the dummy's own predictions, hidden answers mid-race, order and
    answer-once rules, the clock, late answers, a failing model, a swapped model, avoiding
    recent rounds, stored model version, time limit bounds, and the HTTP routes including 404,
    409 and 422.
  - `uv lock --check` ok; `uv run pytest -q` 102 passed, 1 skipped (Pillow not installable
    here); ruff ok; API contract and starter diagram `--check` ok; web tests 18 passed, lint,
    typecheck and build ok; repository audit ok.
  - `uv run mypy`: the same 28 errors as on `main` in this container, all from the `training`
    group (PyTorch, Pillow, onnx) not installing here; none in `race.py`. CI runs it in full.
- Limitations:
  - No race screen yet, and no real-model race yet (M1c).
  - The time limit is enforced on the server only when an answer arrives; the screen in step
    3 will count down and submit a skip at zero.

## Follow-up

Race mode step 3: the race screen (start with a time limit choice, round with countdown,
side-by-side reveal, summary, greyed out with the reason when no real model is loaded).

# 2026-11-02 — Race mode projector mode ("Class vs Model")

## Intent

Race mode step 6 of [`docs/race-mode-plan.md`](../docs/race-mode-plan.md): the whole class
races the model on the projector. kulo chose projector mode only (no LAN race), so the app
stays reachable only from the laptop itself.

## Evidence

- Commit: on `feature/race-projector`, one PR into `main`.
- What changed:
  - Backend: a race now has a `player`, `you` (default) or `class`. `POST /api/v1/races`
    accepts it, and the race and its summary return it. The `races` table gains a `player`
    column; an older database gets it added on start (`ALTER TABLE ... DEFAULT 'you'`), so
    existing races stay "you" races.
  - Class answers still go through the practice submit (the stored post-answer model
    prediction needs the attempt), but `submit_practice(..., record_review=False)` skips the
    spaced-repetition schedule, so the class's guesses do not change kulo's study review.
  - Screen: "Who is racing" on the start screen (You / The class (projector)). A class race is
    titled "Class vs Model", uses larger text, a full-width photo (up to 72 % of the screen
    height), a big clock and score, and a "Full screen" button when the browser offers it.
    Labels say "Class" instead of "You" ("Class 1 : 0 Model", "The class skipped.", "The class
    won!"), and the summary says class answers were not added to study review.
- Commands and results (cloud container, Node 24.22.2):
  - `uv run pytest -q` 104 passed, 1 skipped (Pillow not installable here). New tests: a class
    race scores normally but leaves study review alone; an old `races` table gains the column.
  - `pnpm --dir apps/web test` 23 passed (new: a class race end to end with a stubbed API);
    lint, typecheck and build ok; `ruff check` ok; API contract check ok; repository audit ok.
  - Real Chromium (Playwright) against `vite preview` with the API mocked, at 1600 px wide: the
    round and reveal screens fill the width with the big clock and "Class 1 : 0 Model". A
    starter diagram stood in for the photo; no real photo pack or model is in this container.
- Limitations:
  - Class attempts are still stored as practice attempts, so they can nudge which round
    practice picks next; they never touch the review schedule.
  - Not yet tried on a real projector; check font sizes at the school demo.

## Follow-up

Race mode step 4 (race with M1c) once training is exported; step 5 (history and model graph) is
on its own branch.

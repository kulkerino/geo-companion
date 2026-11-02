# 2026-11-02 — Race mode screen

## Intent

Race mode step 3 of [`docs/race-mode-plan.md`](../docs/race-mode-plan.md): the screen on top of
the race API from step 2, so you can race the model in the app.

## Evidence

- Commit: on `feature/race-screen`, one PR into `main`.
- What changed:
  - New "Race the model" tab (`apps/web/src/Race.tsx`). Start screen: what a race is, the time
    limit per round (no limit, 10 s, 30 s, 1, 2, 3 or 5 min, like GeoGuessr's settings) and a
    Start button. Without a real model or photo pack the button is disabled and the server's
    reason is shown (for example "the placeholder model cannot race").
  - Round: "Round N of 5", the photo with its pre-answer credit, a countdown when a limit is
    set, a note that the model's guess stays hidden, the same searchable country list as
    practice, "Lock in guess" and "Skip". At zero the screen sends one skip by itself.
  - Reveal: the answer, then "You" and "Model" side by side (right or wrong, the model's top 3
    with confidence, abstention, or "unavailable this round"), the points, the running score
    ("You 1 : 0 Model"), the explanation and the answer credit. "Next round", then "See
    results" after the last round.
  - Summary: who won, a table of every round (answer, your guess, the model's guess, points),
    how many rounds the model missed, the model version, and "Race again".
  - `AttributionDetails` moved to its own file so practice and race share it; small CSS for
    the two sides and the clock; `select` uses the shared input style.
- Commands and results (cloud container, Node 24.22.2):
  - New `Race.test.tsx` (3 tests, stubbed API): disabled start with the reason; a two-round
    race checking that nothing about the answer shows before answering, the requests sent
    (time limit, `SK` from a typed name, then a skip), the reveal, the running score and the
    summary; and the automatic single skip when the clock has run out.
  - New integration test with the real FastAPI + SQLite: with the default placeholder model,
    the Race tab shows the reason and Start is disabled.
  - `pnpm --dir apps/web test` 22 passed (5 files); lint, typecheck and build ok;
    `uv run pytest -q` 102 passed, 1 skipped (Pillow not installable here); repository audit ok.
  - Real Chromium (Playwright) against `vite preview` with the API mocked: started a race with a
    1-minute limit, saw the 1:00 clock, typed "Slovakia (SK)", locked in, and the reveal showed
    both sides and "You 1 : 0 Model". A starter diagram stood in for the photo there; no real
    photo pack or model exists in this container.
- Limitations:
  - No race against a real model has run yet; that is step 4 with M1c.
  - The clock uses the server's start time and this computer's clock, which is fine because both
    run on the same machine.

## Follow-up

Race mode step 4: load M1c, measure its speed on the laptop and on the desktop, and play real
races.

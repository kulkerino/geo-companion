# Race mode plan

Drafted 2026-11-02, updated the same day with kulo's answers (see "Decisions" at the end).
Planning only, nothing is built yet. Based on `main` at `78da26c`
(photo rounds, photo upload, the model accuracy page, and the model slot with the dummy and the
ONNX provider).

## The idea

You and the model guess the same photo. Neither sees the other's guess. Then both guesses are
revealed next to the right answer, and points go to whoever got it right. A race is a short
series of rounds with a final score. Stretch goal: the whole class races the model.

## What a race looks like

1. **Start.** A new "Race the model" screen shows which model you are racing (name, version,
   and a Start button. A race is 5 rounds, with a per-round time limit picked before the race.
2. **Round.** The photo is shown with the usual pre-answer credit (generic dataset credit only).
   You pick a country from a searchable list, or skip. A small "Model is ready" badge shows that
   the opponent is there; it never shows anything about its guess.
3. **Reveal.** After you lock in, one screen shows, side by side:
   - the right answer (country name, place) and the photographer credit,
   - your guess, marked right or wrong,
   - the model's top guess, marked right or wrong, with its top 3 and confidence underneath,
   - the points for the round and the running score ("You 2 : 1 Model").
4. **Summary.** After the last round: final score, who won, and a table of every round
   (photo thumbnail, answer, your guess, model's guess). "Race again" starts a new one.

## Scoring (recommended: keep it simple)

- 1 point for the right country, 0 otherwise. Same rule for you and the model.
- A skip, or a model abstention, scores 0.
- The model's 2nd and 3rd guesses are shown for learning, but they don't score.
- No speed points: the model answers in milliseconds, so time can't be fair.
- Draws are allowed.

This is easy to explain at school, and it measures the same thing as the model's honest
top-1 accuracy. Partial credit (for example for a neighbouring country) could come later, but
it needs a neighbour table that we don't have.

## How it reuses what exists

- **Rounds:** races draw from the loaded photo pack (the OSV-5M **test** photos, which the
  model never trained on, so the race is fair). The 10 SVG diagrams are left out, because the
  photo model can't read them. Rounds are picked at random, avoiding ones from your last races
  where possible.
- **Your answer:** goes through the existing practice submit, so it is stored as a normal
  attempt and feeds spaced repetition like any practice round.
- **The model's answer:** uses the existing "Compare with model" path
  (`model_prediction(attempt_id)`), which already requires your answer first and stores the
  result once. The model only ever sees the public round (the photo), never the answer and
  never your guess, and it is deterministic, so asking it after you answer gives exactly the
  same guess as asking it before. No new "predict before answer" route is needed, so the
  current no-leak rule stays as it is.
- **What is new:** a small race record that groups attempts. Two tables: `races` (id, model id
  and version, start and end time) and `race_rounds` (race id, position, round id, attempt id,
  your points, model points). Three endpoints: start a race, answer a race round (submit +
  model prediction + points in one response), and get a race summary.

## When the model isn't available

- **No model** (`GEO_COMPANION_MODEL=none`) or **no photo pack:** the Race screen is shown
  greyed out with one line on why ("Race mode needs a model and the photo pack"). Practice,
  study review and everything else work as today. The start endpoint returns a clear 409.
- **Dummy model:** no racing against the placeholder in the app (kulo, 2026-11-02). It is used
  only in automated tests; the Race screen stays greyed out until a real model is loaded.
- **Model fails in the middle of a race** (error, or later a remote PC that drops off): that
  round shows "Model unavailable", the model gets 0, the race is marked "model missed N rounds",
  and you can finish or end the race. Your answers are still saved as practice.

**Where the model runs:** today the model runs inside the app's own process. The M1c model is a
ResNet-18 in ONNX, and the earlier smoke model took 12.8 ms per image on the laptop CPU, so
M1c should also be fast enough on the laptop (to be measured). If so, race mode and the school
demo need no desktop and no Tailscale at all. A "remote model on the desktop" provider would
only be needed for a much bigger model later, and would be its own piece of work.

## Data needed

- The existing photo pack (200 rounds, 177 countries) is enough to start. A bigger pack (for
  example 500 to 1,000 test photos) would cut repeats; `geo-train photo-pack` can build it.
- The M1c ONNX model and manifest, once training finishes. The dummy is used only in tests.
- A country list for the picker: the model's classes from the manifest, plus any country in the
  pack, with names from the browser's offline `Intl.DisplayNames` (already used for answers).
- Nothing new is downloaded, and nothing goes into the repo. Photos are already cleared for
  display (CC BY-SA credit, 2026-11-01).

## Stretch: the whole class racing

The app is deliberately reachable only from the laptop itself (`127.0.0.1`). kulo chose option A
on 2026-11-02; option B is kept here only as the record of what was considered.

- **A. Projector mode (chosen, no networking).** The race runs on kulo's laptop on
  the projector. The class votes (hands or shouting), kulo enters the class's answer, and the
  final screen shows "Class vs Model". Small change on top of the solo race, zero risk at the
  demo.
- **B. LAN class race (dropped).** A separate, opt-in "race host" that kulo starts on purpose. It listens
  on the local network and serves only the current photo, a nickname form and a guess form;
  never practice data or the database. Classmates open `http://<laptop-ip>:<port>` on their
  phones, guesses are collected, then a leaderboard with the model as one more player.
  Nicknames stay in memory and are thrown away after the race. Simple polling, no accounts.
  Risks: school Wi-Fi often blocks devices from seeing each other (fallback: laptop hotspot),
  and it is an exception to the "loopback only" rule, so it needs your explicit OK.

## Steps, as small PRs

Each PR has its own journal entry and a `PROGRESS.md` update, as usual.

1. **Plan into the repo + country picker.** Add this plan as `docs/race-mode-plan.md`. Replace
   the 2-letter code box with a searchable country list (helps normal practice too). Done on
   `feature/race-plan-country-picker`, see `journal/2026-11-02-race-mode-plan-country-picker.md`.
2. **Race backend.** Contracts, the two tables, three endpoints, scoring, regenerated TS client.
   Tests: model sees only the public round, nothing leaks before the answer, no-model returns
   409, model failure mid-race, scoring and draws. Done on `feature/race-backend`, see
   `journal/2026-11-02-race-backend.md`.
3. **Race screen.** Start, round, side-by-side reveal, summary, greyed-out state without a
   model. Integration test with the dummy model through the real API. Done on `feature/race-screen`, see
   `journal/2026-11-02-race-screen.md`.
4. **Race with M1c.** Load M1c on the laptop and on the desktop, measure time per photo and
   reliability on each, pick the faster reliable one, play a few real races,
   record the results in a journal entry (a nice extra number for the accuracy report: "humans
   vs model"). Depends on M1c finishing.
5. **Race history and model progress.** "You vs model over all races", and a graph of how each
   model version (M1c, then later models) scored on the same fixed set of race photos, so
   improvement between models is visible. Every race already stores the model id and version.
   Done on `feature/race-history`, see `journal/2026-11-02-race-history.md`.
6. **Projector mode** ("Class vs Model"). LAN class race is dropped. Done on
   `feature/race-projector`, see `journal/2026-11-02-race-projector.md`.

## Decisions (kulo, 2026-11-02)

1. Scoring: 1 point per right country (GeoGuessr's distance points need a map pin, and the model
   only guesses a country).
2. 5 rounds per race, with a per-round time limit chosen like GeoGuessr's game settings.
3. Laptop vs desktop model: decide from measured numbers in step 4 (speed and reliability; the
   accuracy is the same, it is the same model file).
   Measured: desktop 33 ms, laptop about 23 ms per race answer, 0 failures, so races run on
   the laptop ([2026-11-09](../journal/2026-11-09-race-laptop-timing.md)).
4. No racing the dummy; race once M1c is in. Track model versions so future models can be
   compared on a graph.
5. Race answers count as practice for spaced repetition (this trains the player, not the model).
6. Class race: projector mode only.

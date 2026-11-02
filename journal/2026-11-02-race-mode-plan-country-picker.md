# 2026-11-02 — Race mode plan and searchable country list

## Intent

kulo asked for a plan for race mode (you and the model guess the same photo, then both are
revealed) and then for the first step of it. This session records the plan in the repository and
replaces the two-letter code box with a searchable country list, which the race screen will reuse
and which already makes normal practice easier.

## Evidence

- Commit: on `feature/race-plan-country-picker`, one PR into `main`.
- What changed:
  - `docs/race-mode-plan.md`: the race mode plan (flow, scoring, reuse of photo rounds and the
    model slot, model-unavailable handling, data, class race, PR steps) with kulo's decisions.
  - `apps/web/src/countries.ts`: a fixed list of the 249 ISO 3166-1 alpha-2 codes plus Kosovo
    (`XK`), labelled `Name (CODE)` with the browser's offline `Intl.DisplayNames`, sorted by
    name. `parseCountryGuess` accepts a picked entry (`Slovakia (SK)`), a full name in any case
    and without accents (`curacao` finds Curaçao), or a code (`sk`). Anything else, including an
    unknown code such as `ZZ`, is not a guess. `country()` moved here from `App.tsx` unchanged.
  - `App.tsx`: the guess box is now "Country guess (type to search, e.g. France or FR)" with a
    `<datalist>` of every country, so the browser filters the list while you type. The submit
    buttons stay disabled until the text names a country, with a one-line hint. The API request
    is unchanged: it still sends the two-letter code.
  - Tests: new `countries.test.ts` (list size and uniqueness, sorting, parsing, rejection); a new
    `App.test.tsx` case that checks the list and that typing `slovakia` sends `SK`; the existing
    tests use the new label, and `zz` is now refused.
- Commands and results (cloud container, Node 24.22.2 for the web tests):
  - `uv lock --check` ok; `uv run pytest -q` 90 passed, 1 skipped (Pillow could not be
    installed here); ruff ok; API contract and starter diagram `--check` ok.
  - `pnpm --dir apps/web test` 18 passed (4 files, including the real FastAPI + SQLite
    integration test); lint, typecheck and build ok; repository audit ok.
  - `uv run mypy` reported 28 errors, all in `packages/training` and all caused by the
    `training` group (PyTorch, Pillow, onnx) not installing in this container (the PyTorch
    index is not reachable here). No file this change touches is Python. CI installs all groups
    and runs mypy in full.
- Decisions (kulo, 2026-11-02; details in the plan):
  - Race scoring is 1 point per right country (GeoGuessr's distance points need a map pin and
    the model only names a country).
  - 5 rounds per race, with a per-round time limit chosen before the race, like GeoGuessr.
  - Whether the race model runs on the laptop or the desktop is decided from measured speed and
    reliability once M1c is exported.
  - No racing the dummy placeholder; races wait for M1c. Each race stores the model id and
    version so later models can be compared on a graph.
  - Race answers count as practice for spaced repetition.
  - The class race is projector mode only; no local-network version.
  - The country list is fixed and never built from a pack's answers, so it cannot narrow down
    the answer of a round.
- Limitations and external gaps:
  - How the `<datalist>` filters (prefix or substring) depends on the browser. Not checked in a
    real browser in this session; jsdom only.
  - The list offers every ISO country, not only the ones the model knows; a guess of a country
    the model was never trained on is still a fair guess for the learner.

## Follow-up

PR 2 of the plan: the race backend (contracts, `races` and `race_rounds` tables, three
endpoints, scoring), tested with the dummy model.

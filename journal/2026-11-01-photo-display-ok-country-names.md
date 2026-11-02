# 2026-11-01 — OSV-5M photo display OK and full country names

## Intent

Record kulo's answer on showing OSV-5M photos in the app, and replace bare country codes
with full country names wherever the app shows a country after the answer.

## Evidence

- Commit: this entry's commit on `feature/photo-upload`.
- Decisions:
  - Asked "Can the app show OSV-5M photos to you during practice?" (photos stay in app data,
    never in the public repo; photographer credited after the answer). kulo: "i mean yea sure".
    Photo rounds are now cleared for display as well as training. Nothing about how the pack
    is built or loaded changed.
  - Country names come from the browser's built-in `Intl.DisplayNames` (English), so they work
    offline and add no data to the bundle. Shown as `Slovakia (SK)`: the code stays visible
    because guesses are still typed as two-letter codes. Used for the revealed answer, the
    "you guessed" line, and the model's candidates (practice comparison and your photo).
    Nothing before the answer changed.
- Commands and results (Windows PC; web checks via `npx --yes pnpm@11.19.0`):
  - `pnpm --dir apps/web test`: 11 passed (after updating the expected texts in
    `App.test.tsx` and `App.integration.test.tsx`; the first run caught a lost space in
    `Portugal (PT) · 41%`).
  - `pnpm --dir apps/web lint`, `typecheck`, `build`: pass.
  - `uv lock --check`: pass. `uv run ruff check .`: pass. `uv run mypy`: pass.
  - `uv run pytest -q`: 139 passed, 1 skipped, 1 failed. The failure is
    `test_web_bundle_safety`, which runs `pnpm` from PATH (the known Windows gap). Checked by
    hand instead: the fresh `apps/web/dist` has no "Slovakia" or "Bratislava".
  - `uv run python tools/audit_repository.py --root .`: pass.
  - Not run: the API-contract and starter-diagram `--check` scripts (no contract or diagram
    change).
- Limitations and external gaps: names follow the browser's ICU data (e.g. "Czechia"); an
  unknown code falls back to the code itself.

## Follow-up

M1c training continues from epoch 5 of 16 per the runbook.

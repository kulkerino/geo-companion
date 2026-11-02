# 2026-10-26 — Photo rounds from held-out OSV-5M test photos

## Intent

The next unfinished model milestone is M1c, the real training run, which needs kulo's RTX
3060 PC; the laptop has no CUDA GPU. While M1c waits, close the gap that made any trained
model useless in the app: practice rounds were only the ten SVG diagrams, so a photo model
abstained on every round. This adds real photo rounds without weakening the answer-leak
rules.

## Evidence

- Branch: `feature/model-m1` (cleanup PR #2 merged into it first).
- What changed:
  - Contracts: `AssetKind` (`diagram` default, `photo`) on `PracticeRound` and
    `PracticeRoundPublic`; `PackAsset` and `LocalPhotoPack` (a `ContentPack` plus one
    SHA-256 per photo; photo rounds only, one asset each). The starter pack's content hash
    changed because `asset_kind` is now part of every round; its version stays 2.0.0 since
    no content changed and progress is keyed by round id.
  - `geo-train photo-pack` (`geo_training/photo_pack.py`): reads the **test** CSV only,
    keeps countries with at least `--min-count` (50) photos, takes them round-robin over a
    seeded shuffle so the pack is not mostly US, then shuffles the round order. Round and
    asset ids are a SHA-256 of pack id, seed and image id. Each photo is EXIF-transposed,
    resized to at most 1280 px and re-encoded into a fresh image, so no EXIF/GPS, XMP, ICC
    profile or comment survives. The pre-answer attribution is the same generic dataset
    credit for every photo; the photographer (`creator_username`), Mapillary image id, place
    and coordinates are only in the answer and its citation. Packs are immutable: the
    command refuses to overwrite an existing `pack.json`, and it needs the ledger `cleared`.
  - API (`geo_companion/photo_pack.py`, `main.py`): `GEO_COMPANION_PHOTO_PACK=<pack.json>`
    loads a pack from outside the repository after checking the content hash, that every
    attribution and citation is `cleared`, and every photo's SHA-256; otherwise the app
    refuses to start. Its rounds follow the starter rounds. `GET /api/v1/assets/{asset_id}`
    serves only photos listed in the loaded pack (404 otherwise). `/api/v1/packs` lists it.
    The pack is also the ONNX provider's `RoundImageSource`, so **Compare with model** runs
    the model on the round's photo. `LearningService` takes its rounds as a parameter.
  - Web: photos load from `/api/v1/assets/…`, diagrams from `/starter-assets/…`; the
    attribution is labelled "Photo attribution" for photos.
  - README section "Photo rounds"; a dated update in `docs/model-m1-plan.md`.
- Commands and results:
  - `uv run geo-train photo-pack --ledger docs/sources/osv5m.json --metadata $D/metadata/test.csv --images $D/images/test`
    → "Wrote 200 photo rounds from 177 countries", 6.6 s, 12 MB in
    `~/.local/share/geo-companion/packs/osv5m-test-photos/1.0.0/`.
  - API on 127.0.0.1 with that pack and the M1b smoke model (scratch data dir): `/packs`
    lists both packs; the public round has `asset_kind: photo` and no answer; the photo
    serves as `image/jpeg`; the reveal shows the place, coordinates and photographer.
  - Smoke model over all 200 photo rounds: it answered 1 and abstained on 199
    (`abstain_below` 0.628). Expected for the weak 2-epoch smoke model; M1c is what matters.
  - Browser check through Vite: the first photo round renders with its photo attribution.
  - Verification list: `uv lock --check` ok; `uv run pytest -q` 122 passed; ruff ok; mypy
    ok; API contract and starter diagram `--check` ok; web tests (8), lint, typecheck, build
    ok; repository audit ok. The audit first flagged a variable named `token` as a possible
    secret; the variable was renamed, the audit was not changed.
- Decisions:
  - Photo rounds come from the OSV-5M **test** split, which training never reads, so neither
    the learner's practice nor the model comparison uses training photos.
  - OSV-5M was cleared for training on 2026-10-19. Showing its photos locally in the app is a
    new use of the same CC BY-SA 4.0 data; the pack carries the ledger's attribution plus a
    per-photo credit. **kulo should confirm this use** before any pack is shared.
  - The photographer credit is withheld until the answer, because a username can hint at the
    place. The credit is still shown with the photo in the same round.
  - Photo upload of a learner's own pictures was not built: locating personal photos raises
    privacy questions that the ethics boundary does not cover yet.
- Limitations and external gaps:
  - Answers show the country code and place name, not a full country name (no offline
    name table yet).
  - Round order is starter diagrams first, then photos; there is no mode switch yet.
  - Nothing ran on Windows; M1c is still not started.

## Follow-up

Run M1c on the RTX 3060 PC with `docs/runbook-m1c-rtx-3060.md`, then load the M1c model
with this photo pack and record how often it answers and how often it is right.

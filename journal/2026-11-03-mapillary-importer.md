# 2026-11-03 — Mapillary panorama importer

## Intent

Get more GeoGuessr-like training images without touching Google imagery: Mapillary 360-degree
panoramas (CC BY-SA 4.0, the same source as OSV-5M) near OSV-5M spots, cut into four horizon
views like the `pano` GeoGuessr-style set. Also let `geo-train run` take several extra sets, so
clip-c2 can train on OSV-5M + GeoGuessr-style + Mapillary at once.

## Evidence

- Commit: see the branch `feature/mapillary-importer`.
- New command `geo-train import-mapillary` (`packages/training/src/geo_training/mapillary.py`):
  seeds per GeoGuessr country from the OSV-5M train CSV (one per 0.1-degree cell, deterministic;
  HK, VN, LA, SK and PH get 3x seeds), the zoom-14 Mapillary coverage tile around each seed,
  car-height panoramas (`is_pano` and not `foot`) within 1.5 km, one per sequence and nearest
  first, their `thumb_2048_url` downloaded, the 0.32-0.68 height band cut into four 512x368
  views. Output in the OSV-5M CSV format under `%LOCALAPPDATA%\geo-companion\datasets\mapillary`
  plus `metadata/attribution.csv` (creator per panorama). Benchmark = 10% of 0.5-degree cells.
  Resumable through `raw/searched.jsonl` and `raw/panos/`.
- `geo-train run --extra-metadata/--extra-images/--extra-ledger` can now be repeated, one triple
  per extra set; each set is named in the model's attribution.
- Ledger `docs/sources/mapillary.json`, `reference-only` until kulo clears it.
- Commands and results (desktop PC, CPU only; clip-c2 was training on the GPU from another
  checkout and was not touched):
  - First version used the Graph API image search with `is_pano=true`: 0 panoramas for 9
    seeds. A probe showed why: central Bratislava returned 495 images, none panoramas, and
    larger boxes gave HTTP 500. Switched to the coverage vector tiles, which mark `is_pano`
    on every point (Hanoi tile: 4,990 of 101,990 images are panoramas; Zilina 1,506 of 2,141).
    The tile server rejects the token in a header (403) and takes it only as a query
    parameter, so that URL is never printed or stored.
  - `geo-train import-mapillary --countries VN,HK,SK,JP --seeds-per-country 4 --weak ""` into
    the scratchpad: 16 seeds, 6 panoramas, 24 views (JP 16, VN 8; HK and SK seeds had no car
    panoramas within 1.5 km), 47 s. Looked at the views: most horizons sit in the band; one
    motorbike panorama is tilted.
  - `uv lock --check` OK; `uv run pytest -q` 188 passed, 1 skipped, 1 failed
    (`test_web_bundle_safety`, which calls `pnpm` from PATH; known on this PC);
    `ruff check .` OK; `mypy` OK; API contract and starter diagram checks OK;
    `tools/audit_repository.py --root .` OK. Web checks not run (no web change).
- Decisions:
  - The token lives in `~/geo-companion-secrets/mapillary-token.txt` (or `MAPILLARY_TOKEN`),
    not in AppData: the Claude desktop app is an MSIX package, so files it writes under
    `%LOCALAPPDATA%` are redirected to
    `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\` and kulo could not see them.
  - A small protobuf decoder reads the tiles, so no new dependency.
- Limitations and external gaps:
  - A panorama takes its seed's country; within 1.5 km of a border a few may be mislabelled.
  - Panoramas are not levelled; tilted ones go in as they are. Partial panoramas padded with
    white in the road half are skipped.
  - Yield is low (about 0.4 panoramas per seed in the smoke run) and each seed takes about 3 s,
    mostly the 1-6 MB tile download; the full default run (60 seeds per country) will take
    hours. It uses no GPU.
  - Mapillary panoramas may include images that are also in OSV-5M.

## Follow-up

Run the full import on the desktop, then train clip-c2/clip-c3 with three sets (repeat the
`--extra-*` triple) and score it on the GeoGuessr-style benchmark.

## Stopping for the night (20:55 UTC)

- The full import (`geo-train import-mapillary`, defaults) had searched 2,060 of 5,665 seeds and
  downloaded 1,361 panoramas when kulo ended the session; about 0.66 panoramas per seed.
- Resume fix: a re-run now downloads panoramas that were chosen but not yet downloaded (with a
  fresh link if the old one expired) and skips a log line cut short by the stop. Test
  `test_a_stopped_run_downloads_what_it_missed`; `pytest packages/training/tests/test_mapillary.py`
  9 passed, `ruff check .` and `mypy` OK.
- Resume with the same command, from the repository root on the desktop:
  `uv run --group training --group model geo-train import-mapillary`
- clip-c2 (started by another session) had finished epoch 2 of 3 (val top-1 0.763) with
  `last.pt` saved. Resume it with its original command plus `--resume`; it is in the project
  plan file `current-plan.md`.

# 2026-11-03 — GeoGuessr-style benchmark, CLIP model (clip-c1), app switched to it

## Intent

Measure M1c on images that look like GeoGuessr, then try a pretrained network (route C) and
put the better model in the app. All runs on the RTX 3060 PC.

## Evidence

- Commits: PR #15 (benchmark, fine-tuning; pagination fix `7646acd`), PR #16 (route C), both
  merged by kulo.
- Commands and results:
  - `uv run geo-train import-geoguessr-style`: first run failed (`raw\sean\metadata.csv`
    missing) because the Hugging Face tree API pages at 1000 entries; fixed by following the
    `Link rel="next"` header. Re-run: train 75,379, benchmark 11,154, 66 countries; skipped
    1,660 duplicates and 1,000 each of BN, MM, TL (not GeoGuessr countries).
  - Partial set (`--sets geoguessr,pano --offline` into `geoguessr-style-partial`, raw files
    hard-linked because the sandbox cannot read through a junction): train 69,659,
    benchmark 10,521, 64 countries.
  - clip-c1: `geo-train run --backbone clip-b16 ... --extra-metadata <partial>\train.csv
    --epochs 5 --learning-rate 3e-5 --batch-size 64 --max-hours 2.5 --device cuda`. Batch 64
    fit (6.5 of 12 GB), about 29 min per epoch, all 5 epochs inside the cap; val top-1
    61.3 / 65.7 / 72.7 / 77.5 / 78.5%.
  - `geo-train regrade` on both benchmarks (top-1 split by source from a one-off script that
    reproduced regrade's top-1 and top-5 exactly):

    | | M1c partial | clip-c1 partial | M1c full | clip-c1 full |
    |---|---|---|---|---|
    | top-1 | 18.6% | 65.6% | 18.2% | 63.8% |
    | top-5 | 42.7% | 87.4% | 42.2% | 85.7% |
    | GeoGuessr screenshots | 25.2% | 77.5% | 25.2% | 77.5% |
    | panorama views | 11.6% | 52.8% | 11.6% | 52.8% |
    | Southeast Asia | — | — | 12.0% | 33.5% |
    | coverage / selective top-1 | 57% / 26% | 85% / 73% | 57% / 25% | 84% / 72% |

    clip-c1 worst on full: PH 33%, SK 21%, HK 15% (740 images), LA 1%, VN 0% (it never saw
    the Southeast Asia training images). Best: IL 92%, DE 88%, JP 88%, SG 87%, FI 82%.
  - ONNX on the PC CPU: M1c 45 MB, 12 ms per image; clip-c1 344 MB, about 150 ms per image.
  - App: `%LOCALAPPDATA%\geo-companion\play-clip.ps1` (copy of `play-m1c.ps1` pointing at the
    clip-c1 manifest, run from a checkout of current `main`). The ONNX provider accepts the
    344 MB model and its manifest checks; `/api/v1/photo-guesses` answers in about 130 ms;
    3 of 6 benchmark photos right first, misses were neighbours.
  - clip-c2 started: `--init-from clip-c1` on the full set, 3 epochs, lr 2e-5.
- Decisions:
  - Route C (pretrained CLIP) replaces M1c as the app's model; route A is not worth running.
  - No Street View or GeoGuessr capture (Google's terms forbid training on Maps content; our
    data policy forbids capture). Next data source: Mapillary panoramas (CC BY-SA), aimed at
    the weak countries.
  - Long work is split into fresh threads to save tokens; `PROGRESS.md` is the handoff.
- Limitations and external gaps:
  - The 77% on screenshots may be optimistic (that set's own test split may share places with
    its training split); the panorama number uses a split by map cell.
  - The pretrained manifest still says `model_id: country-net`, version `0.1.0` and "trained
    from scratch", the same id as M1c, so race history would merge the two models. Not fixed
    yet.
  - Laptop speed of clip-c1 not measured.

## Follow-up

Score clip-c2 and switch `play-clip.ps1` to it if better; fix the manifest id and description
for pretrained backbones; Mapillary import (needs kulo's free token); laptop timing.

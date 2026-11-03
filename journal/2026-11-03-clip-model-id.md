# 2026-11-03 — Own model id for CLIP models

## Intent

clip-c1 was exported with M1c's `model_id` (`country-net`) and version (`0.1.0`), and the app
called it "trained from scratch". Race history and Model progress key on model id + version,
so clip-c1 races were merged with M1c's.

## Evidence

- Commit: see the branch `fix/clip-model-id`.
- `geo-train run --model-id` now defaults to `country-net` for `countrynet` and
  `country-<backbone>` otherwise (`clip-b16` gives `country-clip-b16`).
- `CountryModelManifest` gains `backbone` (default `countrynet`, so older manifests still load);
  the export writes it, and the app describes a pretrained model as "fine-tuned from the
  pretrained <backbone> network" instead of "trained from scratch".
- On the desktop, `runs/clip-c1/manifest.json` now has `model_id` `country-clip-b16` (backup at
  `manifest.json.bak-country-net`). `backbone` is not added there yet, because the app on
  `main` refuses unknown manifest fields; add it after this PR is merged.
- Commands and results (desktop PC): `uv run pytest -q` 182 passed, 1 skipped, 1 failed
  (`test_web_bundle_safety`, which needs `pnpm` on PATH; known on this PC); `ruff check .`,
  `mypy`, the API contract and starter diagram checks, `uv lock --check` and
  `tools/audit_repository.py --root .` OK. Web checks not run (no web change).
- Limitations and external gaps:
  - Races already played with clip-c1 are stored under `country-net 0.1.0` and stay merged
    with M1c's; they cannot be told apart afterwards.
  - clip-c2, which was training when this was written, was started without `--model-id`;
    its manifest needs the same edit (`country-clip-b16`, a new version such as `0.2.0`).

## Follow-up

After the merge, add `"backbone": "clip-b16"` to the CLIP manifests on the desktop.

# 2026-11-02: GeoGuessr-style data, benchmark and fine-tuning

M1c learned from OSV-5M dashcam photos; nobody has measured it on images that look like
GeoGuessr. This adds what is needed to do that and to fine-tune
([runbook](../docs/runbook-geoguessr-benchmark.md)):

- `geo-train import-geoguessr-style`: three free Hugging Face sets (36k GeoGuessr screenshots,
  11k Street View panoramas cut into 4 views each, 11k Southeast Asia images), GeoGuessr
  countries only, de-duplicated, in the OSV CSV format.
- A fixed benchmark (`benchmark.csv`) that no model trains on: the screenshot set's test split,
  10% of panorama map cells and 10% of the Southeast Asia images.
- `geo-train regrade --out-name` scores any run on it; `top1_all_images` counts countries the
  model does not know as misses.
- `geo-train run --init-from <run>` fine-tunes from earlier weights (head rows matched by
  country), and `--extra-metadata/--extra-images/--extra-ledger` adds a private,
  `reference-only` set to training (see docs/data-policy.md). The model's attribution names it.

Open: run the import and score M1c on the PC; pick route A, B or C from the numbers.

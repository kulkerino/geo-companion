# 2026-11-02: GeoGuessr countries only

kulo's first races against M1c asked about China, Svalbard & Jan Mayen, Azerbaijan, Ecuador
and Palau. Only Ecuador is in GeoGuessr. The photo pack spread rounds evenly over every
OSV-5M country, and M1c could answer any of its 171 classes.

Geo Companion trains for GeoGuessr, so one list now decides which countries the app plays:
`packages/api/src/geo_companion/geoguessr_countries.py` (109 countries and territories with
official coverage, from geohints.com and geometas.com, checked 2026-11-02).

- Startup drops photo rounds from other countries, so existing packs need no rebuild.
- `geo-train photo-pack` only draws from the list.
- The ONNX provider masks the other countries' scores and renormalises; no retraining.
- The web guess picker offers only these 109 (a test keeps it equal to the Python list).
- `geo-train regrade --run-dir <run> --test-metadata ... --test-images ...` re-measures a
  finished run the way the app now uses it and writes `report-geoguessr.json`.
- `geo-train run --geoguessr-only` trains only on listed countries (for the next model).

Open: run `regrade` on M1c on the desktop to get the honest GeoGuessr-only accuracy.

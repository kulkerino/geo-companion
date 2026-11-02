# Data policy

Runtime state lives outside this vault in the platform-specific Geo Companion
application-data directory. This includes SQLite databases, active and staged
packs, learner progress, quarantined data, generated reports, and model files.

The repository may track only code, documentation, audit manifests, small
cleared fixtures, and reproducibility metadata. `.gitignore` excludes common
runtime data and model formats. New packs must record provenance and rights
metadata and remain quarantined until a later validation step verifies them.

No component downloads data or models implicitly. Any future external fetch
must be user-directed, auditable, and compatible with the stated rights status.

## Private training data (decided by kulo, 2026-10-14 and 2026-11-02)

Training data may use looser rights than what the app shows. A dataset whose record is
`reference-only` may be added to training with `geo-train run --extra-ledger`, for private
models only; a `quarantined` record is always refused. Its images are never put in a pack or
shown in the app, and the model's attribution names it. The GeoGuessr-style sets
(`docs/sources/geoguessr-style.json`) are used this way: they are the only free images that
look like the game, and their imagery remains under Google's and GeoGuessr's terms. Nothing
in this project captures Street View or GeoGuessr imagery itself.

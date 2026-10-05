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

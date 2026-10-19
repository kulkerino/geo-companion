# Audit structure

Keep durable evidence adjacent to the decision it supports:

- `journal/` holds dated implementation and review notes.
- `docs/` holds product, ethics, data, and architecture decisions.
- Content packs will carry manifests, source ledgers, hashes, and validation
  reports in later tasks.
- Generated reports, private datasets, and model artifacts remain outside Git.

Every substantive task records its tested behavior, commit, limitations, and
external setup gaps in a dated journal note.

The committed Obsidian core-plugin configuration enables Templates and points
it at the vault-visible `templates/` folder. Repository safety checks use the
exact command `uv run python tools/audit_repository.py --root .`; it scans the
working tree (including ignored runtime files), while excluding dependency and
tool-cache directories.

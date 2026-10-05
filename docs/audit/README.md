# Audit structure

Keep durable evidence adjacent to the decision it supports:

- `journal/` holds dated implementation and review notes.
- `docs/` holds product, ethics, data, and architecture decisions.
- Content packs will carry manifests, source ledgers, hashes, and validation
  reports in later tasks.
- Generated reports, private datasets, and model artifacts remain outside Git.

Every substantive task records its tested behavior, commit, limitations, and
external setup gaps in a dated journal note.

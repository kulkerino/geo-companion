# Working agreement for Geo Companion

This folder (`~/Documents/geolearn`) is the project's home. Read `PROGRESS.md` first, then the
latest entry in `journal/`.

## Documenting progress (required in every working session)

1. Add or extend a dated journal entry, `journal/YYYY-MM-DD-<short-topic>.md`. Base it on
   `templates/session-note.md` and include: the intent, the decisions made, the exact
   commands run with their results, any limitations, and the next step.
2. Update `PROGRESS.md`: the task table, the "Last updated" date, the next step, and any
   new decision or known gap.
3. Commit the journal and the `PROGRESS.md` changes together with the code they describe.
4. Record only what actually ran. If a check failed or was skipped, say so.

## Constraints that must not be weakened

- Everything runs offline on the laptop: FastAPI is bound to `127.0.0.1`, and SQLite lives in
  the application-data directory, never inside this folder.
- No pre-answer payload, clue, alt text, or diagram may reveal the answer.
- An active pack is publication-ready only when every attribution and citation is `cleared`.
- Do not weaken the repository audit (`tools/audit_repository.py`) or the data-path
  containment rules.
- Pydantic/OpenAPI is the source of truth. Regenerate the TypeScript client with
  `packages/api/scripts/generate_api_contract.py`; never hand-edit `generated.ts`.
- Regenerate starter diagrams with `packages/api/scripts/generate_starter_diagrams.py`.
- Read `docs/ethics-boundary.md` and `docs/data-policy.md` before adding content, data,
  models, or integrations.

## Verification

```bash
uv lock --check
uv run pytest -q
uv run ruff check .
uv run mypy
uv run python packages/api/scripts/generate_api_contract.py --check
uv run python packages/api/scripts/generate_starter_diagrams.py --check
pnpm --dir apps/web test
pnpm --dir apps/web lint
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
uv run python tools/audit_repository.py --root .
```

`pnpm` and Node 24 are not on the system PATH on this laptop. Use the copies bundled with the
Codex runtime: `~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin` and
`~/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback`.

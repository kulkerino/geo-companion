# Geo Companion

Geo Companion is a private, offline-first learning app for studying visual
geography clues without depending on GeoGuessr. Source, decisions, and
reproducibility metadata are tracked; runtime learner data, downloaded packs,
datasets, and model binaries are not.

## Progress and documentation

- [`PROGRESS.md`](PROGRESS.md) shows the current status, the next step, and the decision log.
- [`journal/`](journal/) holds a dated entry for each working session, with commands and results.
- [`CLAUDE.md`](CLAUDE.md) is the working agreement: every session updates both of the above.

## Native development

The committed runtime pins are Python 3.12 and Node 24. The host may use a
newer compatible Node only to bootstrap dependencies; CI validates Node 24.

```bash
uv sync --python 3.12 --all-groups
pnpm install --frozen-lockfile
uv run uvicorn geo_companion.main:app --host 127.0.0.1 --port 8000
pnpm --dir apps/web dev
```

Open `http://127.0.0.1:5173` for the development shell and
`http://127.0.0.1:8000/api/v1/health` to verify the local API. Future work
will have FastAPI serve the built React application; it must remain bound to
loopback and retain SQLite as the laptop's sole live database.

The Vite development server proxies `/api/*` to the loopback FastAPI server;
start both commands above, then use the Open Practice and Study review tabs.
For a reproducible fresh learner database, set an explicit application-data
directory before starting FastAPI:

```bash
GEO_COMPANION_DATA_DIR=/tmp/geo-companion-clean-start \
  uv run uvicorn geo_companion.main:app --host 127.0.0.1 --port 8000
```

After answering a round you can press **Compare with model** to see a local model's opinion.
`GEO_COMPANION_MODEL` picks the provider when FastAPI starts:

- `dummy` (the default) is a clearly labelled placeholder (`dummy-placeholder`) that makes no
  real inference.
- `none` runs without any model.
- `onnx:<manifest path>` loads a real exported country model. Both `manifest.json` and
  `model.onnx` must live outside this repository (for example in the application-data
  directory); the app refuses to start if the model's SHA-256 does not match the manifest,
  and it never downloads a model. It needs the optional `model` dependency group:

```bash
GEO_COMPANION_MODEL=onnx:$HOME/.local/share/geo-companion/training/runs/m1c/manifest.json \
  uv run --group model uvicorn geo_companion.main:app --host 127.0.0.1 --port 8000
```

The photo model abstains on the bundled starter rounds, which are SVG diagrams rather than
photos. See [`docs/model-m1-plan.md`](docs/model-m1-plan.md) and
[`docs/runbook-m1c-rtx-3060.md`](docs/runbook-m1c-rtx-3060.md) for how the model is trained.

No request leaves the laptop: the bundled diagrams are original teaching assets,
not Street View or other captured imagery. They are rendered deterministically by
`packages/api/scripts/generate_starter_diagrams.py` (use `--check` to detect drift).

## Verification

```bash
uv run pytest
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

See [the project brief](docs/project-brief.md), [ethics boundary](docs/ethics-boundary.md),
and [data policy](docs/data-policy.md) before adding content, data, models, or
integrations.

Use [`templates/session-note.md`](templates/session-note.md) for each
substantive session's journal entry.

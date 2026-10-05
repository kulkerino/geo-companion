# Geo Companion

Geo Companion is a private, offline-first learning app for studying visual
geography clues without depending on GeoGuessr. The repository is also an
Obsidian vault: source, decisions, and reproducibility metadata are tracked;
runtime learner data, downloaded packs, and model binaries are not.

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

## Verification

```bash
uv run pytest
uv run ruff check .
uv run mypy
pnpm --dir apps/web test
pnpm --dir apps/web lint
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
git ls-files -ci --exclude-standard
git ls-files | rg '(^|/)(\.env|.*\.(sqlite3|db|onnx|pt|pth|safetensors))$'
```

See [the project brief](docs/project-brief.md), [ethics boundary](docs/ethics-boundary.md),
and [data policy](docs/data-policy.md) before adding content, data, models, or
integrations.

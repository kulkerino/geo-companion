# Task 3 report — standalone offline vertical slice

## RED / GREEN evidence

- RED: `packages/api/tests/test_learning_slice.py` initially failed because the learning
  service did not exist; `apps/web/src/App.test.tsx` failed because the shell had no mode
  controls. The targeted React tests also failed before the answer/review controls existed.
- GREEN: the targeted service/API tests and two React flow tests passed after implementation.
  Final verification is listed below.
- Harness ruling: the installed TestClient/AnyIO combination hung even against a minimal sync
  FastAPI endpoint. The API tests now use `httpx.AsyncClient` with `ASGITransport`; endpoints
  are async. This is an in-process, no-network test transport, and the full suite passes.

## Starter-pack inventory and licensing

- Pack: `starter-original-diagrams` v1.0.0, immutable in `geo_companion.starter_pack`.
- Lessons: exactly three original authored lessons: `road-sign-shapes`, `road-markings`, and
  `clue-confidence`. Each claim/quiz explanation carries source, URL, creator, license,
  attribution, access/review dates, geographic scope, and `cleared` rights status.
- Factual reference: UNECE's Convention on Road Signs and Signals; original prose is deliberately
  cautious and never presents a single clue as proof.
- Assets: exactly ten original project-authored CC0 SVG educational diagram fixtures,
  `diagram-01.svg` through `diagram-10.svg`, in `apps/web/public/starter-assets/`. Each practice
  round records a CC0 attribution record and states it is not Street View/OSV imagery.
- No third-party imagery, network acquisition, model inference, extension, or pack installation
  is included.

## Changed files

- API contracts, starter content, SQLite learning service, lazy app-data service creation, and
  versioned routes in `packages/api/src/geo_companion/`.
- OpenAPI snapshot and generated TypeScript client.
- Service/API/bootstrap tests and the original ten SVG fixtures.
- Accessible Knowledge, Open Practice, and Study UI plus deterministic component flows.

## Verification

```
UV_CACHE_DIR=/tmp/geo-companion-uv-cache uv run pytest -q                 # 45 passed
UV_CACHE_DIR=/tmp/geo-companion-uv-cache uv run ruff check .              # passed
UV_CACHE_DIR=/tmp/geo-companion-uv-cache uv run mypy                       # passed
UV_CACHE_DIR=/tmp/geo-companion-uv-cache uv run python packages/api/scripts/generate_api_contract.py --check
pnpm --dir apps/web test && pnpm --dir apps/web lint && pnpm --dir apps/web typecheck && pnpm --dir apps/web build
UV_CACHE_DIR=/tmp/geo-companion-uv-cache uv run python tools/audit_repository.py --root .
```

All commands passed. The audit command is silent on success.

## Clean-start procedure and result

1. Use a fresh directory through `GEO_COMPANION_DATA_DIR=/tmp/geo-companion-clean-start`.
2. Load lessons, fetch a public lesson and assert no quiz key, submit a deterministic quiz.
3. Fetch a public round and assert no answer/coordinates, skip/uncertain, then receive source
   truth; submit feedback and a grade.
4. Result: all assertions passed and only `runtime.sqlite3` was written under the clean directory.

## Commit

`feat: add offline learning vertical slice` (this focused Task 3 commit).

## Concerns

- The sandbox refuses loopback port binding, so clean-start API verification uses the same ASGI
  transport as tests rather than a bound uvicorn process. A normal local `uvicorn` run is still
  documented and is loopback-only.
- The starter pack intentionally contains diagrams, not cleared real-world imagery. Larger or
  third-party packs remain Task 4/5 work and must clear the existing attribution gate.

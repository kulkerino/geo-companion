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

## Corrective review evidence — 2026-10-07

- Replaced the simulated web flow with generated-client requests for lesson listing/selection,
  lesson quiz, grade, practice next/clue/answer, attempt-linked feedback, and next local review.
  The Vite development server now proxies `/api` to loopback FastAPI and README documents the
  two-process native topology and `GEO_COMPANION_DATA_DIR` clean start.
- Pre-answer browser state contains only the public round. The production-bundle test builds the
  web app and proves the starter country name, coordinates, and hard-coded answer payload are
  absent from JavaScript; the API test proves public round/clue payloads omit answer/coordinates.
- Synthetic diagrams now carry distinct authored language/road-comparison clues. Their answer is
  an `authored` teaching target with no fabricated coordinate, never a claimed geolocated image.
  Original diagrams/text are CC0; UNECE is accurately `reference-only` factual context. Pack
  validation permits such citations but rejects quarantined sources and requires cleared assets.
- Skip, uncertain guess, and skip-as-uncertain are distinct submissions. Attempts rotate through
  rounds; answer results create a practice review schedule. Feedback requires the actual attempt
  ID, updates only that attempt's report flag, and never promotes a dispute to source truth.
- SM-2 now computes interval using the prior ease, then updates ease. The `(5, 5, 3)` regression
  proves the third interval is 16; lapse behaviour remains covered.
- Browser-flow evidence: the API-mocked Vitest flow asserts list/detail requests, quiz request
  body and explanation, grade response, public practice no-leak, clue request, skip request,
  post-reveal feedback attempt linkage, and a visible API error state.
- Final commands: `uv run pytest -q` → 47 passed; Ruff, mypy, OpenAPI drift, Vitest, ESLint,
  TypeScript, Vite build, and repository audit passed. The revised clean-start ASGI smoke created
  only `/tmp/geo-companion-task3-corrective/runtime.sqlite3` and completed lesson→quiz→grade plus
  public practice→clue→skip→reveal→attempt feedback→review without network access.

## Final corrective pass — 2026-10-14

This section supersedes the lesson inventory, UNECE/OSM citation notes, mocked "browser-flow
evidence", and the "audit passed" claim above. Full detail is in
`journal/2026-10-14-task-3-standalone-offline-vertical-slice.md`.

- Scope change from kulo: Knowledge lessons dropped; Task 3 is Open Practice + SM-2 review.
- Ten new deterministic CC0 diagrams (named city + agreeing office wording) with an
  independent evidence audit; generic non-leaking clue; all-cleared publication gate restored.
- Retry same round vs next round, uncertain-correct scheduling, due-date ordering, full
  attribution UI, and a combined React -> FastAPI -> SQLite test via a stdio ASGI bridge.
- The repository audit failed at `7e61cef` (`.superpowers/sdd/.gitignore` ignored itself);
  fixed by removing the redundant file. `typecheck` previously checked nothing; fixed.
- Verification: pytest 62 passed; ruff, mypy, OpenAPI and diagram drift checks, Vitest (6),
  ESLint, typecheck, build, and repository audit all exit 0.
- Real uvicorn + Vite clean-start smoke in the desktop browser pane passed, including API
  restart persistence and a visible 502 while the API was stopped.

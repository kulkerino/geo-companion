# 2026-10-05 — Task 2 content and application contracts

## Intent

Define the versioned, offline-safe content and application contracts that later
learning, pack-lifecycle, model, and integration tasks consume. This task does
not activate packs or implement learner flows.

## Decisions

- `ContentPack` is a frozen, semantically versioned and hash-addressed domain
  object. It validates source, creator, license, citation, and practice-answer
  fields at parse time; `require_publication_ready()` rejects anything whose
  complete attribution chain is not `cleared`.
- Public practice-round responses deliberately contain neither an answer nor
  coordinates. Source truth, user corrections, imported answers, and model
  predictions are distinct contracts so learner or model activity cannot
  overwrite authored ground truth.
- `0001_contract_foundation.sql` establishes only SQLite’s schema-migrations,
  pack-version, study-progress, and practice-attempt tables. It applies through
  the local `initialize_database()` helper; activation and persistence behavior
  remain later tasks.
- FastAPI exposes stable `/api/v1` placeholder contracts for packs, lessons,
  practice, feedback, and study. Empty lists or explicit 404 responses are
  safe until a cleared active pack and learner services exist.
- `packages/api/openapi/openapi.json` and `apps/web/src/api/generated.ts` are
  deterministically generated from FastAPI with a drift check. The generated
  client preserves JSON Schema nullability as TypeScript `null`.

## TDD evidence

- RED: `/home/kulo/.local/bin/uv run pytest packages/api/tests/test_contracts.py
  packages/api/tests/test_contract_api.py
  packages/api/tests/test_storage_and_generated_api.py -q` failed as expected:
  13 failures from missing contracts/storage/generator and absent API routes.
- GREEN: after minimal contracts, migration, routes, and code generation, the
  same command passed 13 tests.
- Regression RED: `test_generated_types_preserve_nullable_contract_fields`
  failed because the generator emitted `string | unknown` for JSON Schema
  nullable fields.
- Regression GREEN: adding JSON Schema `null` rendering made the focused
  storage/generated-API suite pass 3 tests and the web typecheck pass.

## Final verification

All commands exited 0:

- `/home/kulo/.local/bin/uv lock --check`
- `/home/kulo/.local/bin/uv run ruff check .`
- `/home/kulo/.local/bin/uv run mypy` — 5 source files, no issues
- `/home/kulo/.local/bin/uv run pytest` — 28 passed
- `/home/kulo/.local/bin/uv run python packages/api/scripts/generate_api_contract.py --check`
- `pnpm --dir apps/web test` — 1 passed
- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web build`
- `/home/kulo/.local/bin/uv run python tools/audit_repository.py --root .`

## Limitations and follow-up

- The SQLite schema is a migration foundation only; Task 3 implements the
  learner loop and SM-2 grade calculation, while Task 4 owns staged validation
  and atomic active-pack lifecycle behavior.
- No content pack is activated or bundled by this task, and the API therefore
  returns empty/not-found placeholders rather than inventing content.

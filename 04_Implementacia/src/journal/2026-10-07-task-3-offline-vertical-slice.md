# Task 3 — offline learning vertical slice

> **Historical record, superseded.** This note was left uncommitted in the original Codex
> workspace and is kept for history. Its "repository audit clean" claim did not hold (the
> self-ignoring `.superpowers/sdd/.gitignore` failed the audit), and lessons were later dropped.
> See `2026-10-14-task-3-standalone-offline-vertical-slice.md` for the accepted Task 3 record.

- Date: 2026-10-07
- Scope: bundled original starter content, deterministic lesson/practice loops, SM-2 review,
  local SQLite learner state, and accessible React screens.
- Evidence: `uv run pytest -q` → 45 passed; Ruff and mypy clean; generated OpenAPI/client
  current; Vitest, ESLint, TypeScript, production build, and repository audit clean.
- Clean-start: a fresh `GEO_COMPANION_DATA_DIR=/tmp/geo-companion-clean-start` ran lesson,
  quiz, hidden-answer practice, skip/reveal, feedback, and grade through the ASGI app and
  created only `/tmp/geo-companion-clean-start/runtime.sqlite3`.
- Content decision: ten SVGs are project-authored CC0 educational diagrams. They explicitly
  say that they are synthetic fixtures, not Street View, OSV, Mapillary, or real captures.
- Constraint: sandbox loopback port binding was unavailable, so the clean-start path used the
  same in-process ASGI transport as the API tests; no network request was made.

## Corrective review pass

- Replaced local UI simulations with generated-client request flows and a Vite `/api` proxy.
- Eliminated synthetic coordinates and client answer defaults; original diagrams now reveal only
  authored country teaching targets after submission.
- Added attempt-linked feedback, practice progression/review scheduling, prior-EF SM-2 regression,
  production bundle answer scan, and API-mocked browser flow coverage.
- Exact final evidence: `uv run pytest -q` → 47 passed; `ruff check .`, `mypy`, generated OpenAPI
  check, `pnpm --dir apps/web test`, lint, typecheck, build, and repository audit all passed.
- Fresh `GEO_COMPANION_DATA_DIR=/tmp/geo-companion-task3-corrective` ASGI smoke exercised the
  entire offline route and wrote only `runtime.sqlite3`; sandbox still disallows loopback binding.

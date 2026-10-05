# 2026-10-05 — Task 1 repository and audit foundation

## Intent

Establish the pinned native Python/Node workspace, the offline runtime-data
boundary, health endpoint, React shell, and audit/vault conventions.

## Immutable commit evidence

- `411dbfebb045e36e30d89789a616791dec61168d` —
  `chore: establish repository and audit foundation`. The original version of
  this note was included in that immutable foundation commit.
- Review remediation is committed separately after its final checks. This note
  intentionally does not claim the hash of a commit that did not yet exist
  when this text was written.

## Commands and results

### Initial foundation

- RED: `/home/kulo/.local/bin/uv run pytest packages/api/tests/test_bootstrap.py`
  failed with two missing `geo_companion` module failures; `pnpm --dir apps/web
  test` failed because `src/App.tsx` was absent.
- GREEN/final: `/home/kulo/.local/bin/uv run pytest`,
  `/home/kulo/.local/bin/uv run ruff check .`, `/home/kulo/.local/bin/uv run
  mypy`, `pnpm --dir apps/web test`, `pnpm --dir apps/web lint`,
  `pnpm --dir apps/web typecheck`, and `pnpm --dir apps/web build` all passed
  before the foundation commit (2 Python tests and 1 web test).

### Review remediation

- RED: `/home/kulo/.local/bin/uv run pytest packages/api/tests/test_bootstrap.py
  packages/api/tests/test_repository_audit.py` produced 6 expected failures:
  two unsafe `XDG_DATA_HOME` cases resolved inside the vault and four audit
  tests failed because the audit command did not exist.
- GREEN: the same command passed 8 tests after the isolation guard and audit
  command were added. A subsequent bytecode-cache regression test failed with
  `possible secret: packages/__pycache__/cached.pyc`, then passed after cache
  exclusion; the focused suite then passed 9 tests.
- Audit: `/home/kulo/.local/bin/uv run python tools/audit_repository.py --root
  .` exited 0 after scanning the actual working tree.
- Final: `/home/kulo/.local/bin/uv lock --check`, `/home/kulo/.local/bin/uv
  run pytest` (11 passed), `/home/kulo/.local/bin/uv run ruff check .` (passed),
  `/home/kulo/.local/bin/uv run mypy` (3 source files, no issues),
  `/home/kulo/.local/bin/uv run mypy tools/audit_repository.py` (no issues),
  `pnpm install --frozen-lockfile`, `pnpm --dir apps/web test` (1 passed),
  `pnpm --dir apps/web lint`, `pnpm --dir apps/web typecheck`,
  `pnpm --dir apps/web build`, and the audit command all exited 0.

## Decisions

- Data remains outside the vault even when `XDG_DATA_HOME` points inside a Git
  worktree: Geo Companion falls back to a safe user-data path or fails closed.
- The CI audit invokes `uv run python tools/audit_repository.py --root .` and
  inspects ignored working-tree files, not only Git-tracked files.
- Obsidian Templates is enabled through committed core-plugin configuration and
  uses the vault-visible `templates/` folder.

## Limitations and external gaps

- The local host uses Node 26 to bootstrap checks; Node 24 remains the pinned
  and CI target. Python verification used `uv`-provisioned Python 3.12.15.
- GitHub authentication and `gh` remain unavailable. No remote was created or
  pushed, and hosted CI was not run.
- Runtime packs/data and third-party imagery remain intentionally absent.

## Follow-up

Task 2 will define versioned content and application contracts from this
workspace boundary.

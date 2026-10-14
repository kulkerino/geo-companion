# 2026-10-14 — Move the project to ~/Documents/geolearn and set up progress tracking

## Intent

kulo asked to work from `~/Documents/geolearn` instead of the hidden Codex worktree, and to
make sure that progress and work are documented there.

## Evidence

- Commit: the commit that adds this entry (its parent is `a6970c1`).
- Move:
  - `git clone --branch feature/initial-platform ~/Documents/Codex/2026-09-30/could/geoguessr-meta-coach ~/Documents/geolearn`
  - `git branch main origin/main`
  - `git remote rename origin codex-workspace`
  - Copied the ignored `.superpowers/sdd/2026-10-05-geoguessr-meta-learning/` ledger.
  - Copied the old base checkout's uncommitted `journal/2026-10-07-task-3-offline-vertical-slice.md`,
    marked as superseded.
  - The old folder was not modified.
- Setup:
  - `uv sync --python 3.12 --all-groups`
  - `pnpm install --frozen-lockfile --offline` failed with `ERR_PNPM_NO_OFFLINE_META` for one
    package's metadata; `pnpm install --frozen-lockfile --prefer-offline` then succeeded, with
    all 195 packages reused from the local store.
- Verification in the new folder (all exit 0): `uv lock --check`; `uv run pytest -q` → 62
  passed; ruff; mypy; OpenAPI and diagram `--check`; `pnpm --dir apps/web test` → 6 passed;
  lint; typecheck; build; repository audit.
- Decisions: `PROGRESS.md` is the at-a-glance status and decision log; `CLAUDE.md` (with an
  `AGENTS.md` pointer for Codex) requires each session to add a journal entry and update
  `PROGRESS.md` in the same commit as the work; the README links all three.
- Limitations: `pnpm` and Node 24 are still only available from the Codex runtime
  directory, not on the system PATH.

## Follow-up

Connect the app to a dummy model once kulo says to start.

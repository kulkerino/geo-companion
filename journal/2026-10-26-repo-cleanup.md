# 2026-10-26 — Repository cleanup pass

## Intent

kulo asked for a cleanup pass on a new branch `chore/repo-cleanup`, based on
`feature/model-m1`. The pass changes no behaviour: it stops tracking local Obsidian state,
fixes outdated docs and comments, and merges a duplicate path helper.

## Evidence

- Branch: `chore/repo-cleanup` already existed at `4899779` (same as `feature/model-m1`, no
  extra commits), so the work was added on top of it.
- Commits:
  - `b0475db` chore: stop tracking the local Obsidian config. `git rm -r --cached .obsidian`
    (the files stay on disk), and `.gitignore` now ignores `.obsidian/` as a whole.
  - `cc2fd55` docs: README, `docs/audit/README.md`, and `PROGRESS.md` no longer call the repo
    an Obsidian vault or the model a placeholder only. The README now explains
    `GEO_COMPANION_MODEL` (`dummy`, `none`, `onnx:<manifest>`) and shows how to run with a
    real ONNX model.
  - `21d1208` docs: stale comments in `main.py` (packs endpoint) and `storage.py` (it is the
    migration foundation for Task 4; `LearningService` creates its own learner tables).
  - `4985ab1` refactor: `paths.py` had `is_inside_repository` wrapping
    `_is_inside_git_worktree`; now there is one function with the same behaviour.
- Kept on purpose: the migration tables in `packages/api/migrations/` and the planned contract
  models.
- Commands and results (with `UV_CACHE_DIR=/tmp/geo-companion-uv-cache` and the Codex
  runtime's Node/pnpm on `PATH`), all exit 0:
  - `uv lock --check`: Resolved 50 packages
  - `uv run pytest -q`: 112 passed
  - `uv run ruff check .`: All checks passed!
  - `uv run mypy`: Success: no issues found in 22 source files
  - `uv run python packages/api/scripts/generate_api_contract.py --check`: no drift
  - `uv run python packages/api/scripts/generate_starter_diagrams.py --check`: no drift
  - `pnpm --dir apps/web test`: 7 passed
  - `pnpm --dir apps/web lint`, `typecheck`: clean
  - `pnpm --dir apps/web build`: built
  - `uv run python tools/audit_repository.py --root .`: passed
- Limitations: historical journal entries, plans, and handoffs still mention Obsidian; they are
  records of the time and were left as written.

## Follow-up

Review and merge the draft PR into `feature/model-m1`. The project next step is unchanged: M1c
on the RTX 3060 PC.

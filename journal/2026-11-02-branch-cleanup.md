# 2026-11-02 — Branch cleanup after merging PRs #2–#4

## Intent

kulo found the branches confusing and asked for the merging to be sorted out. On GitHub,
PRs #1–#4 were already merged into `main`; the local clone still had stale branches, and
`PROGRESS.md` still described draft PRs on stacked feature branches.

## Evidence

- Commit: this entry together with `PROGRESS.md`, on `docs/progress-after-merges`, one PR into
  `main`.
- Commands and results:
  - `gh pr list --state all` → #1, #2, #3 and #4 are all MERGED.
  - `git merge-base --is-ancestor` → `feature/model-m1` and `chore/repo-cleanup` are both
    contained in `origin/main`.
  - `git checkout main && git merge --ff-only origin/main` → local `main` moved 26 commits
    forward to `79a7642` (the PR #3 merge).
  - `git branch -d feature/model-m1 chore/repo-cleanup`, `git remote prune origin` → both were
    deleted (neither still existed on GitHub).
  - `git log origin/main..origin/rocnikovy-projekt` → 2 commits, with no merge base against
    `main`. It is the separate school-project branch, so it was left alone, with its worktree.
  - No code changed, so the test suites were not rerun.
- Decisions:
  - kulo merges PRs themselves; Claude opens them and keeps local branches tidy.
  - New work goes on short branches from `main`, one PR each, with no stacking.
- Limitations and external gaps:
  - The M1c status in `PROGRESS.md` (14 of 16 epochs, val top-1 0.761) comes from the project
    chat. The M1c journal itself still records the run only up to epoch 5.

## Follow-up

kulo finishes M1c today. Next on the laptop: a model accuracy page that reads the run's
`report.json`.

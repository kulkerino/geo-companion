# Geo Companion — progress

The current state of the project at a glance. Update this file in the same commit as any
work that changes it; detailed evidence for each session goes in [`journal/`](journal/).

**Last updated:** 2026-10-14
**Branch:** `feature/initial-platform` (no GitHub remote yet; nothing has been pushed)
**Next step:** connect the app to a dummy model. Waiting for kulo to start it.

## Task status

| Task | Status | Commit(s) | Journal |
| --- | --- | --- | --- |
| 1. Repository and audit foundation | done, reviewed | `411dbfe`, `ade9730`, `6b1b241` | [2026-10-05](journal/2026-10-05-task-1-repository-audit-foundation.md) |
| 2. Content and application contracts | done, reviewed | `93abbf1`, `70167f1` | [2026-10-05](journal/2026-10-05-task-2-content-application-contracts.md) |
| 3. Standalone offline Open Practice slice | done, self-reviewed | `0ac1ed0`, `7e61cef`, `a6970c1` | [2026-10-14](journal/2026-10-14-task-3-standalone-offline-vertical-slice.md) |
| Dummy-model wiring | next, not started | — | — |
| 4. Pack lifecycle and source tooling | planned | — | — |
| 5. Curriculum pipeline | planned | — | — |
| 6. Optional local model | planned | — | — |
| 7. Windows RTX worker | planned | — | — |
| 8. GeoGuessr review adapter | planned | — | — |
| 9. School delivery | planned | — | — |

The full plan is in
[`docs/superpowers/plans/2026-10-05-geoguessr-meta-learning.md`](docs/superpowers/plans/2026-10-05-geoguessr-meta-learning.md).

## What works today

- Open Practice on ten original CC0 diagrams. You get an optional clue, then guess, guess
  marked uncertain, or skip; the answer and explanation are revealed afterwards. You can
  report a problem with an attempt, retry the same round, or move to the next round.
- SM-2 study review ordered by due date, with "practice this round" from the review screen.
- Everything runs locally: FastAPI on `127.0.0.1:8000`, Vite on `127.0.0.1:5173`, and SQLite
  in the per-user application-data directory (never inside this folder).

## Decisions log

| Date | Decision | Where recorded |
| --- | --- | --- |
| 2026-10-05 | Original diagrams, not third-party imagery, for the starter pack | plan preflight rulings |
| 2026-10-14 | Knowledge lessons dropped; Task 3 is Open Practice only | plan Task 3 note, Task 3 journal |
| 2026-10-14 | Independent review only at big milestones; a self-review pass otherwise | Task 3 journal |
| 2026-10-14 | Project moved to `~/Documents/geolearn` (the history moved with it) | this file |

## Known gaps

- No GitHub remote or authentication.
- The starter pack teaches one deliberately easy cue (a named city) and contains no real
  imagery.
- Storage cleanup for Task 4: the database tables from the original migration are still
  unused, and old development databases keep an unused progress table.

## Location history

Until 2026-10-14 the project lived in the Codex workspace at
`~/Documents/Codex/2026-09-30/could/geoguessr-meta-coach`, with this branch checked out in its
`.worktrees/initial-platform` folder. It was cloned here with full history, both branches,
and the ignored `.superpowers/sdd` task ledger. The old folder is untouched and kept as a
backup. It is registered here as the git remote `codex-workspace`.

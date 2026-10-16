# 2026-10-14 — Task 3 standalone offline vertical slice (Open Practice)

## Intent

Finish Task 3 as a truthful, fully local learning loop that needs no network, model,
browser extension, or desktop worker. This entry closes the corrective pass recorded in
`docs/handoffs/2026-10-13-claude-handoff.md` (review of `7e61cef`).

**Scope change (kulo, 2026-10-14):** Knowledge lessons are dropped. Task 3 now delivers
Open Practice only: public round -> optional clue -> guess / uncertain guess / skip ->
reveal with explanation -> attempt-linked feedback or report -> retry same round or next
round -> SM-2 study review. The plan file records the change.

## Decisions

### Lesson removal

- Removed `/api/v1/lessons*`, the quiz-answer route, `POST /api/v1/study/grades`, the
  `LessonPublic`/`QuizItemPublic`/`QuizAnswer*`/`StudyGrade` API contracts, the Knowledge tab,
  and all three starter lessons (`STARTER_PACK.lessons == ()`).
- The Task 2 domain contracts `Lesson`/`QuizItem` and `ContentPack.lessons` remain dormant so
  the approved Task 2 pack fixtures stay valid; nothing serves them.
- Study state is now keyed by practice round: `StudyProgress.round_id` (was `lesson_id`) with a
  serialised `next_review_on`, stored in a new `learner_review_schedule` table. Old dev
  databases keep an unused `learner_study_progress` table; nothing is deleted.

### Content and rights

- Ten new original diagrams (`apps/web/public/starter-assets/place-panel-01..10.svg`) replace
  the ambiguous `diagram-*.svg` set. Each shows a schematic place-name panel naming a city that
  exists in one country (BRATISLAVA, BRNO, GRAZ, DEBRECEN, KRAKÓW, LJUBLJANA, ZAGREB,
  CLUJ-NAPOCA, LEIPZIG, FIRENZE) plus a municipal-office panel whose language agrees. Every
  diagram prints "Synthetic teaching diagram — not captured imagery or an official sign design".
- SVGs are rendered deterministically from `starter_pack.STARTER_DIAGRAMS` by
  `packages/api/scripts/generate_starter_diagrams.py`; `--check` fails on drift or extra files.
- Answers are `authored` teaching targets with no coordinate. The post-reveal explanation names
  the cue, a limitation/counterexample (e.g. "Rathaus" fits AT/DE/CH; the place name decides),
  and states the diagram is not photographed, geolocated, or an official sign design.
- One generic clue for every round names evidence types only; it contains no country, code,
  demonym, or language name.
- Rights: every asset attribution and answer citation is the project's own CC0-1.0 authored
  material, `cleared`. The OpenStreetMap Wiki (CC BY-SA 2.0) and UNECE references were removed
  rather than asserted as cleared, because no external text or asset is redistributed.
- `ContentPack.is_publication_ready()` requires **every** attribution/citation to be `cleared`
  (its stale docstring claiming reference-only was acceptable is corrected). Tests reject
  `reference-only` and `quarantined` on both an asset and an answer citation.
- Pack version is now `2.0.0`, and `content_hash` is computed from canonical pack content
  instead of a hand-typed constant.

### Behaviour

- **Retry same round** keeps the round and clears the attempt client-side; **Next round** calls
  `/practice/rounds/next`, which advances past the most recently attempted round, so a retry
  never makes the rotation skip a round.
- `GET /api/v1/practice/rounds/{round_id}` reopens a public round; Study review uses it for
  "Practice this round".
- SM-2 quality: confident correct 4, uncertain correct 3, incorrect 2, skipped 1. Three correct
  answers schedule 1/6/15 days (ease 2.5) when confident and 1/6/13 days (ease 2.08) when
  uncertain.
- The review queue is ordered in Python by `last_reviewed_on + interval_days`, then round ID;
  review dates are taken in UTC.
- `country_code` must match `^[A-Z]{2}$`; empty, lowercase, or default guesses are rejected and
  never scored correct.
- SQLite connections are now closed after each unit of work (previously only committed).
- The UI shows source title/link, attribution text, creator, license name/link, rights status,
  geographic scope, and access/review dates for the diagram and for each answer citation. The
  diagram's alt text describes its visible evidence. External links are plain anchors with
  `rel="noreferrer noopener"`; the page makes no non-loopback requests (checked in the smoke).
- Action buttons are disabled while a request is in flight, so one click records one attempt.

### Tooling fixes found on the way

- `.superpowers/sdd/.gitignore` (added in `7e61cef`) ignored itself, so the Task 1 repository
  audit reported `tracked ignored file` at `7e61cef`; the earlier report's "audit passed" did not
  hold on this machine (git 2.53 and 2.56). The redundant nested file is removed; the root
  `.gitignore` already expresses the same rules. The audit itself is unchanged.
- `pnpm --dir apps/web typecheck` ran `tsc --noEmit` against a root config with `"files": []`
  and exited 0 even with a deliberate type error. It now checks `tsconfig.app.json` and
  `tsconfig.node.json`; a probe error now exits 2.

## Tests

- `packages/api/tests/test_starter_content_audit.py`: parses each SVG's `<text>` and checks the
  drawn place name against an independent gazetteer and the drawn office wording against an
  independent language table; one place and one wording per diagram, no contradicting place;
  disclaimer present; explanation names cue, limitation, and authored nature; no country,
  code, demonym, or language name in public JSON, clue, or SVG; SVGs have no script, image,
  href, `url(`, or external URL; generator `--check`; hash and all-cleared gate (8 cases).
  Mutation checks: swapping GRAZ's answer to DE, adding "Slovak" to the clue, or drawing
  "Comune" on the GRAZ diagram each made the audit fail.
- `packages/api/tests/test_learning_slice.py`: SM-2 regressions (including `(5, 5, 3)` -> 16),
  no-leak public round and clue, malformed guesses, attempt-linked report, retry vs next,
  wrap-around, uncertain vs confident schedules, due-date ordering, UTC dates, clean start,
  persistence across a new service, and the ASGI API flow including retired lesson routes 404.
- `apps/web/src/App.integration.test.tsx` (combined React -> FastAPI -> SQLite): the rendered
  app's `fetch` is answered by `packages/api/scripts/asgi_stdio_bridge.py`, a Python process
  running the unmodified FastAPI app whose lazy `service()` opens SQLite under a temporary
  `GEO_COMPANION_DATA_DIR`. It covers no-leak -> clue -> wrong guess -> reveal -> report (checked
  in SQLite with `node:sqlite`) -> retry -> uncertain correct -> next -> skip -> study review ->
  reload with a new API process and fresh React tree -> practise the scheduled round, plus a
  real 500 from the API shown as an alert. Changing `QUALITY_INCORRECT` in the Python service
  made this web test fail, confirming it exercises the real service.
- `apps/web/src/viteConfig.test.ts`: loopback host and `/api` proxy target.
- `apps/web/src/App.test.tsx`: stubbed-fetch component checks only (guess validation, retry
  makes no request, in-flight guard, network failure). It is not described as end-to-end.

## Verification (this machine, CachyOS, Python 3.12.15, Node 24.19.0, pnpm 11.25.0)

All exited 0, with `UV_CACHE_DIR=/tmp/geo-companion-uv-cache`:

- `uv lock --check`
- `uv run pytest -q` — 62 passed
- `uv run ruff check .` — all checks passed
- `uv run mypy` — no issues in 7 source files
- `uv run python packages/api/scripts/generate_api_contract.py --check`
- `uv run python packages/api/scripts/generate_starter_diagrams.py --check`
- `pnpm --dir apps/web test` — 3 files, 6 tests passed
- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web build`
- `uv run python tools/audit_repository.py --root .`

## Clean-start smoke (real processes, loopback)

1. `GEO_COMPANION_DATA_DIR=/tmp/geo-companion-clean-start-task3 uv run uvicorn
   geo_companion.main:app --host 127.0.0.1 --port 8000` (directory did not exist beforehand)
   and `pnpm --dir apps/web dev`; both listened on `127.0.0.1` only.
2. Through the Vite proxy: `/api/v1/packs` returned pack `2.0.0`; `/practice/rounds/next`
   returned `starter-place-01` with no answer; `/api/v1/lessons` returned 404; the SVG served
   as `image/svg+xml`.
3. In the desktop app's browser pane at `http://127.0.0.1:5173/`: clue; guess `cz` ->
   "Not correct: you guessed CZ.", answer SK with explanation and citation; Report issue;
   Retry same round (same round 01); uncertain `SK` -> "Correct (marked uncertain)." with
   review 2026-10-15, ease 2.04; Next round -> 02; Skip; Study review -> round 01 due
   2026-10-15. Pre-answer page text contained no country name.
4. Stopping uvicorn and reloading showed "Geo Companion API request failed: 502". Restarting
   uvicorn on the same directory and reloading opened round 03 (rotation persisted); Study
   review still listed round 01; "Practice this round" reopened round 01.
5. Every resource the page loaded came from `http://127.0.0.1:5173`. The data directory
   contained only `runtime.sqlite3` with tables `learner_feedback`,
   `learner_practice_attempts` (3 rows, the first with `reported_issue = 1`), and
   `learner_review_schedule` (rounds 01 and 02).

## Commit identity

This entry is committed together with the code in one focused Task 3 commit whose parent is
`7e61cef fix: complete offline learning flow`. The commit's own hash cannot be written inside
itself; `git log --oneline -1 -- journal/2026-10-14-task-3-standalone-offline-vertical-slice.md`
identifies it.

## Limitations and external gaps

- No third-party imagery: the pack teaches with ten schematic diagrams only. City-to-country
  facts are presented as project-authored teaching material, not as sourced citations.
- The diagrams teach a deliberately easy cue (a named city); they do not teach real sign
  designs, which would need sourced, cleared references.
- The migration-0001 tables (`study_progress`, `practice_attempts`) are still not used by
  `LearningService`, which owns its own tables; reconciling them belongs to Task 4's storage
  work. `LearningService` trusts its caller for path containment (`main.service()` uses
  `application_data_dir()`).
- React StrictMode calls `/practice/rounds/next` twice in development; it is a read and is
  harmless.
- No GitHub remote or authentication exists; nothing was pushed.
- Independent review is now required only at big milestones; this task had one self-review
  pass against the handoff's High/Medium list instead of a separate reviewer.

## Follow-up

Next step (waiting for kulo): wire the app to a dummy model. Task 4 has not been started.

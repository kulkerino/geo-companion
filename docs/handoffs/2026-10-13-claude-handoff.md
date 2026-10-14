# Handoff for Claude — Geo Companion

**Prepared:** 2026-10-13  
**Repository worktree to resume:** `/home/kulo/Documents/Codex/2026-09-30/could/geoguessr-meta-coach/.worktrees/initial-platform`  
**Branch:** `feature/initial-platform`  
**Status:** Tasks 1 and 2 are approved. Task 3 is in a third corrective pass and is **not approved**. Do not start Task 4 or later work until Task 3 has passed a new independent review.

## How to use this handoff

Treat this file and the existing implementation plan as the authoritative continuation context. Preserve the current dirty worktree; it is deliberate, unfinished Task 3 work. Do **not** use `git reset --hard`, `git checkout --`, or delete untracked files.

Before editing, run:

```bash
cd /home/kulo/Documents/Codex/2026-09-30/could/geoguessr-meta-coach/.worktrees/initial-platform
git status --short
git log --oneline -8
```

The last committed baseline is:

```text
7e61cef fix: complete offline learning flow
```

At handoff time, the intentional uncommitted Task 3 changes are:

```text
M  apps/web/src/App.tsx
M  packages/api/src/geo_companion/contracts.py
M  packages/api/src/geo_companion/learning.py
M  packages/api/src/geo_companion/starter_pack.py
M  packages/api/tests/test_learning_slice.py
?? packages/api/tests/test_starter_content_audit.py
```

This handoff file itself will also be uncommitted. Review all dirty changes before adding more.

## Product goal

Build an offline-first visual-geography learning application. It must stand on its own without GeoGuessr, cloud services, a model, or the Windows desktop. The three product modes are:

1. **Knowledge** — sourced country/region/meta lessons, comparisons, flashcards, quizzes, and SM-2 review.
2. **Open Practice** — licensed/cleared image or diagram rounds with known answers, then reveal and feedback.
3. **Optional GeoGuessr Review** — post-guess import of completed personal solo rounds; this comes much later and must never assist active play.

The current delivery target is a fully working standalone starter pack. It uses **original instructional diagrams**, not Street View, Mapillary, OSV-5M, GeoGuessr screenshots, or model inference. Do not misrepresent these diagrams as real imagery or geolocated scenes.

## Non-negotiable project constraints

- Laptop/CachyOS is authoritative: FastAPI + React + SQLite + installed packs + learner progress. It works in airplane mode.
- Runtime data is outside the repository/Obsidian vault; model binaries and packs are never committed.
- Python 3.12 with `uv`; Node 24 LTS with `pnpm`. The local host previously used newer Node only for bootstrapping; keep version pins and CI expectations intact.
- FastAPI is loopback-only (`127.0.0.1:8000`). SQLite has one writer/application owner.
- Pydantic/OpenAPI is the source of truth; TypeScript API types are generated, not independently hand-designed.
- Only `cleared` content can be in an **active** pack, inference evidence, or training. `reference-only` may assist research but cannot make an active pack publication-ready.
- Every lesson/practice asset exposes creator, source URL, license name/URL, attribution, access/review dates, geographic scope, and rights state in the interface.
- Answers and coordinates are hidden until a learner submits or skips. A country answer never establishes that a particular “meta” was visible.
- Learner guesses, time, hint use, and confidence affect scheduling only; they are not visual ground truth or automatic model labels.
- No telemetry, account system, public hosting, model download, full OSV-5M download, live scraping, generated lesson authoring, GeoGuessr API, competitive help, or online model update in v1.
- Optional GeoGuessr extension: English `/game/*` solo only, result visible + explicit confirmation before any backend activity. Fail closed for all other contexts.

Read before making design changes:

- `docs/superpowers/specs/2026-10-05-geoguessr-meta-learning-design.md`
- `docs/superpowers/plans/2026-10-05-geoguessr-meta-learning.md`
- `docs/ethics-boundary.md`
- `docs/data-policy.md`
- `.superpowers/sdd/2026-10-05-geoguessr-meta-learning/progress.md`

## Repository structure

```text
apps/web/                         React + Vite + Vitest user interface
  src/App.tsx                     current Knowledge/Open Practice/Study application
  src/api/generated.ts            generated API client; regenerate, do not hand-edit
  public/starter-assets/          10 original SVG instructional fixtures
packages/api/
  src/geo_companion/contracts.py  Pydantic domain/API contracts
  src/geo_companion/main.py       FastAPI routes and lazy service access
  src/geo_companion/learning.py   SQLite learning service and SM-2 behavior
  src/geo_companion/starter_pack.py
                                  bundled authored starter pack
  openapi/openapi.json            committed API snapshot
  scripts/generate_api_contract.py
                                  OpenAPI snapshot + TypeScript client generator
  tests/                          contract, storage, vertical-flow, audit tests
tools/audit_repository.py         committed secret/runtime-artifact audit
docs/                             design, policies, audit, handoffs
journal/                          required dated Obsidian entries (Task 3 entry missing)
.superpowers/sdd/...              ignored task briefs, reports, diffs, and progress ledger
```

## Native commands

```bash
cd /home/kulo/Documents/Codex/2026-09-30/could/geoguessr-meta-coach/.worktrees/initial-platform

uv sync --python 3.12 --all-groups
pnpm install --frozen-lockfile

uv run uvicorn geo_companion.main:app --host 127.0.0.1 --port 8000
pnpm --dir apps/web dev
```

The Vite development server is intended to proxy `/api/*` to FastAPI. The sandbox used for prior work prohibits loopback binding, so automated tests use `httpx.AsyncClient` + `ASGITransport`; a real CachyOS run must still be verified manually.

Full verification target:

```bash
UV_CACHE_DIR=/tmp/geo-companion-uv-cache uv run pytest -q
UV_CACHE_DIR=/tmp/geo-companion-uv-cache uv run ruff check .
UV_CACHE_DIR=/tmp/geo-companion-uv-cache uv run mypy
UV_CACHE_DIR=/tmp/geo-companion-uv-cache uv run python packages/api/scripts/generate_api_contract.py --check
pnpm --dir apps/web test
pnpm --dir apps/web lint
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
UV_CACHE_DIR=/tmp/geo-companion-uv-cache uv run python tools/audit_repository.py --root .
```

Use a fresh runtime directory for a clean-start proof:

```bash
GEO_COMPANION_DATA_DIR=/tmp/geo-companion-clean-start \
  uv run uvicorn geo_companion.main:app --host 127.0.0.1 --port 8000
```

Do not claim a real port-bound test passed in this sandbox if it did not. Document the ASGI limitation precisely.

## Completed work and approved checkpoints

### Task 1 — repository and audit foundation — approved

Commits:

```text
411dbfe chore: establish repository and audit foundation
ade9730 fix: harden runtime and repository audits
6b1b241 fix: enforce tracked runtime and key audits
```

Delivered:

- Native Python/React monorepo and Obsidian vault conventions.
- Version pins, lockfiles, README, CI, `.gitignore`, docs, journal templates.
- Runtime-data isolation that rejects repository/vault locations even if hostile XDG paths are supplied.
- Repository audit that detects secrets, PEM keys, large-file secrets, model/runtime artifacts, and force-added prohibited runtime paths.
- Tests, linting, types, production web build, lock checks, audit checks.

Review history matters: Task 1 required multiple review/fix loops. Do not weaken audit or application-data containment.

### Task 2 — contracts and foundations — approved

Commits:

```text
93abbf1 feat: define content and application contracts
70167f1 fix: harden content contract boundaries
```

Delivered:

- Pydantic contracts for content packs, attributions/rights, lessons, quiz items, practice rounds, answer provenance, feedback, progress, model manifests, and experiments.
- SQLite storage/migration foundation.
- Required API surface in an honest pre-Task-3 state.
- OpenAPI snapshot and generated TypeScript client.
- Critical contract corrections: genuine skip semantics; required request body/path parameters in generated client; no false `202` success when an endpoint is not implemented; SQLite path containment under app data; immutable/versioned model artifact identity for experiments.

Never regress these rules. In particular, `ContentPack.is_publication_ready()` must require **all** content attributions/citations to be `RightsStatus.CLEARED`.

## Task 3 baseline and review record

Task 3 is the standalone vertical slice. The last committed work is:

```text
0ac1ed0 feat: add offline learning vertical slice
7e61cef fix: complete offline learning flow
```

Commit `7e61cef` reported 47 Python tests plus web test/lint/type/build, OpenAPI drift, repository audit, bundle no-leak scan, and ASGI clean-start smoke. That result is **not approval**. Independent review found serious content-integrity, behavior, and test-scope defects afterwards.

### What already exists

- FastAPI endpoints for lessons, lesson quiz answers, practice next/clue/answer, feedback, study progress/review/grade.
- `LearningService` backed by SQLite under application data.
- Public practice payloads separate from post-answer results.
- React tabs for Knowledge, Open Practice, Study.
- Generated client usage and Vite proxy configuration.
- Original CC0 SVG starter diagrams in `apps/web/public/starter-assets/`.
- Starter pack with 3 lessons and 10 teaching rounds.
- Attempt-linked feedback and a production-build scan intended to catch answer leakage.

### Previous review failures fixed in `7e61cef` (recheck; do not assume)

- The original UI was only a fake demo. It now attempts generated-client API calls.
- Country/coordinates were previously bundled in the browser and injected as guesses. The client must now receive only public round data until answer submission.
- Feedback now has/uses an attempt identity.
- SM-2 third-success behavior was corrected to use prior ease factor before updating it.
- Vite proxy was added.
- UI gained attribution fields and diagram rendering.

### Latest independent review: blocking findings that remain

The reviewer rejected Task 3 at `7e61cef` for the following concrete reasons. These are the mandatory acceptance criteria for the next correction:

#### High 1 — clue text leaks answers

`starter_pack.py` gave public optional clues such as “Slovak-looking”, “Czech”, “Hungarian”, etc. This semantically reveals the country even if no `answer` JSON key exists.

Required fix:

- Public clue text must not contain the answer country, country code, demonym, or obvious answer alias.
- Make clues generic, e.g. “Inspect place-name, language feature, and sign category,” while the **diagram** contains the actual learnable evidence.
- Add a test for every starter round that bans country/code/demonym tokens in public clue text. The unfinished `test_starter_content_audit.py` begins this work but is incomplete.

#### High 2 — ambiguous diagrams cannot be scored as uniquely correct

Examples cited by review:

- `POZOR` does not prove Czechia versus other language contexts.
- `AUSFAHRT` cannot distinguish Austria from Germany without another visible cue.
- `IZLAZ` is regional and cannot prove Croatia alone.

Required fix:

- Replace all ambiguous synthetic fixtures with ten distinct original diagrams that show deterministic, defensible country evidence.
- Use visible evidence such as a specific country-unique place name plus appropriate language/sign context; do not merely claim that the evidence is there in metadata/clue text.
- Do not invent a coordinate or claim a synthetic diagram is a geolocated capture.
- The answer must be `AUTHORED` teaching truth, with explanation explicitly saying it is an authored teaching target—not verified photographed source truth.
- Explain the cue and a counterexample/limitation after reveal.
- Add a substantive content audit checking the actual SVG text/evidence and mapping it to the intended round. “Ten files have distinct text” is insufficient.

#### High 3 — active-pack rights gate was weakened

`7e61cef` changed `ContentPack.is_publication_ready()` to accept `reference-only` citations. That violates Task 2 and the core data policy.

Required fix:

- Active pack must be publication-ready only if **every** attribution/citation/answer citation is `CLEARED`.
- `reference-only` may be stored only for research/review outside active packs.
- Do not call an official page “cleared” merely because it is public. A compatible explicit license/permission and license URL are required.
- The dirty change restores `all(... is CLEARED)`, but verify it survives and tests both rejected `reference-only` and accepted fully cleared content.
- The dirty change uses OpenStreetMap Wiki as CC BY-SA 2.0. Independently confirm that this source and specific attribution/license representation really meet the project’s intended reuse conditions before retaining it. If uncertain, use a more defensible explicit public-domain/CC source or reduce the claim to original teaching material with cleared author attribution only.

#### Medium 1 — retry is not retry

The previous “Retry / next round” called `next_round()` and always advanced. Required UI behavior:

- **Retry same round:** retain same public asset/round ID, clear learner attempt state, do not advance rotation.
- **Next round:** request/advance to the next selection.
- Test both behavior paths.

The dirty `App.tsx` changes the UI to separate buttons and `LearningService.round_public()` exists. Verify the end-to-end semantics rather than assuming it works.

#### Medium 2 — scheduling semantics

- A correct uncertain answer must schedule differently from a correct confident answer (the product teaches that uncertainty improves scheduling).
- `next_review()` must order by computed due date (`last_reviewed_on + interval_days`), not raw `last_reviewed_on`.
- The dirty `learning.py` implements a quality 3 for uncertain correct vs 4 confident correct and changes SQL ordering. Verify with tests and check it does not have SQLite/date-format edge cases.

#### Medium 3 — attribution and diagram UI

- Knowledge UI must render `lesson.diagram_asset_id` with useful alt text.
- Lesson and practice UI must visibly show attribution text, creator, source link, license/link, and rights status.
- The dirty UI adds these fields. Verify it works for all assets and does not make unsafe external network requests.

#### Medium 4 — combined vertical test is still missing

Prior web tests mocked every `fetch`, while API tests used ASGI separately. This does not prove React -> FastAPI -> SQLite persistence, Vite proxy connectivity, or error handling together.

Required fix:

- Add a real combined test. Because the sandbox blocks loopback sockets, a legitimate solution is an in-process/stdio bridge that routes the rendered app’s `fetch` calls into the real FastAPI ASGI app while retaining one temporary SQLite database for the entire test.
- It must exercise rendered UI actions and real endpoint effects: lesson list/detail -> quiz -> grade; public practice no-leak -> clue -> submit/skip -> reveal; attempt-linked feedback/report; persistence across a reload/new service; visible API error state.
- Keep a separate Vite proxy configuration test. Do not call a fully mocked request test “end-to-end.”
- If a real browser/port test is impossible in this environment, say exactly what was run and why; do not fabricate a smoke result.

#### Medium 5 — required journal is missing

Create and commit `journal/2026-10-13-task-3-standalone-offline-vertical-slice.md` (or a correctly dated equivalent). It must include:

- task objective and scope;
- content/rights decisions and all remaining limitations;
- exact verification commands and their results;
- clean-start procedure/evidence;
- commit identifier strategy (the entry may be committed together with the code, so record the parent or use a follow-up evidence commit honestly);
- external setup gaps: GitHub remote/auth absent; sandbox loopback limitation; no real third-party imagery in starter pack.

## Current unfinished dirty changes

These changes are valuable but not yet verified as a coherent patch:

- `contracts.py`: restores `ContentPack.is_publication_ready()` to require all attributions/citations be `CLEARED`.
- `starter_pack.py`: replaces UNECE reference-only citation metadata with an asserted OpenStreetMap Wiki CC BY-SA 2.0 citation; genericizes clue text to remove country names.
- `learning.py`: adds `round_public()`, gives a correct uncertain answer lower practice quality, and orders reviews by calculated due date.
- `App.tsx`: renders lessons diagrams/attribution metadata and separates “Retry same round” from “Next round.”
- `test_learning_slice.py`: adds retry, uncertain-scheduling, and due-date ordering tests.
- `test_starter_content_audit.py`: new, untracked partial audit. It presently checks only clue-name tokens, cleared statuses, and distinct SVG file text. It must be strengthened to validate actual deterministic evidence/cue mapping and the publication gate.

Do not commit these blindly. Reconcile all source metadata and SVG content, regenerate OpenAPI/client if contract changes require it, and run the full suite.

## Relevant API and behavior contracts

The implemented Task 3 route names are currently:

```text
GET  /api/v1/health
GET  /api/v1/packs
GET  /api/v1/lessons
GET  /api/v1/lessons/{lesson_id}
POST /api/v1/lessons/{lesson_id}/quizzes/{quiz_id}/answers
GET  /api/v1/practice/rounds/next
GET  /api/v1/practice/rounds/{round_id}/clue
POST /api/v1/practice/rounds/{round_id}/answers
POST /api/v1/feedback
GET  /api/v1/study/progress/{lesson_id}
GET  /api/v1/study/review/next
POST /api/v1/study/grades
```

Rules to preserve:

- `PracticeRoundPublic` has no answer, country code, country name, exact coordinates, answer citation, or model prediction.
- A clue must be non-answer-revealing guidance. It is not an excuse to put the country into the public payload.
- On answer submission, source/authoritative answer is revealed. Empty/default guesses must never silently become the correct answer.
- `Feedback` must include the exact `attempt_id` from the revealed answer. A reported issue only marks that attempt and must not overwrite verified source truth or enter active study history as a known answer.
- Skip and uncertain are separate booleans/states and need validated combinations.
- SM-2 computes the next repetition interval from prior EF, then adjusts EF. Existing regression target: qualities `(5, 5, 3)` yield interval 16 on the third review.
- Study selection is due-date ordered and local/pseudonymous.
- Model outputs/imported GeoGuessr answers/user corrections must remain distinct from source truth in contracts/UI. The current starter pack should not exercise model or GeoGuessr paths.

## Task 3 acceptance gate

Do not call Task 3 complete until all of these are true:

- Clean installation can complete Knowledge -> quiz -> explanation -> grade -> scheduled review and Open Practice -> clue -> guess/skip/uncertain -> reveal -> feedback/report/retry -> review with no network, model, extension, or desktop worker.
- At least 3 substantive original authored lessons and >=10 original, cleared, semantically valid instructional diagrams are present.
- Every active-pack citation/asset/answer citation is cleared and shown in the UI.
- Pre-answer output does not leak the answer directly or semantically.
- Answers have defensible deterministic teaching targets; diagrams explicitly disclose their synthetic, authored nature.
- SQLite persists state outside the repository, and clean-start produces only local runtime state.
- A meaningful combined UI/API/SQLite test and a clean-start smoke test pass.
- Journal entry is committed.
- Full verification passes and a new independent reviewer returns no High or Medium findings.

## Later tasks — do not start before Task 3 approval

### Task 4 — pack lifecycle and source tooling

Implement stage -> validate -> hash verify -> atomically activate, with rollback/removal/storage reporting/source ledger/attribution UI. Corrupted, incomplete, incompatible, or improperly licensed packs must never activate. Do not add live network downloads to test fixtures.

### Task 5 — curriculum pipeline

Implement reproducible curation/split/dedup/audit tooling capable of creating a 900-round pack from separately obtained, cleared input. Required split: 630 train/retrieval eligible, 135 validation, 135 locked shadow test, grouped by round/sequence/geocell. Do not fabricate a 900-round pack or its provenance. Full OSV-5M is 259 GB and out of scope.

### Task 6 — optional local model

Frozen local provider boundary, no-model fallback, optional ONNX and retrieval, abstention/model manifests/evaluation/benchmark gates. Never download model weights implicitly. No online training or automatic lesson generation.

### Task 7 — Windows RTX worker

Outbound Tailscale polling/leases only; immutable artifacts/hashes/heartbeats/retry/fallback. Worker does not own or replicate SQLite; laptop works if desktop is absent.

### Task 8 — GeoGuessr review adapter

Manifest V3, English solo `/game/*` only, session-memory capture, no upload/prediction/embedding/clue before visible result and explicit confirmation. Block multiplayer/ranked/challenges/replay/spectator/logged-out/unknown states. Keep screenshots quarantined unless their use is expressly cleared.

### Task 9 — school delivery

CPU Docker smoke artifact (not primary runtime), clean-room scripts, model/dataset cards, licensing appendix, architecture diagrams, demo script, report/evidence traceability. New evaluator must be able to run the standalone demo offline.

At Tasks 5, 8, and 9, run independent architecture, ML/data, and delivery/safety reviews, store them under `docs/reviews/YYYY-MM-DD-gate-N/`, and record accepted/rejected recommendations in an ADR. Do not proceed past unresolved P0 findings.

## External environment/setup gaps

- No GitHub CLI/authentication was available; the repository has no private GitHub remote yet. Do not create a public remote as a workaround.
- The worktree is a linked Git worktree. The project’s base repository is `/home/kulo/Documents/Codex/2026-09-30/could/geoguessr-meta-coach`.
- Sandbox loopback binding is unavailable. Validate a real native Vite + Uvicorn session manually on CachyOS later.
- No real Mapillary/OSV imagery has been acquired. That is intentional. Any later Mapillary/OSV pack needs creator/image/sequence/source/license/attribution metadata and an external legal/terms review before caching or redistribution.
- No model weights, ONNX Runtime integration, Tailscale worker, Docker image, extension, or cloud deployment exists yet.
- The optional cloud budget remains $20 total with alerts at $10/$15 and hard cutoff at $18; this does not buy rights clearance or continuous GPU hosting.

## Recommended continuation workflow

1. Read the relevant files and preserve the dirty changes.
2. Run targeted tests for the dirty patch and inspect the rendered SVG text. Ensure evidence, citation licenses, and answer keys match.
3. Finish the true combined React -> FastAPI -> SQLite test or document a technically valid substitute that genuinely uses the real API/service/database, not fixed JSON mocks.
4. Add the Task 3 journal entry and improve `task-3-report.md` in `.superpowers` with real final evidence.
5. Run the entire verification suite from a fresh app-data directory.
6. Make a focused Task 3 corrective commit; do not bundle Task 4 work.
7. Obtain an independent review specifically against every High/Medium item listed above. Fix all High/Medium findings before marking Task 3 complete.
8. Update `.superpowers/sdd/.../progress.md` only after approval, then proceed to Task 4.

## Suggested opening prompt for Claude

> You are resuming the Geo Companion repository at `/home/kulo/Documents/Codex/2026-09-30/could/geoguessr-meta-coach/.worktrees/initial-platform` on branch `feature/initial-platform`. Read `docs/handoffs/2026-10-13-claude-handoff.md`, the plan/spec, and `git status` before changing anything. Preserve the intentionally dirty Task 3 worktree. Tasks 1–2 are approved; Task 3 is blocked by a review recorded in the handoff. Complete only Task 3, using strict test-first changes, with special focus on non-leaking clues, deterministic instructional evidence, all-cleared active-pack licensing, actual retry/scheduling/attribution behavior, and a genuine combined React->FastAPI->SQLite test. Do not start Task 4. Run the full verification suite, journal the work, make a focused commit, then obtain/reconcile an independent review before declaring Task 3 complete.

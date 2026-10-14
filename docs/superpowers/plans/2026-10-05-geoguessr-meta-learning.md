# GeoGuessr Meta Learning System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Use test-driven development for behavior changes.

**Goal:** Deliver an offline-first, sourced learning application with Knowledge and Open Practice modes, then add optional model, desktop-worker, and post-guess GeoGuessr integrations.

**Architecture:** The CachyOS laptop runs one FastAPI/SQLite application and serves a React UI. Immutable content packs provide lessons and practice; runtime data lives outside the repository. Optional ONNX inference is local and an optional Windows CUDA worker exchanges immutable artifacts over Tailscale.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy/SQLite, Alembic, pytest, React, TypeScript, Vite, Vitest, pnpm, ONNX Runtime, Docker for CPU smoke testing only.

**Spec:** `docs/superpowers/specs/2026-10-05-geoguessr-meta-learning-design.md`

## Global Constraints

- Project root is also the Obsidian vault; commit shared settings only.
- FastAPI binds to `127.0.0.1:8000`; one application worker owns SQLite.
- Runtime data and model binaries are excluded from Git and resolved with `platformdirs`.
- Pydantic/OpenAPI is the schema source of truth; TypeScript API types are generated.
- The standalone offline learning loop must work without ML, Tailscale, Windows, or GeoGuessr.
- Only `cleared` content can enter active packs, inference evidence, or training.
- Tests precede production behavior and are observed failing before implementation.
- Every task updates the current Obsidian journal, runs the full available suite, and ends in a focused commit.

## Review Focus

- Missing or invalid source/license metadata must block content activation.
- Answers must remain hidden until a learner submits or skips.
- Offline clean-start must not invoke a network or optional integration.
- Runtime data must never fall back into the repository.
- Optional worker or extension failure must not break standalone learning.

---

### Task 1: Repository and audit foundation

**Files:** Create the monorepo/vault skeleton, shared configuration, CI, README, journal templates, project brief, ethics boundary, data policy, and bootstrap tests.

**Interfaces:** Produce locked Python/Node workspaces, `geo_companion` import package, React shell, documented native launch commands, and an audit structure consumed by all later tasks.

- [ ] Write failing bootstrap tests for application-data path isolation, the API health response, and the web test harness.
- [ ] Verify each test fails for the missing behavior.
- [ ] Create the minimal Python/React skeleton, Obsidian settings/templates, GitHub workflows, ignore rules, and documentation.
- [ ] Run Python and web suites, lint/type checks, and a repository secret/artifact check.
- [ ] Add a dated journal entry and commit the task.

### Task 2: Content and application contracts

**Files:** Add Pydantic/domain schemas, storage models and migrations, pack fixtures, API routes, OpenAPI snapshot, and generated TypeScript client.

**Interfaces:** Define packs, lessons, quiz items, practice rounds, answers, attribution, rights status, progress, model manifests, and experiments; expose `/api/v1/packs`, `/lessons`, `/practice`, and `/study` contracts.

- [ ] Write failing schema and API tests using hand-checked fixtures, including rejection of missing source, license, creator, answer, and non-cleared content.
- [ ] Verify expected failures.
- [ ] Implement minimal schemas, SQLite storage, migrations, routes, and OpenAPI generation.
- [ ] Generate TypeScript types and run full Python/web tests.
- [ ] Journal and commit.

### Task 3: Standalone offline vertical slice

> **Scope change (2026-10-14, kulo):** Knowledge lessons are dropped. Task 3 delivers Open
> Practice only (clue -> guess/skip/uncertain -> reveal -> feedback/report -> retry/next ->
> SM-2 review) over ten original cleared diagrams. The lesson items below are superseded; the
> dormant `Lesson`/`QuizItem` domain contracts remain only so Task 2 pack fixtures stay valid.

**Files:** Add a bundled starter pack, learning services, SM-2 scheduling, React Knowledge/Open Practice screens, and end-to-end tests.

**Interfaces:** Implement lesson -> quiz -> explanation -> grade and image -> guess -> reveal -> feedback -> review without network access.

- [ ] Write failing service, API, component, and browser-flow tests for hidden answers, deterministic scoring, persistence, skip/uncertain/retry/report, and review scheduling.
- [ ] Verify expected failures.
- [ ] Implement the minimal end-to-end learning loop with three original lessons and at least ten redistributable generated/diagram fixtures.
- [ ] Run the complete offline test suite and clean-start smoke test.
- [ ] Journal and commit.

### Task 4: Pack lifecycle and source tooling

**Files:** Add staging/verification/activation services, atomic filesystem operations, rollback/removal/storage APIs, attribution UI, CLI validation, and tests.

**Interfaces:** Implement download-or-local install -> stage -> schema/hash/rights verification -> atomic activation, with rollback and deletion.

- [ ] Write failing tests for corrupted hashes, incomplete metadata, incompatible versions, partial installs, rollback, removal, and storage reporting.
- [ ] Verify expected failures.
- [ ] Implement lifecycle services and source-ledger tooling without adding live network download to tests.
- [ ] Run full suites and validate the bundled pack.
- [ ] Journal and commit.

### Task 5: Curriculum pack pipeline

**Files:** Add deterministic curation/split/dedup tooling, manifest schemas, composition reports, attribution reports, country index content, and tiny test fixtures.

**Interfaces:** Produce a reproducible pipeline capable of building the planned 900-round pack from separately obtained cleared inputs; do not fabricate or redistribute unavailable third-party assets.

- [ ] Write failing tests for round/sequence/geocell grouping, 630/135/135 splitting, perceptual duplicate exclusion, country composition, and attribution completeness.
- [ ] Verify expected failures.
- [ ] Implement curation tools and an all-country sourced index framework; populate only facts/assets with verified rights.
- [ ] Run pipeline tests and generate a fixture composition report.
- [ ] Journal and commit, documenting any external-data gap rather than weakening validation.

### Task 6: Local model enhancement

**Files:** Add inference provider interfaces, deterministic no-model provider, ONNX provider, retrieval store, model manifests, benchmark/evaluation tooling, and tests.

**Interfaces:** Keep standalone behavior intact; optional predictions include model ID, runtime, calibrated candidates, and abstention. Enforce model size/memory/latency gates through recorded benchmarks.

- [ ] Write failing provider-contract, abstention, manifest, retrieval-separation, and fallback tests.
- [ ] Verify expected failures.
- [ ] Implement provider boundaries and an optional ONNX path; never download a model implicitly.
- [ ] Run full suites and benchmark any explicitly installed model.
- [ ] Journal and commit.

### Task 7: Windows worker

**Files:** Add leased job storage, worker API/CLI, immutable artifact transfer, hashes, heartbeats, retry/fallback logic, Tailscale documentation, and tests.

**Interfaces:** The worker polls outbound; it never accepts inbound public connections or writes SQLite. The laptop returns local results immediately.

- [ ] Write failing tests for leasing, idempotency, stale heartbeats, duplicate completion, corruption, retry, timeout, and desktop absence.
- [ ] Verify expected failures.
- [ ] Implement the minimal worker protocol and PowerShell setup/launch scripts.
- [ ] Run full suites with a fake local worker, then document manual Windows verification.
- [ ] Journal and commit.

### Task 8: Optional GeoGuessr review adapter

**Files:** Add Manifest V3 extension, local fixture pages, explicit state machine, session-only capture storage, review handoff, permission audit, and tests.

**Interfaces:** English solo `/game/*` only; no backend activity before visible result plus user confirmation; all other modes fail closed.

- [ ] Write failing state-machine, permissions, navigation, unsupported-mode, duplicate-submit, reload, and no-pre-answer-network tests against fixtures.
- [ ] Verify expected failures.
- [ ] Implement the extension against fixtures, then isolate the live-site adapter behind a replaceable parser.
- [ ] Run extension and application suites; audit manifest permissions and network calls.
- [ ] Journal and commit.

### Task 9: School delivery and release evidence

**Files:** Add CPU Docker smoke image, clean-room scripts, report outline/content, cards, evaluation summaries, limitations, licensing appendix, diagrams, demo script, and traceability matrix.

**Interfaces:** A new evaluator can clone, build, run the bundled starter pack offline, inspect evidence, and reproduce fixture metrics.

- [ ] Write failing clean-room/smoke tests for the documented commands and artifact exclusions.
- [ ] Verify expected failures.
- [ ] Implement the reproducibility package and complete the school evidence set.
- [ ] Run all verification commands from a clean checkout or equivalent temporary clone.
- [ ] Journal, perform the final three-domain review, and commit.

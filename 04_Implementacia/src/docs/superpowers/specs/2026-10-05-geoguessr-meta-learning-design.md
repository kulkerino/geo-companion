# GeoGuessr Meta Learning System Design

## Purpose

Build a private, offline-first school project that teaches visual geographic clues without requiring GeoGuessr. The core product provides sourced lessons, deterministic quizzes, and licensed image-practice rounds. An optional post-guess GeoGuessr adapter may later reuse the same review pipeline, but the standalone product must remain complete without it.

## Users and success

The initial user is the project owner on a CachyOS laptop. A successful v1 starts locally without network access, exposes the source and license of every lesson or image, persists progress, schedules review, and supports a complete lesson-to-practice learning loop. The laptop is authoritative; a Windows 11 RTX 3060 desktop is optional compute only.

## Architecture

- FastAPI owns application state, serves the built React UI, and exposes a versioned `/api/v1` interface from `127.0.0.1:8000`.
- SQLite is the sole live database and resides in the laptop's XDG application-data directory, never in Git.
- The repository root is an Obsidian vault. Git tracks code, decisions, manifests, tiny licensed fixtures, and reproducibility metadata, not private runtime data or model binaries.
- Knowledge and Open Practice consume immutable content packs. Packs stage, validate, hash-check, and atomically activate; incomplete or unlicensed packs never become visible.
- A compact ONNX model may enhance local practice later. The deterministic learning loop does not depend on ML inference.
- The Windows worker initiates outbound Tailscale connections and exchanges immutable, hash-verified artifacts. It never replicates or edits SQLite.

## Content and rights

Every lesson claim and image asset records source, creator, URL, access date, license, attribution, geographic scope, review date, and rights status. Rights status is one of `cleared`, `reference-only`, or `quarantined`; only `cleared` items may appear in packs or training. Public availability alone is not permission. Starter content uses original prose and small redistributable visual fixtures; larger OSV-5M/Mapillary packs require complete attribution and a documented license review.

## Learning behavior

Knowledge mode is lesson -> quiz -> cited explanation -> SM-2 grade. Open Practice is licensed image -> optional clue -> submitted guess -> verified answer -> sourced explanation -> feedback -> review schedule. Answers remain hidden until submission. Users may skip, mark uncertain, retry, or report an issue. Known answers, user corrections, model predictions, and imported answers remain distinct.

## ML behavior

The initial ML contract names `student-small.onnx` for required CPU inference and `teacher-large.pt` for optional CUDA inference. Backbones remain frozen in v1. Retrieval and candidates are versioned and evaluation-separated. User guesses influence study scheduling, never visual ground truth. A country label never implies that a meta was visible. Promotion is shadow-only until the documented sample gates are met.

## Optional GeoGuessr adapter

The private Chromium extension supports English solo `/game/*` pages only. Capture is user-triggered and stays in extension session storage. No upload, inference, or clue output occurs until a visible result and explicit post-guess confirmation. Unknown, competitive, unsupported, or ambiguous states fail closed. The adapter uses no private API and is not required for v1 success.

## Audit and delivery

Every substantive session has a dated Obsidian journal note linked to commits, tests, experiments, and decisions. Independent architecture, ML/data, and delivery reviews occur at defined gates. The final school package includes source/license registries, dataset/model cards, evaluation, limitations, ethics, architecture diagrams, a demo script, and a clean-room CPU run.


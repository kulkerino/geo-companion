# 2026-10-05 — Task 1 repository and audit foundation

## Intent

Establish the pinned native Python/Node workspace, the offline runtime-data
boundary, health endpoint, React shell, and audit/vault conventions.

## Evidence

- Commit: `HEAD` — `chore: establish repository and audit foundation`
- RED: bootstrap API and web tests were observed failing before implementation.
- Decisions: data remains outside the vault; API binds to loopback; only
  cleared content can later become active.

## Follow-up

Task 2 will define versioned content and application contracts from this
workspace boundary.

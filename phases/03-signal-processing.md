# Phase 03 — Signal processing

**Status:** Completed locally on 2026-11-19 in branch
`phase/03-signal-processing`. Phase 04 has not started. Evidence is recorded in
`docs/phase-03-report.md`.

## Goal
Compute repeatable vibration features on original-time windows using **the laptop's Docker Compose stack**.

## Prerequisites / inputs
Phase 02 MQTT data, verified sampling rate and axis interpretation.

## Detailed instructions for Codex
1. Add independent signal-processor container
2. validate JSON schema and data gaps
3. form one-second source-time windows
4. document gravity/baseline removal and orientation
5. compute dynamic acceleration RMS, peak deviation, sample count and quality flags
6. publish roadsense/v1/imu/features
7. add synthetic numeric unit tests.

## Deliverables / documentation
Processor code and Dockerfile, numeric tests, feature contract, sample charts and runbook.

## Acceptance / exit gate
- [x] Hand-verified synthetic signals match output
- [x] window calculation invariant under replay-rate changes
- [x] missing/duplicate samples handled
- [x] feature topic delivers records
- [x] do not label potholes.

## Required phase report
Codex must record actual commands (without secrets), files created, test commands and results, observed output screenshots/logs, assumptions, unresolved risks and the rollback procedure when relevant. Do not mark complete on unverified claims.

## Copyable Codex request
Implement **only Phase 03** for RoadSense. First read AGENTS.md, README.md, docs/architecture.md, docs/contracts.md, docs/operations.md, and this phase. Work in a dedicated branch, follow the prerequisites and acceptance gates, deliver the listed documentation and tests, and STOP before the next phase. Do not invent dataset facts, successful tests, or cloud deployment status.

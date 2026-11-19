# Phase 00 — Dataset and course scope

**Status:** Not started. Documentation only.

## Goal
Verify the exact MUHOS data and teacher requirements before choosing processing rules.

## Prerequisites / inputs
Official course README, MUHOS archive URL, permitted download and basic environment info.

## Detailed instructions for Codex
1. Reopen current course Final-Project README
2. confirm VPS counts as local/external Docker or record laptop fallback
3. download one Bosch IMU archive
4. inspect exact schema/timestamp precision/time zone/unit and sampling intervals
5. check missing samples, sensor orientation and attribution
6. select a second contrasting recording
7. produce source data dictionary and profiling results.

## Deliverables / documentation
docs/dataset-profile.md, data dictionary, input-file provenance/checksum, sample plots, documented course interpretation and fixed message contract.

## Acceptance / exit gate
- [ ] CSV fields/sample rates verified from actual files
- [ ] dates/units and limits documented
- [ ] teacher topology risk resolved or escalated
- [ ] attribution confirmed
- [ ] no raw dataset committed.

## Required phase report
Codex must record actual commands (without secrets), files created, test commands and results, observed output screenshots/logs, assumptions, unresolved risks and the rollback procedure when relevant. Do not mark complete on unverified claims.

## Copyable Codex request
Implement **only Phase 00** for RoadSense. First read AGENTS.md, README.md, docs/architecture.md, docs/contracts.md, docs/operations.md, and this phase. Work in a dedicated branch, follow the prerequisites and acceptance gates, deliver the listed documentation and tests, and STOP before the next phase. Do not invent dataset facts, successful tests, or cloud deployment status.

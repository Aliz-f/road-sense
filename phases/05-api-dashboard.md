# Phase 05 — API and dashboard

**Status:** Not started. Documentation only.

## Goal
Show a working end-to-end product in the VPS browser, before cloud migration.

## Prerequisites / inputs
Phase 04 persisted data; API contracts and access plan.

## Detailed instructions for Codex
1. Build FastAPI routes for health/sessions/runs/features/events with validation and pagination
2. build Streamlit/Plotly run selector, vibration chart, alert list and source caveat
3. use HTTP between dashboard and API (never direct DB)
4. keep dashboard private or protected
5. add tests and all-in-one Compose smoke test.

## Deliverables / documentation
API/Dashboard service directories with Dockerfiles, tested local Compose runbook, screenshots and e2e report.

## Acceptance / exit gate
- [ ] Real recorded stream appears in UI
- [ ] API returns correct stored results
- [ ] empty/error states handled
- [ ] dashboard auth/access controlled
- [ ] no direct browser connection to DB.

## Required phase report
Codex must record actual commands (without secrets), files created, test commands and results, observed output screenshots/logs, assumptions, unresolved risks and the rollback procedure when relevant. Do not mark complete on unverified claims.

## Copyable Codex request
Implement **only Phase 05** for RoadSense. First read AGENTS.md, README.md, docs/architecture.md, docs/contracts.md, docs/operations.md, and this phase. Work in a dedicated branch, follow the prerequisites and acceptance gates, deliver the listed documentation and tests, and STOP before the next phase. Do not invent dataset facts, successful tests, or cloud deployment status.

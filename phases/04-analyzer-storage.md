# Phase 04 — Road analyzer and database

**Status:** Not started. Documentation only.

## Goal
Convert feature streams into simple explained events and durable records **on the laptop's Docker Compose environment**.

## Prerequisites / inputs
Phase 03 features, DB schema, initial documented heuristic threshold.

## Detailed instructions for Codex
1. Create road-analyzer subscriber
2. use threshold to flag high-vibration windows
3. write run/session/feature/event data to PostgreSQL via schema migrations
4. enforce unique run/window identifiers and idempotent upsert
5. mount DB volume
6. add reconnect/restart and duplicate tests.

## Deliverables / documentation
Analyzer and DB modules, migrations, Compose additions, threshold rationale, recovery tests.

## Acceptance / exit gate
- [ ] Queryable persisted features/events
- [ ] duplicate delivery creates no extra rows
- [ ] state persists after restart
- [ ] no publicly accessible DB.

## Required phase report
Codex must record actual commands (without secrets), files created, test commands and results, observed output screenshots/logs, assumptions, unresolved risks and the rollback procedure when relevant. Do not mark complete on unverified claims.

## Copyable Codex request
Implement **only Phase 04** for RoadSense. First read AGENTS.md, README.md, docs/architecture.md, docs/contracts.md, docs/operations.md, and this phase. Work in a dedicated branch, follow the prerequisites and acceptance gates, deliver the listed documentation and tests, and STOP before the next phase. Do not invent dataset facts, successful tests, or cloud deployment status.

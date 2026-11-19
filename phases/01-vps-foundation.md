# Phase 01 — VPS readiness and security

**Status:** Not started. Documentation only.

## Goal
Prepare VPS as a reliable secure Docker environment without accidentally exposing data.

## Prerequisites / inputs
Phase 00 complete; user supplies VPS access, OS, RAM/disk, SSH method, domain intention; approval for changes.

## Detailed instructions for Codex
1. Inventory OS/resources/network/services
2. check backup/recovery plan
3. only with approval install Docker/Compose
4. create least-privilege service user, restricted dataset mount and secret-loading strategy
5. set firewall and SSH safeguards without locking user out
6. plan dashboard access over VPN or HTTPS+auth.

## Deliverables / documentation
VPS setup and rollback runbook, capacity inventory, exact verified commands, Docker health proof, secrets procedure.

## Acceptance / exit gate
- [ ] Docker Compose available
- [ ] dataset mount private/read-only
- [ ] no unexpected public ports
- [ ] user retains SSH access
- [ ] changes and rollback documented.

## Required phase report
Codex must record actual commands (without secrets), files created, test commands and results, observed output screenshots/logs, assumptions, unresolved risks and the rollback procedure when relevant. Do not mark complete on unverified claims.

## Copyable Codex request
Implement **only Phase 01** for RoadSense. First read AGENTS.md, README.md, docs/architecture.md, docs/contracts.md, docs/operations.md, and this phase. Work in a dedicated branch, follow the prerequisites and acceptance gates, deliver the listed documentation and tests, and STOP before the next phase. Do not invent dataset facts, successful tests, or cloud deployment status.

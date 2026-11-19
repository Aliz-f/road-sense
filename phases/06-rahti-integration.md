# Phase 06 — Rahti and VPS integration

**Status:** Not started. Documentation only.

## Goal
Move backend to Rahti while feeder/dashboard remain on the VPS; prove cross-environment flow.

## Prerequisites / inputs
Phase 05 working Compose; CSC project credentials/quotas, approved registry and TLS plan; explicit deployment approval.

## Detailed instructions for Codex
1. Inventory Rahti permissions/storage/routes
2. push pinned images
3. create Deployment/Service/ConfigMap/Secret template/PVC/Route manifests
4. validate MQTT TLS passthrough or supported equivalent
5. keep PostgreSQL internal
6. move processor, analyzer, API, broker and DB to Rahti
7. point VPS feeder/dashboard to secure Rahti endpoints
8. verify recoverability, log evidence, rollback.

## Deliverables / documentation
infrastructure/rahti manifests and runbook, environment templates, Rahti resource inventory, cross-environment evidence, rollback procedure.

## Acceptance / exit gate
- [ ] Rahti pods healthy and DB persistent
- [ ] VPS->Rahti MQTT/TLS and Rahti->VPS API HTTPS functional
- [ ] full CSV->MQTT->features->events->DB->API->dashboard trace
- [ ] no secrets publicly exposed.

## Required phase report
Codex must record actual commands (without secrets), files created, test commands and results, observed output screenshots/logs, assumptions, unresolved risks and the rollback procedure when relevant. Do not mark complete on unverified claims.

## Copyable Codex request
Implement **only Phase 06** for RoadSense. First read AGENTS.md, README.md, docs/architecture.md, docs/contracts.md, docs/operations.md, and this phase. Work in a dedicated branch, follow the prerequisites and acceptance gates, deliver the listed documentation and tests, and STOP before the next phase. Do not invent dataset facts, successful tests, or cloud deployment status.

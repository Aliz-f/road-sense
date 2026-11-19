# Phase 01 — Local laptop development foundation

**Status:** Completed on 2026-11-19 in branch
`phase/01-local-foundation`. Phase 02 has not started. Evidence is recorded in
`docs/local-development.md` and `docs/phase-01-report.md`.

## Goal
Prepare a reproducible, safe development environment on the **local laptop**, not on the VPS.

## Inputs
Phase 00 data profile; laptop OS, CPU/RAM/disk, Docker availability, and consent for local package installations.

## Instructions
1. Inspect laptop Docker Engine/Compose versions, free disk space and permissions.
2. Prepare local repository clone and a Git-ignored private dataset folder/mount.
3. Define environment-specific configuration templates for `local`, future `vps`, and future `rahti` without placing secrets in Git.
4. Plan local Compose service names, private Docker network, service health checks and loopback-only UI/API debug ports.
5. Document reproducible developer setup, data acquisition, local startup/teardown and troubleshooting commands.
6. Verify a minimal Docker Compose preflight only after explicit implementation approval.
7. Do **not** configure the VPS or Rahti yet.

## Deliverables
Local setup guide, development environment template, dataset mount instructions, Docker/Compose preflight report, local environment risk checklist.

## Exit checklist
- [x] Laptop Docker and Compose environment verified.
- [x] Private data folder and .gitignore behavior verified.
- [x] Project can be prepared locally without VPS access.
- [x] Local ports are not accidentally publicly exposed.
- [x] Commands and rollback/cleanup are documented.

The validation script completed successfully and removed its dedicated
container/network. No existing container was stopped or changed. No VPS or
Rahti endpoint was accessed.

## Codex request
Implement **only Phase 01** on my **local laptop**. Read AGENTS.md and this phase; set up reproducible local Docker/Compose development and documentation. Do not touch VPS or Rahti and stop before Phase 02.

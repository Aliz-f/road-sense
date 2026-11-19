# Phase 07 — Validation, demonstration and submission

**Status:** Not started. Documentation only.

## Goal
Prove system correctness and deliver artifacts matching current course rules.

## Prerequisites / inputs
Successful Phase 06 integration; current official course instructions and owner approval for recording/submission.

## Detailed instructions for Codex
1. Run integration/numeric/idempotency/restart/security tests
2. compare 2 sessions with speed caveats
3. capture sanitized logs and resource screenshots
4. export Mermaid diagram to arch.png after matching actual system
5. update citations and source usage
6. prepare required GitLab Final-Project files, open-source.url and video-demonstration.url if specified
7. rehearse short narrated demo
8. require user-led recording and explicit submission approval.

## Deliverables / documentation
Test/evidence report, architecture PNG, final setup/teardown documentation, submission checklist, demo outline/recording URL and course fork artifacts.

## Acceptance / exit gate
- [ ] End-to-end repeatable
- [ ] no secret/data leakage
- [ ] all current official requirements checked
- [ ] correct course GitLab submission path
- [ ] user confirms final delivery.

## Required phase report
Codex must record actual commands (without secrets), files created, test commands and results, observed output screenshots/logs, assumptions, unresolved risks and the rollback procedure when relevant. Do not mark complete on unverified claims.

## Copyable Codex request
Implement **only Phase 07** for RoadSense. First read AGENTS.md, README.md, docs/architecture.md, docs/contracts.md, docs/operations.md, and this phase. Work in a dedicated branch, follow the prerequisites and acceptance gates, deliver the listed documentation and tests, and STOP before the next phase. Do not invent dataset facts, successful tests, or cloud deployment status.

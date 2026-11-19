# Phase 02 — Sensor feeder and MQTT

**Status:** Not started. Documentation only.

## Goal
Replay genuine Bosch IMU data from the VPS into an MQTT broker in local Compose.

## Prerequisites / inputs
Actual profiled dataset and secured VPS; MQTT raw JSON v1 contract.

## Detailed instructions for Codex
1. Write Python CSV reader with run_id, session_id, batches, sample index, source timestamps, configurable replay speed and graceful shutdown
2. Dockerize it
3. run local Mosquitto on Compose network with credentials
4. publish roadsense/v1/imu/raw
5. add test subscriber and parser tests
6. log sanitized evidence.

## Deliverables / documentation
services/sensor-replay, Dockerfile, Compose broker definition, tests, README, real message sample.

## Acceptance / exit gate
- [ ] One recording reliably replayed
- [ ] subscribed client receives ordered JSON messages
- [ ] topic auth works
- [ ] replay rate configurable
- [ ] no unauthenticated public broker or secrets in Git.

## Required phase report
Codex must record actual commands (without secrets), files created, test commands and results, observed output screenshots/logs, assumptions, unresolved risks and the rollback procedure when relevant. Do not mark complete on unverified claims.

## Copyable Codex request
Implement **only Phase 02** for RoadSense. First read AGENTS.md, README.md, docs/architecture.md, docs/contracts.md, docs/operations.md, and this phase. Work in a dedicated branch, follow the prerequisites and acceptance gates, deliver the listed documentation and tests, and STOP before the next phase. Do not invent dataset facts, successful tests, or cloud deployment status.

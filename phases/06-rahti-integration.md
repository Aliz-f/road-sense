# Phase 06 — Publish Docker images and deploy across personal VPS + CSC Rahti

**Status:** Deployment files and learning runbook prepared in `phase/06-deployment-prep`. No remote deployment has been performed; exit checklist is still open.

## Goal
Take the tested **local laptop** application and deploy it into the intended **two remote environments**: personal VPS and Rahti.

## Inputs
Passed laptop end-to-end Phase 05; approved Docker registry; personal VPS specs and access; CSC Rahti namespace/quota/credentials; approval for remote changes.

## Instructions
1. Ensure local Compose integration tests passed and document versioned release images/digests.
2. Build/push versioned images to approved registry; separate configuration from images.
3. Inventory, secure and prepare personal VPS with Docker Engine/Compose and restricted MUHOS dataset volume (with owner approval).
4. Deploy **only** sensor-replay and dashboard to VPS using Docker Compose; keep it initially private/guarded.
5. Inspect Rahti namespace, quotas, PVC classes, HTTPS Route support, and CSC
   approval/assignment for a raw-TCP LoadBalancer ingress IP.
6. Deploy Mosquitto, signal-processor, road-analyzer, PostgreSQL/PVC and FastAPI to Rahti with resource limits, probes, private DB and controlled external endpoints.
7. Point VPS feeder to Rahti broker via authenticated MQTT/TLS; dashboard to Rahti API via HTTPS. Do not expose database publicly.
8. Run and record full real-data trace VPS CSV → Rahti broker → processor → analyzer → database → API → VPS dashboard.
9. Test restart, replay duplicate handling, persistence, secure access, recovery and rollback.

Deployment preparation and step-by-step commands: [Phase 06 deployment guide](../docs/phase-06-deployment-guide.md).

## Deliverables
Versioned published images, `infrastructure/vps` and `infrastructure/rahti` deployment instructions/manifests, VPS Compose, settings templates, approved remote configuration, test evidence and rollback guide.

## Exit checklist
- [ ] Whole app passed local Compose tests before promotion.
- [ ] VPS runs feeder + dashboard, with credentials and data protected.
- [ ] Rahti runs broker, processor, analyzer, DB and API in healthy Pods.
- [ ] MQTT/TLS and HTTPS cross-environment connections verified.
- [ ] Database persists; no secrets/public DB exposure.
- [ ] Full end-to-end remote flow demonstrated.
- [ ] Owner approval recorded for remote changes; rollback documented.

## Codex request
Implement **only Phase 06**. Promote my already-tested **laptop** application onto **my own VPS** (sensor feeder + dashboard) and **CSC Rahti** (backend). Require approval before changing remote infrastructure. Test end-to-end and stop before Phase 07.

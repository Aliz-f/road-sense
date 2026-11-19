# Phase 05 — Local FastAPI and Streamlit Dashboard

**Status:** Not started. Documentation only.

## Goal
Complete the **whole application on the laptop**, running all services via Docker Compose and a local browser.

## Inputs
Phases 02–04 implemented locally, PostgreSQL data and API contracts.

## Instructions
1. Create FastAPI endpoints for health, recordings, runs, features and alerts; use typed validation and pagination.
2. Create Streamlit + Plotly dashboard with recording selection, vibration charts, event display, processing status and methodology limitations.
3. Keep dashboard ↔ API communication over HTTP (no direct DB or MQTT in dashboard).
4. Add API unit tests, dashboard smoke tests, and local Compose integration test using real MUHOS recordings.
5. Configure accessible laptop browser URL via loopback while keeping DB/MQTT ports internal.
6. Verify full laptop pipeline: CSV → feeder → MQTT → processor → analyzer → DB → API → dashboard.
7. Document full local startup/shutdown and capture sanitized demo evidence.

## Deliverables
Dockerized FastAPI and Streamlit services, complete laptop Compose environment, automated/smoke tests and local end-to-end report.

## Exit checklist
- [ ] All seven services operate together **on laptop**.
- [ ] Real IMU source produces features, events, API records and visualization.
- [ ] Each service has independent container ownership and documented logs.
- [ ] HTTP paths validated, non-sensitive local ports accessible.
- [ ] App works end-to-end without VPS or Rahti.

## Codex request
Implement **only Phase 05**. Finish the app on my **local laptop** with full Docker Compose integration and tests. Do not deploy remotely or start Phase 06.

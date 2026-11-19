# Docker Compose

**Status: Phase 01 local preflight verified — no application Compose stack or
deployment exists.**

`preflight.compose.yaml` verifies the laptop daemon, Compose lifecycle, health
checks, an internal network, a read-only root filesystem, and absence of
published ports. It contains no RoadSense application service.

Phase 02 adds a broker and feeder on the **local laptop**; Phases 03–05 create
the complete **laptop Compose development stack**; Phase 06 creates a separate
VPS Compose deployment for only sensor-replay and dashboard.

See `../../docs/local-development.md`, the numbered specifications under
`../../phases/`, and `../../docs/architecture.md`.

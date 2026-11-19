# Docker Compose

**Status: Phase 03 local Sensor Replay + MQTT + Signal Processor stack
verified. No later-phase service or remote deployment exists.**

`preflight.compose.yaml` verifies the laptop daemon, Compose lifecycle, health
checks, an internal network, a read-only root filesystem, and absence of
published ports. It contains no RoadSense application service.

Phases 02–03 add the broker, feeder, and processor on the **local laptop**;
Phases 04–05 complete the **laptop Compose development stack**; Phase 06
creates a separate VPS Compose deployment for only sensor-replay and dashboard.

`local.compose.yaml` currently contains Sensor Replay, Signal Processor, a
TLS/authenticated Mosquitto broker, an auth-file initializer, and
profile-gated raw/feature subscribers and unit-test containers. The broker and
services have no host-published ports; all MQTT traffic stays on the internal
`roadsense-local_roadsense` network. Local passwords, certificate keys, and
dataset paths are generated under Git-ignored paths by
`../../tools/prepare_phase02_local.sh`.

See `../../docs/local-development.md`, the numbered specifications under
`../../phases/`, and `../../docs/architecture.md`.
